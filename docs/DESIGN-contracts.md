# Conception Technique — Contrats de Données

## 1. Vue d'ensemble

Les contrats de données SkyWeb sont des modèles **Pydantic v2** qui constituent le socle partagé entre tous les services et l'API. Ils définissent la structure, la validation et la sérialisation de toutes les entités métier.

### 1.1 Principes de conception

| Principe | Détail |
|----------|--------|
| **Pydantic v2 BaseModel** | Validation automatique, sérialisation JSON/dict intégrée, intégration native FastAPI |
| **Enums `str`** | Toutes les énumérations héritent de `str, Enum` pour une sérialisation string native |
| **Firestore-ready** | Base class `FirestoreModel` avec `to_firestore()` / `from_firestore()` |
| **Référence par ID** | Les routes référencent des waypoints par ID, pas par embedding (efficacité Firestore) |
| **Persisté vs calculé** | On stocke les intentions du pilote ; distance, cap, ETE et points CLIMB/DESC sont dérivés au runtime |
| **Indépendant de SkyPath** | Contrats propres à SkyWeb, structurellement compatibles avec SkyPath mais sans import |

### 1.2 Structure des fichiers

```
core/contracts/
├── __init__.py         # Re-exports publics
├── enums.py            # Énumérations partagées
├── common.py           # FirestoreModel (base), GeoPoint
├── result.py           # ServiceResult[T] générique
├── waypoint.py         # Waypoint (éphémère), UserWaypoint (persisté)
├── route.py            # Route, RouteLeg, RouteProjection, ProjectionAssumptions
├── aircraft.py         # Aircraft, FuelProfile
├── flight.py           # Flight, Track, WaypointPassageTime
├── weather.py          # WeatherSimulation, modèles multi-modèle
├── airspace.py         # AirspaceIntersection, LegAirspaces
└── aerodrome.py        # AerodromeInfo, Runway, services
```

### 1.3 Responsabilité et nature des modèles

Chaque modèle a une **nature contractuelle** explicite. Cette classification est un invariant du système.

