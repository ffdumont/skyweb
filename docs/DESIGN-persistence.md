# Conception Technique — Couche de Persistance

## 1. Vue d'ensemble

La couche de persistance couvre deux systèmes distincts :

| Système | Données | Mode | Technologie |
|---------|---------|------|-------------|
| **Firestore** | Données utilisateur (routes, waypoints, aircraft, flights, simulations) | Read-write, isolé par `user_id` | `google-cloud-firestore` AsyncClient |
| **SpatiaLite sur GCS** | Référence aéronautique (~22 Mo, 63k espaces, 255k géométries, aérodromes, fréquences) | Read-only, versionné par cycle AIRAC | `sqlite3` + SpatiaLite, `google-cloud-storage` |

### 1.1 Principes

| Principe | Détail |
|----------|--------|
| **Contracts-first** | Les modèles Pydantic v2 (`core/contracts/`) sont le schéma de référence. La persistance sérialise via `to_firestore()` et désérialise via `from_firestore()`. |
| **Repository pattern léger** | Une classe par collection Firestore, pas de framework ORM. |
| **Isolation par user_id** | Tout accès Firestore requiert un `user_id` explicite. Aucune méthode ne peut accéder aux données d'un autre utilisateur. |
| **Read-only pour la référence** | SpatiaLite est ouvert en `?mode=ro`. Aucune écriture en production. |
| **Budget minimal** | Pas de Cloud SQL. GCS + SQLite en RAM = coût quasi-nul. |

---

## 2. Structure des fichiers

```
core/persistence/
├── __init__.py
├── firestore_client.py          # Singleton AsyncClient
├── errors.py                    # Exceptions persistance
├── repositories/
│   ├── __init__.py
│   ├── base.py                  # BaseRepository[T] générique
│   ├── waypoint_repo.py         # UserWaypoint CRUD + batch + tags
│   ├── route_repo.py            # Route CRUD + batch atomique + subcollection simulations
│   ├── aircraft_repo.py         # Aircraft CRUD
│   ├── flight_repo.py           # Flight CRUD + filtre par statut
│   └── community_repo.py        # /community/vac_notes, /community/tdp_database
└── spatialite/
    ├── __init__.py
    ├── db_manager.py            # GCS download, cache local, connexion read-only
    ├── airspace_query.py        # Requêtes spatiales → AirspaceIntersection
    └── aerodrome_query.py       # Lookup ICAO, bbox → AerodromeInfo
```

---

## 3. Firestore — Client

```python
# core/persistence/firestore_client.py

from google.cloud.firestore import AsyncClient

_client: AsyncClient | None = None

def get_firestore_client() -> AsyncClient:
    """Lazy singleton. Utilise ADC (Application Default Credentials).
    En dev, utilise FIRESTORE_EMULATOR_HOST si défini.
    """
    global _client
    if _client is None:
        _client = AsyncClient()
    return _client
```

---

## 4. Firestore — BaseRepository[T]

Repository générique typé pour les collections sous `/users/{user_id}/`.

```python
# core/persistence/repositories/base.py

class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T], collection_name: str):
        self._model_class = model_class
        self._collection_name = collection_name

    def _collection_ref(self, user_id: str):
        db = get_firestore_client()
        return db.collection("users").document(user_id).collection(self._collection_name)
```

### Méthodes CRUD

| Méthode | Comportement |
|---------|-------------|
| `get(user_id, doc_id) → T \| None` | Lit le document, injecte `doc.id` dans le dict avant `from_firestore()`. |
| `list_all(user_id) → list[T]` | Stream tous les documents de la collection. |
| `create(user_id, entity) → str` | Extrait `id` du dict `to_firestore()` pour l'utiliser comme document ID (ex: UserWaypoint MD5). Si absent, Firestore auto-génère. Retourne le doc ID. |
| `update(user_id, doc_id, entity)` | `set(data, merge=True)` pour mise à jour partielle. |
| `delete(user_id, doc_id)` | Suppression simple. |

### Gestion de l'ID

