# Conception Technique - Automatisation Préparation Vol VFR

## 1. Périmètre fonctionnel

SkyWeb automatise la préparation d'un vol VFR de bout en bout : import de route, analyse des espaces aériens, collecte météo, NOTAM, et génération de la fiche de préparation.

### 1.1 Capacités

| Capacité | Statut |
|----------|--------|
| Import KML SD VFR | ✅ |
| Modèle Route / Waypoint / RouteLeg / FlightPlan | ✅ |
| Analyse espaces aériens 3D (zones traversées, fréquences, services ATC) | ✅ |
| Données aérodromes (XML SIA) | ✅ |
| Météo forecast (Open-Meteo) | ✅ |
| Météo observations METAR (NOAA) | ✅ |
| Conversions ISA (pression/altitude) | ✅ |
| Évaluation sécurité VFR | ✅ |
| Pipeline ETL XML SIA | ✅ |
| Client METAR/TAF Météo-France | ❌ À développer |
| NOTAM (Eurocontrol/ICAO) | ❌ À développer |
| SUP AIP | ❌ À développer |
| Génération fiche préparation 4120 | ❌ À développer |
| Export FPL Garmin | ❌ À développer |
| Données VAC capitalisées (CRUD) | ❌ À développer |
| API Administration AIRAC | ❌ À développer |
| Authentification utilisateur | ❌ À développer |

---

## 2. Modèle de données

### 2.1 Modèles navigation

```python
class WaypointType(Enum):
    NORMAL = "normal"
    AD = "aerodrome"

class Waypoint:
    id: str                    # MD5(name:lat:lon)[:16]
    name: str
    lat: float                 # WGS84
    lon: float                 # WGS84
    waypoint_type: WaypointType

class RouteWaypoint:
    waypoint: Waypoint
    sequence_order: int        # Ordre 1..N

class RouteLeg:                # Altitude de croisière par tronçon (voir DESIGN-import-route-sdvfr.md §3.5)
    from_sequence_order: int
    to_sequence_order: int     # = from + 1
    planned_altitude_ft: int

class Route:
    id: int | None
    name: str
    waypoints: list[RouteWaypoint]
    legs: list[RouteLeg]
    created_at: datetime

class FlightPlan:
    id: int | None
    route: Route
    departure_datetime: datetime
    cruise_speed_kt: int
    timings: list[WaypointTiming]
```

### 2.2 Modèles aérodrome & espaces aériens

```python
@dataclass
class AerodromeData:
    icao: str
    name: str
    latitude: float
    longitude: float
    elevation_ft: Optional[int]
    status: Optional[str]
    international: bool
    ifr: bool
    vfr: bool

@dataclass
class FrequencyInfo:
    frequence: str             # "119.250"
    espacement: Optional[str]  # "25", "8.33"
    hor_code: Optional[str]
    hor_txt: Optional[str]     # "H24", "HJ"

@dataclass
class ServiceInfo:
    indic_lieu: str            # "PARIS"
    indic_service: str         # "TWR", "APP", "AFIS"
    langue: Optional[str]
    frequencies: List[FrequencyInfo]

@dataclass
class AirspaceIntersection:
    identifier: str            # "TMA PARIS"
    type: str                  # TMA, CTR, SIV, R, D, P
    airspace_class: Optional[str]  # A-G
    lower_limit_ft: int
    upper_limit_ft: int
    intersection_type: str     # CROSSES, INSIDE, CORRIDOR
    is_intercepted: bool
    services: List[ServiceInfo]
```

### 2.3 Modèles météo