| Modèle | Nature | Persisté | Stable dans le temps | Description |
|--------|--------|----------|---------------------|-------------|
| `Route` | **Intention** | Oui (Firestore) | Oui | Navigation horizontale et verticale, indépendante du temps, de la météo et de l'avion |
| `RouteLeg` | **Intention** (champs persistés) + **Projection** (champs calculés) | Partiellement | Champs persistés: oui. Champs calculés: non | Altitude = intention pilote. Distance, cap, ETE = projection sous hypothèses |
| `RouteProjection` | **Projection** | Non (API response) | Non | Vue calculée d'une Route sous un jeu d'hypothèses explicites (heure, avion, vent). Peut être recalculée à tout moment. Résultats non garantis stables |
| `Flight` | **Intention** + **Snapshot** | Oui (Firestore) | Oui | Instance de vol avec références figées vers météo et NOTAM collectés |
| `WeatherSimulation` | **Snapshot** | Oui (Firestore) | Oui (figé à la collecte) | Capture météo à un instant donné. Jamais auto-rafraîchi |
| `Aircraft` | **Configuration** | Oui (Firestore) | Oui | Données avion stables (modifiable par l'utilisateur) |
| `UserWaypoint` | **Référence utilisateur** | Oui (Firestore) | Oui | Lieu sauvegardé pour réutilisation |
| `Waypoint` | **Éphémère** | Non | N/A | Lieu temporaire durant import/édition |
| `AerodromeInfo` | **Référence partagée** | Non (SQLite) | Par cycle AIRAC | Données de référence SIA, read-only |
| `LegAirspaces` | **Projection** | Non | Non | Analyse d'intersection route/espaces aériens |

> **Règle** : un développeur frontend ou backend doit pouvoir déterminer la nature d'un objet (intention / projection / snapshot) sans lire le code source.

---

## 2. Base commune

### 2.1 FirestoreModel

Classe de base dont héritent tous les modèles métier. Fournit la sérialisation Firestore.

```python
class FirestoreModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    def to_firestore(self) -> dict[str, Any]
    def from_firestore(cls, data: dict[str, Any]) -> FirestoreModel
```

- `to_firestore()` : appelle `model_dump(mode="json", exclude_none=True)` → datetimes en ISO 8601, enums en strings, champs `None` exclus.
- `from_firestore()` : appelle `model_validate()` → coercion automatique (ex : clés `str` → `int` pour les niveaux de pression).

### 2.2 GeoPoint

Coordonnée WGS84 immuable (usage interne, pas un modèle Firestore).

```python
class GeoPoint(BaseModel):
    latitude: float
    longitude: float
```

### 2.3 ServiceResult[T]

Enveloppe générique pour les retours de services.

```python
class ServiceResult(BaseModel, Generic[T]):
    success: bool
    data: T | None
    error: ServiceError | None
    duration_ms: float | None
    timestamp: datetime

    @classmethod ok(data: T) -> ServiceResult[T]
    @classmethod fail(code: str, message: str) -> ServiceResult[T]
```

---

## 3. Énumérations

Définies dans `core/contracts/enums.py`. Toutes héritent de `str, Enum`.

| Enum | Valeurs | Usage |
|------|---------|-------|
| `LocationType` | `aerodrome`, `navaid`, `visual_reference`, `gps_point` | Nature intrinsèque du lieu |
| `WaypointRole` | `departure`, `arrival`, `alternate`, `enroute` | Rôle d'un waypoint dans une route spécifique |
| `WaypointSource` | `sdvfr_import`, `manual`, `gpx_trace` | Origine du waypoint (UserWaypoint uniquement) |
| `FlightStatus` | `draft`, `planned`, `ready`, `completed`, `cancelled` | Cycle de vie du vol |
| `TrackSource` | `gpx_file`, `flightaware`, `manual` | Source de la trace GPS |
| `ForecastModel` | `arome_france`, `arome_hd`, `arpege_europe`, `arpege_world` | Modèle météo |
| `VFRStatus` | `green`, `yellow`, `red` | Indice sécurité VFR |
| `CloudCover` | `CLR`, `FEW`, `SCT`, `BKN`, `OVC` | Couverture nuageuse METAR |
| `AirspaceType` | `TMA`, `CTR`, `SIV`, `D`, `R`, `P`, `TSA`, `CBA`, `AWY`, `FIR`, `OTHER` | Type d'espace aérien |
| `IntersectionType` | `crosses`, `inside`, `corridor` | Mode d'intersection route/espace |
| `AerodromeStatus` | `CAP`, `restricted`, `military`, `closed` | Statut opérationnel AD |

---

## 4. Modèles métier

### 4.1 Waypoint et UserWaypoint

Deux niveaux de modélisation pour les lieux géographiques :

- **`Waypoint`** — lieu éphémère, utilisé dans le contexte d'une seule navigation. Non persisté dans Firestore.
- **`UserWaypoint`** (hérite de `Waypoint`) — lieu **sauvegardé** par l'utilisateur pour réutilisation entre plusieurs routes.

```
Firestore: /users/{user_id}/user_waypoints/{waypoint_id}   (UserWaypoint uniquement)
```

#### Waypoint (éphémère)

| Champ | Type | Description |
|-------|------|-------------|
| `id` | `str` (computed) | MD5(name:lat:lon)[:16] — déterministe |
| `name` | `str` | Nom du waypoint (ex: `MOR1V`, `LFXU - LES MUREAUX`) |
| `latitude` | `float` | WGS84, [-90, 90] |
| `longitude` | `float` | WGS84, [-180, 180] |
| `location_type` | `LocationType` | Nature du lieu : `aerodrome`, `navaid`, `visual_reference`, `gps_point` |
| `icao_code` | `str?` | Code OACI si aérodrome (pattern `^[A-Z]{4}$`) |
| `description` | `str?` | Description libre |

Le `location_type` décrit la **nature intrinsèque** du lieu. Il ne préjuge pas du rôle que ce waypoint joue dans une route donnée — c'est le `WaypointRole` sur `RouteWaypointRef` qui porte cette information.

#### UserWaypoint (persisté)

Hérite de tous les champs de `Waypoint` et ajoute les métadonnées de persistance :

| Champ | Type | Description |
|-------|------|-------------|
| *(tous les champs Waypoint)* | | |
| `source` | `WaypointSource` | `sdvfr_import`, `manual`, `gpx_trace` |
| `tags` | `list[str]` | Tags d'organisation (normalisés en minuscules) |
| `created_at` | `datetime` | Horodatage UTC de création |
| `updated_at` | `datetime?` | Dernière modification |

**Identifiant déterministe** : l'`id` est un `@computed_field` calculé par `MD5(name:lat:lon)[:16]`. Deux waypoints avec les mêmes nom et coordonnées produisent le même ID, ce qui permet le **dédoublonnage** lors de l'import SDVFR.

**Quand utiliser lequel ?**

| Scénario | Modèle | Cycle de vie |
|----------|--------|-------------|
| Import SDVFR | `Waypoint` → `UserWaypoint` | Éphémère pendant l'import, promu à la sauvegarde |
| Waypoint créé manuellement et sauvegardé | `UserWaypoint` | Directement persisté |
| Waypoint créé pendant l'édition d'une route | `Waypoint` | Éphémère, promu automatiquement à la sauvegarde de la Route |
| Point extrait d'une trace GPX | `Waypoint` | Éphémère tant que non sauvegardé explicitement |

**Invariant contractuel** :

> Tout `Waypoint` éphémère est autorisé **uniquement** pendant l'import ou l'édition en cours.
> Lors de la persistance d'une `Route`, tout waypoint éphémère encore référencé est **automatiquement promu** en `UserWaypoint`.
> Une Route persistée ne référence **jamais** de waypoints non persistés.

**Validations** :
- Le nom est strippé automatiquement (espaces en début/fin supprimés).
- Les tags (UserWaypoint) sont normalisés en minuscules.
- Le code OACI doit être exactement 4 lettres majuscules.

### 4.2 Route

Une séquence ordonnée de waypoints avec des intentions d'altitude par tronçon.

```
Firestore: /users/{user_id}/routes/{route_id}
```

#### RouteWaypointRef

Référence un waypoint par son ID, avec un numéro d'ordre et un **rôle** dans la route.

| Champ | Type | Description |
|-------|------|-------------|
| `waypoint_id` | `str` | Référence vers `Waypoint.id` ou `UserWaypoint.id` |
| `sequence_order` | `int` | Position dans la route (1..N) |
| `role` | `WaypointRole` | Rôle dans la route (défaut: `enroute`) |

Le **rôle** (`WaypointRole`) décrit la fonction du waypoint dans cette route spécifique :

| Rôle | Description |
|------|-------------|
| `DEPARTURE` | Aérodrome de départ |
| `ARRIVAL` | Aérodrome d'arrivée |
| `ALTERNATE` | Aérodrome de dégagement |
| `ENROUTE` | Point en route — tournant, report, survol, etc. |

Un même lieu géographique peut avoir des rôles différents selon la route : `DEPARTURE` dans l'une, `ENROUTE` dans une autre.

#### RouteLeg

Un leg entre deux waypoints consécutifs. Combine l'**intention du pilote** (persistée) et la **projection calculée** (remplie au runtime, pas persistée).

| Champ | Type | Persisté | Description |
|-------|------|----------|-------------|
| `from_seq` | `int` | oui | `sequence_order` du waypoint de départ (≥1) |
| `to_seq` | `int` | oui | `sequence_order` du waypoint d'arrivée (= `from_seq + 1`) |
| `planned_altitude_ft` | `int` | oui | Altitude de croisière prévue en ft AMSL [0, 19500] |
| `distance_nm` | `float?` | non | Distance orthodromique (NM) |
| `true_heading_deg` | `float?` | non | Cap vrai (°) [0, 360[ |
| `magnetic_heading_deg` | `float?` | non | Cap magnétique (vrai + déclinaison) |
| `ground_speed_kt` | `float?` | non | Vitesse sol avec vent (kt) |
| `estimated_time_minutes` | `float?` | non | Durée estimée du leg |
| `wind_correction_deg` | `float?` | non | Correction de dérive vent |
| `fuel_consumption_liters` | `float?` | non | Consommation estimée (L) |

**Validation** : `to_seq` doit être exactement `from_seq + 1`.

Les champs calculés (`distance_nm`, `true_heading_deg`, etc.) sont remplis par le constructeur de nav log à partir des coordonnées des waypoints, du vent et des performances avion. Ils sont `None` par défaut et naturellement exclus par `to_firestore()` (`exclude_none=True`), donc jamais persistés dans Firestore.

#### Route

| Champ | Type | Description |
|-------|------|-------------|
| `id` | `str?` | ID Firestore du document |
| `name` | `str` | Nom de la route (ex: `LFXU-LFFU`) |
| `waypoints` | `list[RouteWaypointRef]` | Minimum 2 waypoints |
| `legs` | `list[RouteLeg]` | 0 ou N-1 legs (N = nombre de waypoints) |
| `source_kml_ref` | `str?` | Chemin GCS vers le KML source |
| `created_at` | `datetime` | Horodatage UTC |
| `updated_at` | `datetime?` | Dernière modification |

**Validations** :
- Les `sequence_order` doivent être consécutifs de 1 à N.
- Si des legs sont fournis, il doit y en avoir exactement N-1.
- Les legs ne peuvent pas référencer des `sequence_order` au-delà de N.

#### Relation Route → Waypoint

```
Route
  ├── waypoints: [RouteWaypointRef]  ──référence──→  Waypoint ou UserWaypoint (par ID)
  │                      └── role     (DEPARTURE, ARRIVAL, ALTERNATE, ENROUTE)
  └── legs: [RouteLeg]               ──référence──→  sequence_order des waypoints
```

Un même waypoint peut apparaître dans plusieurs routes. La route ne stocke que les références (IDs), pas les objets complets.

**Invariant de persistance des Waypoints** :

> Toute Route **persistée** dans Firestore ne référence que des `UserWaypoint` persistés.
> Les `Waypoint` éphémères sont autorisés uniquement pendant l'import ou l'édition en cours.
> Lors de la sauvegarde d'une Route, tout `Waypoint` éphémère encore référencé est **automatiquement promu** en `UserWaypoint`.

#### RouteProjection (calculé — DTO API)

Projection calculée d'une Route sous un jeu d'hypothèses explicites. Retournée par l'API, **jamais persistée**. Peut être recalculée à tout moment — les résultats ne sont pas garantis stables dans le temps (un changement de prévision vent produit une projection différente).

```
GET  /api/routes/{route_id}/projection?aircraft_id=...&departure=...
POST /api/routes/{route_id}/projection   (si hypothèses complexes)
```

| Champ | Type | Description |
|-------|------|-------------|
| `route_id` | `str` | Route source |
| `route_name` | `str` | Nom de la route (dénormalisé pour affichage) |
| `legs` | `list[RouteLeg]` | Legs avec champs calculés remplis |
| `assumptions` | `ProjectionAssumptions` | Hypothèses de calcul (voir ci-dessous) |
| `total_distance_nm` | `float` | Somme des distances des legs |
| `total_time_minutes` | `float` | Somme des ETE des legs |
| `total_fuel_liters` | `float?` | Somme des consommations (absent si pas d'avion) |
| `generated_at` | `datetime` | Horodatage de génération |

#### ProjectionAssumptions

Rend explicite chaque paramètre qui influence le résultat. Un changement d'hypothèse produit une projection différente.

| Champ | Type | Description |
|-------|------|-------------|
| `aircraft_id` | `str?` | Avion utilisé pour TAS et profil carburant |
| `cruise_speed_kt` | `int?` | TAS override (si pas d'avion) |
| `departure_datetime_utc` | `datetime?` | Heure de départ — pilote l'interpolation vent |
| `wind_source` | `str?` | Source vent : `arome_france`, `manual`, `none` |

**Garanties contractuelles distinctes** :

| | `GET /api/routes/{id}` | `GET /api/routes/{id}/projection` |
|---|---|---|
| **Données** | Intention pilote (waypoints, altitude) | Projection complète (distance, cap, ETE, fuel) |
| **Nature** | Stable, persistée | Éphémère, recalculable |
| **Dépendances** | Aucune | Avion, heure, vent |
| **Champs calculés sur RouteLeg** | `None` | Remplis |
| **`assumptions`** | Absent | Présent |
| **`generated_at`** | Absent | Présent |

### 4.3 Aircraft

Configuration d'un avion pour un utilisateur, incluant le centrogramme et les stations de chargement.

```
Firestore: /users/{user_id}/aircraft/{aircraft_id}
```

| Champ | Type | Description |
|-------|------|-------------|
| `id` | `str?` | ID Firestore |
| `registration` | `str` | Immatriculation (ex: `F-HBCT`, pattern `^[A-Z0-9-]+$`) |
| `aircraft_type` | `str` | Type (ex: `CT-LS`, `DR400-120`) |
| `empty_weight_kg` | `float` | Masse à vide (>0) |
| `empty_arm_m` | `float` | Bras de levier masse à vide (m) |
| `mtow_kg` | `float` | Masse max au décollage (>0) |
| `fuel_capacity_liters` | `float` | Capacité carburant (>0) |
| `cruise_speed_kt` | `int` | TAS croisière typique en kt (>0, ≤300) |
| `envelope` | `list[EnvelopePoint]` | Points du centrogramme (polygone W&B) |
| `loading_stations` | `list[LoadingStation]` | Stations de chargement |
| `fuel_profile` | `FuelProfile?` | Profil de consommation |
| `notes` | `str?` | Notes libres |

#### EnvelopePoint (centrogramme)

Les points forment un polygone fermé définissant l'enveloppe masse/centrage admissible.

| Champ | Type | Description |
|-------|------|-------------|
| `arm_m` | `float` | Bras de levier (m) |
| `weight_kg` | `float` | Poids (kg) |

**Exemple CT-LS** (d'après SDVFR) :

| arm_m | weight_kg | Position dans l'enveloppe |
|-------|-----------|--------------------------|
| 0.282 | 300.0 | Avant-gauche |
| 0.282 | 600.0 | Avant-droite |
| 0.478 | 600.0 | Arrière-droite |
| 0.478 | 300.0 | Arrière-gauche |

#### LoadingStation

Chaque station représente un point de chargement avec un bras de levier fixe.

| Champ | Type | Description |
|-------|------|-------------|
| `name` | `str` | Nom de la station (ex: `Equipage`, `Passager(s)`, `Bagages`, `Carburant`) |
| `station_type` | `StationType` | `crew`, `passenger`, `baggage`, `fuel` |
| `arm_m` | `float` | Bras de levier fixe (m) |
| `max_weight_kg` | `float` | Poids maximum admissible à cette station (>0) |

#### FuelProfile

| Champ | Type | Description |
|-------|------|-------------|
| `cruise_ff_lph` | `float` | Consommation croisière en L/h (>0) |
| `climb_ff_lph` | `float?` | Consommation montée en L/h |
| `descent_ff_lph` | `float?` | Consommation descente en L/h |
| `taxi_ff_lph` | `float?` | Consommation roulage en L/h |

#### Calcul du centrage

Le calcul du centre de gravité est effectué au service-layer (pas persisté) :

```
moment_total = empty_weight × empty_arm + Σ(station_load × station_arm)
weight_total = empty_weight + Σ(station_load)
cg = moment_total / weight_total
```

On vérifie ensuite que le point (cg, weight_total) est **à l'intérieur** du polygone `envelope`.

### 4.4 Flight et Track

Un vol est une instance spécifique d'une route à une date donnée.

```
Firestore: /users/{user_id}/flights/{flight_id}
```

#### Flight

| Champ | Type | Description |
|-------|------|-------------|
| `id` | `str?` | ID Firestore |
| `route_id` | `str` | Référence vers la Route |
| `aircraft_id` | `str?` | Référence vers l'Aircraft |
| `departure_datetime_utc` | `datetime` | Date/heure de départ prévue (UTC) |
| `status` | `FlightStatus` | `draft` → `planned` → `ready` → `completed` |
| `station_loads` | `list[StationLoad]` | Poids chargé à chaque station pour ce vol |
| `track` | `Track?` | Trace GPS post-vol |
| `weather_simulation_id` | `str?` | Snapshot météo figé à la collecte |
| `notam_snapshot_ref` | `str?` | Snapshot NOTAM figé à la collecte |
| `prep_sheet_ref` | `str?` | Fiche préparation générée (GCS) |
| `created_at` | `datetime` | Horodatage UTC |
| `updated_at` | `datetime?` | Dernière modification |

**Temporalité des données de vol** :

Un Flight combine trois catégories de données avec des garanties contractuelles différentes :

| Catégorie | Champs | Comportement |
|-----------|--------|-------------|
| **Intention** (persistée, stable) | `route_id`, `aircraft_id`, `departure_datetime_utc`, `status`, `station_loads` | Saisie pilote, stockée en Firestore, ne change pas sauf action explicite |
| **Snapshot** (persisté, figé) | `weather_simulation_id`, `notam_snapshot_ref`, `prep_sheet_ref` | Capture à un instant donné. **Jamais auto-rafraîchi.** Le pilote doit explicitement déclencher une nouvelle collecte pour mettre à jour |
| **Projection** (calculée, éphémère) | `RouteProjection` associée | Calculée à la demande via l'API. Dépend des hypothèses (avion, vent). Non persistée, non stable |

> **Règle** : la fiche de préparation reflète exactement les snapshots consultés par le pilote, pas des données recalculées silencieusement.

#### Track

Trace GPS réelle associée à un vol. Contient les heures de passage aux waypoints, calculées par un algorithme de « snap » (point de la trace GPX le plus proche de chaque waypoint).

| Champ | Type | Description |
|-------|------|-------------|
| `gpx_ref` | `str?` | Chemin GCS vers le fichier GPX brut |
| `source` | `TrackSource` | Origine de la trace (`gpx_file`, `flightaware`, `manual`) |
| `passage_times` | `list[WaypointPassageTime]` | Heures de passage snappées |
| `recorded_at` | `datetime?` | Horodatage d'import |
| `total_distance_nm` | `float?` | Distance totale parcourue |
| `total_time_minutes` | `float?` | Durée totale du vol |

#### WaypointPassageTime

| Champ | Type | Description |
|-------|------|-------------|
| `waypoint_id` | `str` | Référence UserWaypoint |
| `sequence_order` | `int` | Position dans la route |
| `passage_time_utc` | `datetime` | Heure de passage réelle |
| `latitude` | `float?` | Position GPS réelle au passage |
| `longitude` | `float?` | Position GPS réelle au passage |

#### StationLoad

Poids réel chargé à une station pour un vol donné. Référence une `LoadingStation` par son nom.

| Champ | Type | Description |
|-------|------|-------------|
| `station_name` | `str` | Référence vers `LoadingStation.name` de l'Aircraft |
| `weight_kg` | `float` | Poids effectivement chargé (≥0) |

#### Cycle de vie Flight + Track

```
1. Création du vol (DRAFT)
   └─→ route_id, departure_datetime, pilot inputs

2. Collecte données (PLANNED → READY)
   └─→ weather_simulation_id, notam_snapshot_ref

3. Vol effectué

4. Import trace GPX (COMPLETED)
   └─→ track.gpx_ref
   └─→ track.passage_times (snap waypoints ↔ trace)
   └─→ Enrichissement météo avec heures réelles
```

### 4.5 Weather — Simulation multi-modèle

Architecture de simulation météo permettant de comparer plusieurs modèles de prévision.

```
Firestore: /users/{user_id}/routes/{route_id}/simulations/{simulation_id}
```

#### Hiérarchie

```
WeatherSimulation
├── waypoints: [WaypointContext]        # Partagés entre modèles
│   ├── estimated_time_utc              # Heure de passage planifiée
│   ├── actual_time_utc                 # Heure réelle (post-vol, via Track)
│   └── observation: ObservationData?   # METAR réel (post-vol)
│
└── model_results: [ModelResult]        # Un par modèle interrogé
    ├── model: ForecastModel            # AROME_FRANCE, ARPEGE_EUROPE, etc.
    ├── model_run_time                  # Quand le modèle a tourné
    └── points: [ModelPoint]            # Un par waypoint, même ordre
        ├── forecast: ForecastData      # T°, vent, nuages, visi, précip
        └── vfr_index: VFRIndex         # GREEN / YELLOW / RED
```

#### WeatherSimulation

| Champ | Type | Description |
|-------|------|-------------|
| `id` | `str?` | ID du document |
| `route_id` | `str` | Route concernée |
| `simulated_at` | `datetime` | Quand la simulation a été lancée |
| `navigation_datetime` | `datetime` | Date/heure de vol prévue |
| `waypoints` | `list[WaypointContext]` | Waypoints de la route (contexte partagé) |
| `model_results` | `list[ModelResult]` | Résultats par modèle |

#### WaypointContext

| Champ | Type | Description |
|-------|------|-------------|
| `waypoint_name` | `str` | Nom du waypoint |
| `waypoint_index` | `int` | Index dans la route (0-based) |
| `latitude`, `longitude` | `float` | Coordonnées |
| `icao` | `str?` | Code OACI si aérodrome |
| `estimated_time_utc` | `datetime` | Heure de passage planifiée |
| `actual_time_utc` | `datetime?` | Heure réelle (post-vol, depuis Track) |
| `observation` | `ObservationData?` | METAR réel à l'heure du passage |

#### ForecastData

Données de prévision pour un point/instant donné, issues d'un modèle.

| Champ | Type | Description |
|-------|------|-------------|
| `temperature_2m` | `float?` | Température à 2m (°C) |
| `dewpoint_2m` | `float?` | Point de rosée à 2m (°C) |
| `temperature_levels` | `dict[int, float]` | Température par niveau de pression {hPa: °C} |
| `wind_speed_10m` | `float?` | Vent à 10m (kt) |
| `wind_direction_10m` | `int?` | Direction du vent à 10m (°) |
| `wind_gusts_10m` | `float?` | Rafales à 10m (kt) |
| `wind_speed_levels` | `dict[int, float]` | Vent par niveau de pression {hPa: kt} |
| `wind_direction_levels` | `dict[int, int]` | Direction vent par niveau {hPa: °} |
| `cloud_cover` | `int?` | Couverture nuageuse totale (%) |
| `cloud_cover_low` | `int?` | Nébulosité basse (%) |
| `cloud_cover_mid` | `int?` | Nébulosité moyenne (%) |
| `cloud_cover_high` | `int?` | Nébulosité haute (%) |
| `visibility` | `int?` | Visibilité (m) |
| `precipitation` | `float?` | Précipitations (mm) |
| `pressure_msl` | `float?` | Pression au niveau de la mer (hPa) |
| `weather_code` | `int?` | Code météo WMO |

**Niveaux de pression** :

| Niveau | Altitude approx. | Usage VFR |
|--------|-------------------|-----------|
| 1000 hPa | ~300 ft AMSL | Décollage / atterrissage |
| 925 hPa | ~2 500 ft AMSL | Croisière basse |
| 850 hPa | ~5 000 ft AMSL | Croisière moyenne |
| 700 hPa | ~10 000 ft AMSL | Croisière haute |

> **Règle** : utiliser le vent à l'**altitude de croisière planifiée** du leg, pas le vent de surface.

**Sérialisation Firestore** : les clés `dict[int, float]` sont sérialisées en strings par `mode="json"` (ex: `{"1000": 12.5}`). Pydantic v2 coerce automatiquement les clés string vers `int` à la désérialisation.

#### ObservationData (METAR)

| Champ | Type | Description |
|-------|------|-------------|
| `observation_time` | `datetime` | Heure de l'observation |
| `icao` | `str` | Code OACI de la station |
| `wind_direction` | `int?` | Direction (°) |
| `wind_speed` | `float?` | Vitesse (kt) |
| `wind_gust` | `float?` | Rafales (kt) |
| `temperature` | `float?` | Température (°C) |
| `dewpoint` | `float?` | Point de rosée (°C) |
| `visibility` | `int?` | Visibilité (m) |
| `ceiling` | `int?` | Plafond (ft AGL, plus bas BKN/OVC) |
| `clouds` | `list[CloudLayer]` | Couches nuageuses |
| `flight_category` | `str?` | `VFR`, `MVFR`, `IFR`, `LIFR` |
| `altimeter` | `float?` | QNH (hPa) |
| `raw_metar` | `str?` | METAR brut |

#### VFRIndex

| Champ | Type | Description |
|-------|------|-------------|
| `status` | `VFRStatus` | `green`, `yellow`, `red` |
| `visibility_ok` | `bool` | Visibilité conforme VMC |
| `ceiling_ok` | `bool` | Plafond conforme VMC |
| `wind_ok` | `bool` | Vent dans les limites |
| `details` | `str` | Explication lisible |

### 4.6 Airspace — Analyse d'intersection

Résultats de l'analyse des espaces aériens traversés par une route.

#### AirspaceIntersection

| Champ | Type | Description |
|-------|------|-------------|
| `identifier` | `str` | Nom de l'espace (ex: `TMA PARIS 1`) |
| `airspace_type` | `AirspaceType` | Type (`TMA`, `CTR`, `SIV`, `D`, `R`, `P`, ...) |
| `airspace_class` | `str?` | Classe OACI A-G |
| `lower_limit_ft` | `int` | Limite inférieure (ft AMSL) |
| `upper_limit_ft` | `int` | Limite supérieure (ft AMSL) |
| `intersection_type` | `IntersectionType` | `crosses`, `inside`, `corridor` |
| `color_html` | `str?` | Couleur HTML pour affichage |
| `services` | `list[ServiceInfo]` | Services ATC associés |

#### LegAirspaces

| Champ | Type | Description |
|-------|------|-------------|
| `from_waypoint`, `to_waypoint` | `str` | Noms des waypoints du leg |
| `from_seq`, `to_seq` | `int` | Numéros d'ordre |
| `planned_altitude_ft` | `int` | Altitude de croisière du leg |
| `route_airspaces` | `list[AirspaceIntersection]` | Espaces traversés directement |
| `corridor_airspaces` | `list[AirspaceIntersection]` | Espaces dans le couloir latéral |

#### RouteAirspaceAnalysis

| Champ | Type | Description |
|-------|------|-------------|
| `route_id` | `str` | Route analysée |
| `legs` | `list[LegAirspaces]` | Analyse par leg |
| `analyzed_at` | `str?` | Horodatage ISO 8601 |

### 4.7 Aerodrome — Données de référence

Modèle en **lecture seule**, alimenté par le pipeline ETL XML SIA. N'est pas stocké par utilisateur dans Firestore — provient des bases de référence.

#### AerodromeInfo

| Champ | Type | Description |
|-------|------|-------------|
| `icao` | `str` | Code OACI (clé primaire) |
| `name` | `str` | Nom complet |
| `status` | `AerodromeStatus?` | `CAP`, `restricted`, `military`, `closed` |
| `vfr` | `bool` | Ouvert au VFR |
| `private` | `bool` | Usage privé |
| `latitude`, `longitude` | `float` | Coordonnées ARP |
| `elevation_ft` | `int?` | Altitude de référence (ft AMSL) |
| `mag_variation` | `float?` | Déclinaison magnétique (°) |
| `ref_temperature` | `float?` | Température de référence (°C) |
| `ats_hours` | `str?` | Horaires services ATS |
| `fuel_available` | `str?` | Carburant disponible |
| `met_centre` | `str?` | Centre météo local |
| `runways` | `list[Runway]` | Pistes |
| `services` | `list[AerodromeService]` | Services ATC/FIS |
| `airac_cycle` | `str?` | Cycle AIRAC source |

---

## 5. Autorité des données et mapping Firestore

### 5.0 Principe d'autorité

Chaque donnée a une **source de vérité** unique :

| Source | Rôle | Données |
|--------|------|---------|
| **Firestore** | Source de vérité, lecture-écriture | Données utilisateur : waypoints, routes, aircraft, flights, weather simulations |
| **SQLite / SpatiaLite** | Référence partagée, lecture seule | Données AIRAC : aérodromes, espaces aériens (mis à jour par cycle, jamais par l'utilisateur) |
| **Cloud Storage** | Stockage binaire, référencé par GCS path | Fichiers : GPX, KML, fiches préparation PDF, snapshots NOTAM |
| **Runtime** | Calculé à la volée, jamais persisté | `RouteProjection`, champs calculés de `RouteLeg`, vérification centrage, carburant requis |

### 5.1 Mapping Firestore

```
/users/{user_id}/
├── profile                             # (à définir)
├── aircraft/{aircraft_id}              # → Aircraft
├── user_waypoints/{waypoint_id}        # → UserWaypoint (id = MD5)
├── routes/{route_id}                   # → Route
│   └── simulations/{simulation_id}     # → WeatherSimulation
└── flights/{flight_id}                 # → Flight (inclut Track en embedded)
```

### 5.2 Données de référence (partagées, read-only)

| Donnée | Stockage | Format |
|--------|----------|--------|
| Espaces aériens | `gs://skyweb-reference/airac/{cycle}/skypath.db` | SpatiaLite |
| Aérodromes | `gs://skyweb-reference/airac/{cycle}/skypath.db` | SpatiaLite |
| Notes VAC | Firestore `/community/vac_notes/{icao}` | Document |
| Base TDP | Firestore `/community/tdp_database/{icao}` | Document |

### 5.3 Données utilisateur (privées, read-write)

| Donnée | Stockage | Contrat |
|--------|----------|---------|
| Waypoints réutilisables | Firestore `user_waypoints/` | `UserWaypoint` |
| Routes | Firestore `routes/` | `Route` (refs vers waypoints) |
| Config avions | Firestore `aircraft/` | `Aircraft` |
| Vols | Firestore `flights/` | `Flight` (Track embedded) |
| Simulations météo | Firestore `routes/{id}/simulations/` | `WeatherSimulation` |
| Fichiers KML/GPX | Cloud Storage `gs://skyweb-users/{user_id}/` | Références dans les documents |

---

## 6. Conventions contractuelles

### 6.1 Unités

Toutes les valeurs exposées dans les contrats et l'API suivent les conventions aéronautiques.

| Grandeur | Unité | Suffixe champ | Note |
|----------|-------|---------------|------|
| Distance | **NM** | `_nm` | Convention aéronautique |
| Vitesse | **kt** | `_kt` | TAS, GS, vent |
| Altitude | **ft AMSL** | `_ft` | |
| Masse | **kg** | `_kg` | |
| Bras de levier | **m** | `_m` | Centrage (centrogramme) |
| Carburant | **litres** | `_liters` | |
| Cap / angles | **degrés** | `_deg` | [0, 360[ |
| Pression | **hPa** | | |
| Température | **°C** | | |
| Visibilité | **m** | | Convention METAR |
| Coordonnées | **degrés décimaux WGS84** | `latitude` / `longitude` | |
| Datetimes | **UTC** | `_utc` | ISO 8601 sérialisé |

> **Règle** : les services internes (SpatiaLite, Open-Meteo) peuvent utiliser des unités métriques (km, m/s) mais **doivent convertir** avant de renvoyer au layer API/contrats.

### 6.2 Enums

Toutes les enums sont des `str, Enum` avec des valeurs **minuscules stables** (ex: `"draft"`, `"planned"`, `"aerodrome"`). Exceptions : `CloudCover` et `AirspaceType` utilisent des codes aéronautiques standards en majuscules (ex: `"BKN"`, `"TMA"`).

Les valeurs d'enum constituent un contrat d'API — elles ne doivent jamais être renommées sans migration.

### 6.3 Datetimes

- Toujours **UTC** dans les modèles et l'API.
- Sérialisés en **ISO 8601** par `mode="json"` (suffixe `Z` ou `+00:00`).
- Les champs datetime portent le suffixe `_utc` quand le nom ne l'implique pas déjà (ex: `departure_datetime_utc`, `passage_time_utc`).

### 6.4 Identifiants

- Les ID Firestore sont attribués par Firestore (`id: str | None`).
- Les ID UserWaypoint sont **déterministes** : `MD5(name:lat:lon)[:16]`.
- Les références entre documents utilisent des ID string simples (`route_id`, `aircraft_id`).

---

## 7. Alignement avec SkyPath

Les contrats SkyWeb sont structurellement compatibles avec SkyPath mais indépendants :

| SkyPath | SkyWeb | Différences |
|---------|--------|-------------|
| `Point` | `Waypoint` / `UserWaypoint` | `Waypoint` = éphémère, `UserWaypoint` = persisté ; ajoute `location_type`, `id` déterministe ; supprime `visibility` |
| `CorrectedWaypoint` | — | Correction = service-layer, pas persisté |
| `RouteSegment` | `RouteLeg` (persisté + champs calculés optionnels) | SkyPath mélangeait tout dans un seul objet ; SkyWeb sépare intention (persistée) et calcul (runtime) dans le même modèle via champs optionnels |
| `Airspace` | `AirspaceIntersection` | Ajoute `services` ; `class_` renommé `airspace_class` |
| `SegmentAirspaces` | `LegAirspaces` | Renommé pour cohérence vocabulaire « leg » ; ajoute `from_seq`/`to_seq` |
| `ElevationResult` | — | Transitoire, usage service-layer uniquement |

---

*Document créé le : 2026-02-02*
*Version : 0.5 — RouteProjection formalisé, responsabilité des modèles, invariant persistance waypoints, temporalité Flight, conventions contractuelles*