```python
async def create(self, user_id: str, entity: T) -> str:
    data = entity.to_firestore()
    doc_id = data.pop("id", None)      # Extrait l'ID déterministe s'il existe
    if doc_id:
        await self._collection_ref(user_id).document(doc_id).set(data)
        return doc_id
    else:
        ref = await self._collection_ref(user_id).add(data)
        return ref[1].id

async def get(self, user_id: str, doc_id: str) -> T | None:
    doc = await self._collection_ref(user_id).document(doc_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id                # Réinjecte l'ID dans le dict
    return self._model_class.from_firestore(data)
```

`UserWaypoint.id` est un `@computed_field` (MD5 de nom+lat+lon). `to_firestore()` l'inclut dans le dict. `create()` l'utilise comme document ID → déduplication naturelle (écrire deux fois le même waypoint = même document).

---

## 5. Repositories concrets

### 5.1 WaypointRepository

```python
class WaypointRepository(BaseRepository[UserWaypoint]):
    def __init__(self):
        super().__init__(UserWaypoint, "user_waypoints")
```

| Méthode | Détail |
|---------|--------|
| `get_by_ids(user_id, ids) → dict[str, UserWaypoint]` | Batch fetch via `get_all()` (Firestore supporte jusqu'à 30 refs par appel). |
| `find_by_tag(user_id, tag) → list[UserWaypoint]` | Query avec `where("tags", "array_contains", tag)`. |

### 5.2 RouteRepository

```python
class RouteRepository(BaseRepository[Route]):
    def __init__(self):
        super().__init__(Route, "routes")
```

| Méthode | Détail |
|---------|--------|
| `save_with_waypoints(user_id, route, waypoints) → str` | **Batch atomique** : promeut les waypoints éphémères en `UserWaypoint` + sauvegarde la route en un seul commit. Garantit qu'une route ne référence jamais des waypoints non persistés. |
| `add_simulation(user_id, route_id, sim) → str` | Écrit dans la subcollection `/routes/{route_id}/simulations/`. |
| `get_simulation(user_id, route_id, sim_id) → WeatherSimulation \| None` | Lecture depuis la subcollection. |
| `list_simulations(user_id, route_id) → list[WeatherSimulation]` | Stream de la subcollection. |

**Batch atomique** (save_with_waypoints) :

```python
async def save_with_waypoints(self, user_id: str, route: Route, waypoints: list[UserWaypoint]) -> str:
    db = get_firestore_client()
    batch = db.batch()

    # Promotion des waypoints
    wp_col = db.collection("users").document(user_id).collection("user_waypoints")
    for wp in waypoints:
        data = wp.to_firestore()
        wp_id = data.pop("id")
        batch.set(wp_col.document(wp_id), data)

    # Sauvegarde de la route
    route_data = route.to_firestore()
    route_id = route_data.pop("id", None)
    route_col = self._collection_ref(user_id)
    if route_id:
        batch.set(route_col.document(route_id), route_data)
    else:
        route_ref = route_col.document()
        route_id = route_ref.id
        batch.set(route_ref, route_data)

    await batch.commit()
    return route_id
```

### 5.3 AircraftRepository

```python
class AircraftRepository(BaseRepository[Aircraft]):
    def __init__(self):
        super().__init__(Aircraft, "aircraft")
```

CRUD standard, pas de méthode spécifique.

### 5.4 FlightRepository

```python
class FlightRepository(BaseRepository[Flight]):
    def __init__(self):
        super().__init__(Flight, "flights")
```

| Méthode | Détail |
|---------|--------|
| `list_by_status(user_id, status) → list[Flight]` | Query avec `where("status", "==", status.value)`. |

### 5.5 CommunityRepository

Collections partagées, **pas scopées par user_id** :

```python
class CommunityRepository:
    """CRUD pour /community/ (VAC notes, TDP database)."""

    async def get_vac_notes(self, icao: str) -> dict | None
    async def set_vac_notes(self, icao: str, data: dict, user_id: str) -> None
        # Ajoute updated_by + updated_at automatiquement

    async def get_tdp(self, icao: str) -> dict | None
```

Paths Firestore :
- `/community/vac_notes/entries/{icao}`
- `/community/tdp_database/entries/{icao}`

---

## 6. Exceptions

```python
# core/persistence/errors.py

class PersistenceError(Exception):
    """Base pour toutes les erreurs de persistance."""

class DocumentNotFoundError(PersistenceError):
    def __init__(self, collection: str, doc_id: str):
        self.collection = collection
        self.doc_id = doc_id
        super().__init__(f"{collection}/{doc_id} not found")

class SpatiaLiteNotReadyError(PersistenceError):
    """La base SpatiaLite n'est pas encore téléchargée."""

class AIRACCycleError(PersistenceError):
    """Erreur lors des opérations sur le cycle AIRAC."""
```

---

## 7. Injection dans FastAPI

```python
# api/deps.py (futur)

from core.persistence.repositories.route_repo import RouteRepository

def get_route_repo() -> RouteRepository:
    return RouteRepository()

# Dans un endpoint :
@router.get("/api/routes/{route_id}")
async def get_route(
    route_id: str,
    user_id: str = Depends(get_current_user_id),
    repo: RouteRepository = Depends(get_route_repo),
):
    route = await repo.get(user_id, route_id)
    if not route:
        raise HTTPException(404)
    return route
```

---

## 8. SpatiaLite — SpatiaLiteManager

Gère le cycle de vie de la base de référence aéronautique.

```python
# core/persistence/spatialite/db_manager.py

class SpatiaLiteManager:
    """Télécharge, cache et sert des connexions read-only vers la base SpatiaLite."""

    def __init__(
        self,
        bucket_name: str = "skyweb-reference",
        db_prefix: str = "airac",
        db_filename: str = "skypath.db",
        local_dir: str | None = None,       # défaut: tempfile.gettempdir()
    ): ...

    @property
    def current_cycle(self) -> str | None: ...
    @property
    def is_ready(self) -> bool: ...

    def download(self, cycle: str | None = None) -> Path:
        """Télécharge depuis GCS. Si cycle=None, lit gs://skyweb-reference/current_cycle."""

    def get_connection(self) -> sqlite3.Connection:
        """Connexion read-only avec SpatiaLite chargé."""
```

### Détails d'implémentation

**Download** :
```
gs://skyweb-reference/
├── current_cycle                          → fichier texte contenant "2604"
└── airac/
    ├── 2603/skypath.db
    └── 2604/skypath.db
```

Cache local : `/tmp/skypath_{cycle}.db`. Si le fichier existe déjà, pas de re-téléchargement.

**Connexion** :
```python
def get_connection(self) -> sqlite3.Connection:
    if not self.is_ready:
        raise SpatiaLiteNotReadyError()
    uri = f"file:{self._local_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    conn.load_extension("mod_spatialite")
    return conn
```

- `?mode=ro` : read-only, concurrent readers OK, aucun lock.
- Sur Cloud Run, `/tmp` est tmpfs → la DB vit en RAM (~22 Mo).
- Chaque requête ouvre sa propre connexion (léger, pas de pool nécessaire en read-only).

### Startup hook FastAPI

```python
from contextlib import asynccontextmanager

spatialite_manager = SpatiaLiteManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    spatialite_manager.download()
    yield

app = FastAPI(lifespan=lifespan)
```

---

## 9. SpatiaLite — Requêtes spatiales

### 9.1 AirspaceQueryService

Port des requêtes SkyPath (`skypath_services/airspace_api.py`) mappées vers les contrats SkyWeb.

```python
class AirspaceQueryService:
    def __init__(self, manager: SpatiaLiteManager): ...
```

| Méthode | Signature | Détail |
|---------|-----------|--------|
| `query_segment_airspaces` | `(lat1, lon1, lat2, lon2, altitude_ft, corridor_nm=2.5) → list[AirspaceIntersection]` | Détection d'intersection segment/espace avec filtre altitude. |
| `analyze_route` | `(waypoints, legs) → list[LegAirspaces]` | Analyse complète de route, appelle `query_segment_airspaces` par leg. |

**Requête principale** (query_segment_airspaces) :

```sql
SELECT a.identifier, a.type, a.class, a.lower_ft, a.upper_ft,
       a.partie_pk, a.volume_pk
FROM airspace_spatial_indexed a
WHERE a.ROWID IN (
    SELECT ROWID FROM SpatialIndex
    WHERE f_table_name = 'airspace_spatial_indexed'
      AND f_geometry_column = 'Geometrie'
      AND search_frame = BuildMbr(?, ?, ?, ?)    -- Filtre R-tree (rapide)
)
AND ST_Intersects(a.Geometrie, GeomFromText(?, 4326))  -- Test exact
AND a.lower_ft <= ?                                       -- Filtre altitude
AND a.upper_ft >= ?
```

La vue matérialisée `airspace_spatial_indexed` (créée phase 4 du pipeline SkyPath) pré-joint Espace→Partie→Volume avec altitudes converties en ft AMSL. Performance : ~10-50 ms par segment.

**Services et fréquences** — jointure secondaire :

```sql
SELECT s.IndicLieu, s.IndicService, f.Frequence, f.Espacement
FROM Service s
LEFT JOIN Frequence f ON f.lk_service = s.pk
WHERE s.lk_partie = ?
```

Résultat mappé vers `ServiceInfo` → `FrequencyInfo` → `AirspaceIntersection.services`.

### 9.2 AerodromeQueryService

```python
class AerodromeQueryService:
    def __init__(self, manager: SpatiaLiteManager): ...
```

| Méthode | Signature | Détail |
|---------|-----------|--------|
| `get_by_icao` | `(icao) → AerodromeInfo \| None` | Jointure complète : aérodrome + pistes + services + fréquences → contrat `AerodromeInfo`. |
| `search_bbox` | `(lat_min, lon_min, lat_max, lon_max) → list[AerodromeInfo]` | Recherche légère sans jointures complètes (pour l'affichage carte). |

---

## 10. Cycle AIRAC

### 10.1 Flux de mise à jour

```
1. Pipeline ETL (Cloud Run Job)
   └── XML SIA → phases 0-5 → skypath.db
   └── Upload : gs://skyweb-reference/airac/{cycle}/skypath.db

2. Écriture métadonnées Firestore
   └── /admin/airac_cycles/{cycle} = {
         status: "ready",
         uploaded_at: "...",
         db_size_bytes: 22000000,
         airspace_count: 63000,
         aerodrome_count: 480
       }

3. Activation (manuelle)
   └── Mise à jour gs://skyweb-reference/current_cycle → "2604"
   └── Firestore /admin/current_cycle → {cycle: "2604", activated_at: "..."}

4. Instances Cloud Run
   └── Nouvelles instances téléchargent le cycle activé au démarrage
   └── Instances existantes sont recyclées naturellement par Cloud Run
```

### 10.2 Coexistence de versions

Le cache local utilise des noms de fichiers spécifiques au cycle (`skypath_2604.db`). Un changement de cycle n'écrase pas la connexion en cours. Les instances en cours de traitement continuent avec l'ancien cycle jusqu'à leur recyclage.

### 10.3 Pas de hot-reload en v1

Pour un projet mono-développeur à faible trafic, le recyclage naturel des instances Cloud Run (quelques minutes d'inactivité) suffit. Si le hot-reload devient nécessaire, ajouter un listener Firestore sur `/admin/current_cycle`.

### 10.4 Endpoint de santé

```python
@router.get("/health/airac")
def airac_health():
    return {
        "cycle": spatialite_manager.current_cycle,
        "ready": spatialite_manager.is_ready,
    }
```

---

## 11. Dépendances

### pyproject.toml

```toml
[project.optional-dependencies]
gcp = [
    "google-cloud-firestore>=2.16",
    "google-cloud-storage>=2.16",
]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.3",
    "mypy>=1.9",
]
```

### Dockerfile Cloud Run

```dockerfile
RUN apt-get update && apt-get install -y libsqlite3-mod-spatialite && rm -rf /var/lib/apt/lists/*
```

Le chemin de l'extension sur Debian/Ubuntu est `/usr/lib/x86_64-linux-gnu/mod_spatialite.so`. `load_extension("mod_spatialite")` le trouve automatiquement si il est dans le library path.

---

## 12. Stratégie de test

### 12.1 Repositories Firestore — FakeFirestoreClient

Pas d'émulateur requis. Un `FakeFirestoreClient` in-memory (dict-backed) réplique le pattern roundtrip déjà prouvé dans les tests contrats :

```python
class FakeDocumentRef:
    def __init__(self, store: dict, path: str):
        self._store = store
        self._path = path
        self.id = path.split("/")[-1]

    async def get(self):
        return FakeDocumentSnapshot(self._store.get(self._path), self.id)

    async def set(self, data, merge=False):
        if merge and self._path in self._store:
            self._store[self._path].update(data)
        else:
            self._store[self._path] = dict(data)

    async def delete(self):
        self._store.pop(self._path, None)
```

### 12.2 Requêtes SpatiaLite — Fixture réelle

Les requêtes spatiales sont testées contre une vraie base SpatiaLite minimale (2-3 espaces aériens de test) :

```python
@pytest.fixture
def spatialite_service(tmp_path):
    db_path = tmp_path / "test_skypath.db"
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    conn.load_extension("mod_spatialite")
    conn.execute("SELECT InitSpatialMetaData(1)")
    # Créer schéma minimal + insérer TMA PARIS, CTR TOUSSUS...
    conn.close()

    manager = SpatiaLiteManager(local_dir=str(tmp_path))
    manager._local_path = db_path
    manager._current_cycle = "test"
    return AirspaceQueryService(manager)
```

### 12.3 GCS — Mock ou skip

Le `SpatiaLiteManager.download()` est testé avec un mock de `storage.Client`, ou `@pytest.mark.skipif` en CI.

### 12.4 Matrice de tests

| Couche | Ce qu'on teste | Approche | Réseau |
|--------|---------------|----------|--------|
| Contrats `to_firestore()`/`from_firestore()` | Sérialisation roundtrip | Dict equality (déjà fait) | Non |
| `BaseRepository` CRUD | Paths, injection ID | `FakeFirestoreClient` | Non |
| `WaypointRepository.get_by_ids` | Batch fetch | `FakeFirestoreClient` | Non |
| `RouteRepository.save_with_waypoints` | Batch atomique | `FakeFirestoreClient` | Non |
| `AirspaceQueryService` | SQL + mapping contrats | Fixture SpatiaLite réelle | Non |
| `AerodromeQueryService` | SQL + mapping contrats | Fixture SQLite réelle | Non |
| `SpatiaLiteManager.download` | Intégration GCS | Mock `storage.Client` | Non |

---

## 13. Schéma Firestore complet

```
/users/{user_id}/
├── user_waypoints/{waypoint_id}           → UserWaypoint
│   (ID = MD5(name:lat:lon)[:16], déterministe)
│
├── routes/{route_id}                      → Route
│   ├── waypoints: [RouteWaypointRef]
│   ├── legs: [RouteLeg]
│   └── simulations/{simulation_id}        → WeatherSimulation
│       ├── waypoints: [WaypointContext]
│       └── model_results: [ModelResult]
│
├── aircraft/{aircraft_id}                 → Aircraft
│   ├── loading_stations: [LoadingStation]
│   ├── envelope_points: [EnvelopePoint]
│   └── fuel_profile: FuelProfile
│
└── flights/{flight_id}                    → Flight
    ├── route_snapshot: Route
    ├── station_loads: [StationLoad]
    └── track: Track (optionnel, post-vol)

/community/
├── vac_notes/entries/{icao}               → notes VAC collaboratives
└── tdp_database/entries/{icao}            → altitude + sens TDP

/admin/
├── current_cycle                          → {cycle: "2604", activated_at: "..."}
└── airac_cycles/{cycle}                   → métadonnées (status, taille, compteurs)
```

---

*Document créé : 2026-02-02*
*Version : 0.1 — Design initial*
*Documents liés :*
- [DESIGN-contracts.md](DESIGN-contracts.md) — Contrats de données (dépendance)
- [SPEC-skypath-web.md](SPEC-skypath-web.md) — Architecture SpatiaLite/GCS (source)
- [DESIGN-weather.md](DESIGN-weather.md) — Module météo (consommateur)