```python
@dataclass
class ForecastPoint:
    forecast_time: datetime
    valid_time: datetime
    latitude: float
    longitude: float
    temperature_2m: Optional[float]       # °C
    wind_speed_10m: Optional[float]       # kt
    wind_direction_10m: Optional[int]     # °
    wind_gusts_10m: Optional[float]       # kt
    cloud_cover: Optional[int]            # %
    visibility: Optional[int]             # m
    pressure_msl: Optional[float]         # hPa
    precipitation: Optional[float]        # mm

@dataclass
class ObservationPoint:
    observation_time: datetime
    icao: str
    temperature: Optional[float]          # °C
    wind_direction: Optional[int]         # °
    wind_speed: Optional[float]           # kt
    visibility: Optional[int]             # m
    altimeter: Optional[float]            # hPa (QNH)
    ceiling: Optional[int]               # ft
    flight_category: Optional[str]        # VFR/MVFR/IFR/LIFR
    raw_metar: Optional[str]
```

### 2.4 Modèles spécifiques préparation vol

```python
# --- Données VAC capitalisées ---
@dataclass
class VacNotes:
    icao: str
    # Éléments non disponibles dans XML SIA
    circuit_direction: Optional[str]       # L/R (si pas dans TDP DB)
    circuit_altitude_ft: Optional[int]     # (si pas dans TDP DB)
    piste_preferentielle: Optional[str]
    pente_papi: Optional[float]
    reperes_sol: Optional[str]             # Texte libre
    obstacles: Optional[str]
    perimetres_urbanises: Optional[str]
    aire_signaux: Optional[str]
    activites_speciales: Optional[str]     # Para, voltige...
    points_compte_rendu: Optional[str]
    itineraires_arrivee: Optional[str]
    itineraires_depart: Optional[str]
    procedure_panne_radio: Optional[str]
    integration_circuit: Optional[str]
    horaires_avitaillement: Optional[str]
    updated_at: datetime
    updated_by: str                        # user_id

# --- Contexte vol (assemblage) ---
@dataclass
class FlightContext:
    """Toutes les données collectées pour un vol"""
    flight_id: str
    route: Route
    flight_plan: FlightPlan
    # Par segment
    segment_airspaces: list[SegmentAirspaces]
    # Par aérodrome (départ, arrivée, dégagements)
    aerodromes: dict[str, AerodromeData]
    vac_notes: dict[str, VacNotes]
    # Météo (contextuel au vol)
    weather_points: list[ForecastPoint]
    metar_departure: Optional[ObservationPoint]
    metar_arrival: Optional[ObservationPoint]
    # NOTAM (contextuel au vol)
    notams: list[dict]                    # Structure TBD
    # Metadata
    created_at: datetime
    status: str                           # draft/ready/completed

# --- NOTAM (structure à valider avec Eurocontrol) ---
@dataclass
class Notam:
    id: str                               # NOTAM series + number
    icao: Optional[str]
    fir: Optional[str]
    q_code: Optional[str]
    valid_from: datetime
    valid_to: datetime
    text: str
    raw: str
```

### 2.5 Conventions d'unités

| Grandeur | Unité |
|----------|-------|
| Distance calculs | **km** |
| Distance aéro | **NM** |
| Vitesse | **kt** |
| Altitude | **ft AMSL** |
| Vent | **kt** (⚠️ Open-Meteo fournit km/h, Météo-France m/s → conversion requise) |
| Pression | **hPa** |
| Température | **°C** |
| Visibilité | **m** |

---

## 3. Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | **Python 3.11+** |
| Framework API | **FastAPI** |
| Base référence aéro | **SQLite + SpatiaLite** |
| Base utilisateur | **Firestore** |
| Déploiement | **GCP Cloud Run** |
| CI/CD | **Cloud Build** |
| Storage | **GCP Cloud Storage** |
| Auth | **Firebase Auth** |
| Météo | **Open-Meteo + NOAA AWC** |

---

## 4. Architecture API

### 4.1 Endpoints utilisateur

#### Route

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/route/upload` | POST | Upload KML SD VFR |
| `/api/route/{id}` | GET | Récupérer une route |
| `/api/route/{id}/segments` | GET | Segments avec distances, caps |
| `/api/route/{id}/airspaces` | GET | Zones traversées par segment |
| `/api/route/{id}/frequencies` | GET | Fréquences le long de la route |

#### Aérodrome

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/aerodrome/{icao}` | GET | Infos AD (XML SIA) |
| `/api/aerodrome/{icao}/runways` | GET | Pistes, TODA, LDA, déclivité |
| `/api/aerodrome/{icao}/frequencies` | GET | Fréquences AD |
| `/api/aerodrome/{icao}/vac-notes` | GET | Notes VAC capitalisées |
| `/api/aerodrome/{icao}/vac-notes` | PUT | Saisie/MAJ notes VAC |

#### Météo

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/weather/route/{route_id}` | GET | Météo complète le long de la route (vents, temp, nébulosité, visi, METAR/TAF aux AD) |
| `/api/weather/aerodrome/{icao}` | GET | METAR + TAF + forecast pour un AD |
| `/api/weather/winds-aloft` | GET | Vent à position+altitude donnée |

#### Vol

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/flight` | POST | Créer préparation vol |
| `/api/flight/{id}` | GET | Récupérer contexte vol complet |
| `/api/flight/{id}/collect` | POST | Lancer collecte données (météo, NOTAM) |
| `/api/flight/{id}/prep-sheet` | GET | Générer fiche préparation 4120 |
| `/api/flight/{id}/export/fpl` | GET | Export FPL Garmin |

#### NOTAM

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/notam/route/{route_id}` | GET | NOTAM le long de la route |
| `/api/notam/aerodrome/{icao}` | GET | NOTAM pour un AD |

### 4.2 Endpoints administration

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/admin/airac/upload` | POST | Upload nouveau XML SIA |
| `/admin/airac/activate` | POST | Activer un cycle AIRAC |
| `/admin/airac/list` | GET | Lister cycles disponibles |
| `/admin/airac/current` | GET | Cycle actif + metadata |
| `/admin/community/vac-notes` | PUT | MAJ notes VAC (bulk) |
| `/admin/community/tdp` | PUT | MAJ base TDP |
| `/admin/community/export` | GET | Export données communauté |

### 4.3 Endpoints communs

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Health check (non authentifié) |
| `/api/user/profile` | GET/PUT | Profil utilisateur |
| `/api/user/aircraft` | GET/POST/PUT | Config avions |

---

## 5. Schéma de données persisté

### 5.1 Base navigation (SQLite `navlog.db`)

```
waypoints, routes, route_waypoints, flight_plans, waypoint_timings,
route_airspaces, airspace_services, airspace_frequencies
```

### 5.2 Base aéronautique (SpatiaLite `skypath.db`)

#### Champs XML SIA à capturer

Le schéma aérodrome actuel ne capture pas tous les champs utiles à la préparation vol. Le XSD définit des champs supplémentaires :

| Champ XML SIA | Capturé | Usage préparation vol |
|---------------|-------------------|----------------------|
| `HorAtsTxt` | ❌ | Horaires services ATS |
| `HorAtsCode` | ❌ | Horaires ATS (codé) |
| `HorAvtTxt` | ❌ | Horaires avitaillement |
| `SvcEscaleFuel` | ❌ | Carburant disponible |
| `SvcEscaleFuelRem` | ❌ | Remarques carburant |
| `MetCentre` | ❌ | Centre météo local |
| `MetBriefing` | ❌ | Contact briefing météo |

**Action** : Étendre le schéma `Ad` existant ou créer une table complémentaire dédiée.

#### Modèle AD cible pour SkyWeb

Table `aerodrome` : vue consolidée pour la préparation vol, alimentée depuis XML SIA.

```sql
CREATE TABLE aerodrome (
    -- Identification
    icao            TEXT PRIMARY KEY,     -- Ad.AdCode
    name            TEXT NOT NULL,        -- Ad.AdNomComplet
    status          TEXT,                 -- Ad.AdStatut (CAP/Restreint)
    vfr             TEXT,                 -- Ad.TfcVfr
    private         TEXT,                 -- Ad.TfcPrive

    -- Localisation
    latitude        REAL NOT NULL,        -- Ad.ArpLat
    longitude       REAL NOT NULL,        -- Ad.ArpLong
    elevation_ft    INTEGER,              -- Ad.AdRefAltFt
    mag_variation   REAL,                 -- Ad.AdMagVar
    ref_temperature REAL,                 -- Ad.AdRefTemp

    -- Horaires & Services
    ats_hours       TEXT,                 -- Ad.HorAtsTxt (nouveau)
    fuel_available  TEXT,                 -- Ad.SvcEscaleFuel (nouveau)
    fuel_remarks    TEXT,                 -- Ad.SvcEscaleFuelRem (nouveau)
    met_centre      TEXT,                 -- Ad.MetCentre (nouveau)
    met_briefing    TEXT,                 -- Ad.MetBriefing (nouveau)

    -- Sécurité
    sslia_category  INTEGER,              -- Ad.SsliaCat

    -- Contact
    management      TEXT,                 -- Ad.AdGestion
    phone           TEXT,                 -- Ad.AdTel
    remarks         TEXT,                 -- Ad.AdRem

    -- Metadata chargement
    airac_cycle     TEXT NOT NULL,        -- Cycle AIRAC source
    loaded_at       TEXT NOT NULL         -- ISO 8601
);

CREATE TABLE aerodrome_runway (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    icao            TEXT NOT NULL REFERENCES aerodrome(icao),
    designator      TEXT NOT NULL,        -- Rwy.Rwy ("08/26")
    length_m        INTEGER,              -- Rwy.Longueur
    width_m         INTEGER,              -- Rwy.Largeur
    is_main         TEXT,                 -- Rwy.Principale
    surface         TEXT,                 -- Rwy.Revetement
    pcn             TEXT,                 -- Rwy.Resistance
    orientation_geo REAL,                 -- Rwy.OrientationGeo
    lat_thr1        REAL,                 -- Rwy.LatThr1
    lon_thr1        REAL,                 -- Rwy.LongThr1
    alt_ft_thr1     INTEGER,              -- Rwy.AltFtThr1
    lat_thr2        REAL,                 -- Rwy.LatThr2
    lon_thr2        REAL,                 -- Rwy.LongThr2
    alt_ft_thr2     INTEGER,              -- Rwy.AltFtThr2
    lda1_m          INTEGER,              -- Rwy.Lda1
    lda2_m          INTEGER,              -- Rwy.Lda2
    UNIQUE(icao, designator)
);

CREATE TABLE aerodrome_service (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    icao            TEXT NOT NULL REFERENCES aerodrome(icao),
    service_type    TEXT NOT NULL,        -- Service.Service (TWR, AFIS, APP...)
    callsign        TEXT,                 -- Service.IndicLieu
    indicator       TEXT,                 -- Service.IndicService
    language        TEXT,                 -- Service.Langue
    hours_code      TEXT,                 -- Service.HorCode
    hours_text      TEXT,                 -- Service.HorTxt
    remarks         TEXT                  -- Service.Remarque
);

CREATE TABLE aerodrome_frequency (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      INTEGER NOT NULL REFERENCES aerodrome_service(id),
    frequency_mhz   REAL NOT NULL,       -- Frequence.Frequence
    spacing         TEXT,                 -- Frequence.Espacement
    hours_code      TEXT,                 -- Frequence.HorCode
    hours_text      TEXT,                 -- Frequence.HorTxt
    sector          TEXT,                 -- Frequence.SecteurSituation
    remarks         TEXT                  -- Frequence.Remarque
);

-- Index pour requêtes fréquentes
CREATE INDEX idx_runway_icao ON aerodrome_runway(icao);
CREATE INDEX idx_service_icao ON aerodrome_service(icao);
CREATE INDEX idx_frequency_service ON aerodrome_frequency(service_id);
```

#### Mécanisme de chargement XML SIA → table aerodrome

```
XML SIA (data.gouv.fr)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Pipeline de chargement (admin ou scheduled)          │
│                                                      │
│ 1. EXTRACT : Parser XML SIA                          │
│    - Parser Ad + Rwy + Service + Frequence           │
│    - Extrait Ad + Rwy + Service + Frequence          │
│    - Ajoute extraction champs manquants              │
│      (HorAtsTxt, SvcEscaleFuel, MetCentre...)        │
│                                                      │
│ 2. TRANSFORM : Mapper vers modèle cible              │
│    - Ad.AdCode → aerodrome.icao                      │
│    - Filtrer champs utiles préparation vol            │
│    - Normaliser types (texte→enum si pertinent)      │
│    - Ajouter metadata (airac_cycle, loaded_at)       │
│                                                      │
│ 3. LOAD : Charger dans base SkyWeb                   │
│    - REPLACE INTO aerodrome (idempotent)             │
│    - CASCADE suppression pistes/services/freq        │
│    - Vérification intégrité post-chargement          │
│    - Log : nb AD chargés, erreurs, delta vs cycle N-1│
└─────────────────────────────────────────────────────┘
```

**Deux options d'implémentation** :

| Option | Description | Avantage | Inconvénient |
|--------|-------------|----------|--------------|
| **A. Étendre le schéma existant** | Ajouter colonnes manquantes au schéma Ad | Une seule base, pipeline existant | Modifie le schéma existant |
| **B. Base séparée** | Nouvelle base `aerodrome.db` avec schéma dédié | Indépendant, schéma optimisé | Duplication extraction |

**Recommandation** : Option B (base séparée) pour la préparation vol, car :
- Le schéma est orienté "consommation" (noms lisibles, clé OACI) vs schéma existant orienté "stockage brut" (clé pk/lk)
- On peut ajouter des champs calculés (distances, circuit de piste)
- Pas d'impact sur la base existante

### 5.3 Firestore

```
/users/{user_id}/
├── profile {name, email, default_aircraft, base_icao}
├── aircraft/{id} {type, registration, empty_weight, fuel_arm, ...}
├── routes/{id} {name, waypoints_summary, kml_ref, created_at}
└── flights/{id}
    ├── route_ref, date, status
    ├── weather_snapshot {points[], metar_dep, metar_arr}
    ├── notam_snapshot {notams[], collected_at}
    └── prep_sheet_ref → Cloud Storage

/community/
├── vac_notes/{icao} {VacNotes fields, updated_at, updated_by}
└── tdp_database/{icao} {direction, altitude_ft, source}

/admin/
└── airac_cycles/{cycle_id} {status, activated_at, metadata}
```

---

## 6. Architecture des modules

```
                        SkyWeb API (FastAPI)
                              │
        ┌─────────────┬───────┼───────┬──────────────┐
        │             │       │       │              │
  ┌─────┴─────┐ ┌─────┴────┐ │ ┌─────┴─────┐ ┌─────┴─────┐
  │   Route   │ │Aérodrome │ │ │   NOTAM   │ │   Admin   │
  │  Service  │ │ Service  │ │ │  Service  │ │  Service  │
  └─────┬─────┘ └─────┬────┘ │ └───────────┘ └───────────┘
        │             │      │
        │        ┌────┘  ┌───┴──────┐
        │        │       │ Weather  │
        │        │       │ Service  │
        │        │       └──────────┘
        │        │
  ┌─────┴────────┴─────┐
  │   Base aéronautique │
  │ skypath.db + aero.db│
  └────────────────────┘
```

---

*Document créé le : 2026-01-21*
*Version : 0.4 - Module météo unifié, suppression références stack interne*
