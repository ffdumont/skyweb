# Conception Technique - Module Weather

## 1. Vue d'ensemble

Le module Weather produit des **simulations météo multi-modèles** sur les points clés d'une route VFR. Chaque simulation est déclenchée sur ordre par l'utilisateur, interroge plusieurs modèles de prévision, et génère un **météogramme par modèle** (température, vent en altitude, couverture nuageuse) avec un indice VFR par point. Les météogrammes peuvent être affichés individuellement ou comparés.

Les observations réelles peuvent être collectées a posteriori une fois le vol effectué, à partir des heures de passage réelles extraites du GPX de navigation.

### 1.1 Trois dates structurantes

Chaque simulation météo est définie par trois repères temporels :

| Date | Description | Source |
|------|-------------|--------|
| **Date de simulation** (`simulated_at`) | Instant où la simulation est lancée. Détermine le run de modèle utilisé (le plus récent disponible à cet instant). | Horodatage automatique |
| **Date de navigation** (`navigation_datetime`) | Date et heure prévues pour le vol. Peut être modifiée d'une simulation à l'autre pour explorer différents créneaux. | Saisie utilisateur (issue de la route) |
| **Date du vol réel** (`actual_datetime`) | Heures de passage réelles aux points de la route, capturées depuis le journal de navigation / GPX. | Import GPX post-vol |

```
Simulation 1 (02/02 10:00)              Simulation 2 (04/02 08:00)
├─ simulated_at: 02/02 10:00            ├─ simulated_at: 04/02 08:00
├─ navigation_datetime: 05/02 09:00     ├─ navigation_datetime: 05/02 14:00  ← créneau modifié
├─ modèles:                              ├─ modèles:
│  ├─ ARPEGE Europe (run 02/02 00Z)     │  ├─ AROME France (run 04/02 00Z)
│  └─ ARPEGE World  (run 02/02 00Z)     │  ├─ AROME HD     (run 04/02 00Z)
│                                        │  └─ ARPEGE Europe (run 04/02 00Z)
└─ résultat: 2 météogrammes             └─ résultat: 3 météogrammes

                                         Vol réel (05/02)
                                         ├─ actual_datetime par point (GPX)
                                         └─ observations METAR (indépendantes du modèle)
```

### 1.2 Points météo

La simulation porte sur les **points clés de la route**, pas sur des stations météo :

- Point de départ (aérodrome)
- Points tournants
- Point d'arrivée (aérodrome)

Pour les points qui correspondent à un aérodrome, les observations METAR/TAF sont collectées en complément des prévisions.

---

## 2. Modèle de données

### 2.1 Simulation météo

La simulation sépare ce qui est partagé (waypoints, observations = la réalité) de ce qui dépend du modèle (prévisions, indice VFR).

```python
@dataclass
class WeatherSimulation:
    """Résultat d'une simulation multi-modèles sur une route."""
    id: str                             # Identifiant unique
    route_id: str
    simulated_at: datetime              # Quand la simulation a été lancée (UTC)
    navigation_datetime: datetime       # Date/heure prévue du vol (UTC)

    # Points de la route (partagés entre modèles)
    waypoints: list[WaypointContext]

    # Un météogramme par modèle interrogé
    model_results: list[ModelResult]

@dataclass
class WaypointContext:
    """Point clé de la route — données partagées entre modèles."""
    waypoint_name: str
    waypoint_index: int                 # Ordre dans la route
    latitude: float
    longitude: float
    icao: Optional[str]                 # Si aérodrome

    # Heure de passage prévue à ce point
    estimated_time: datetime            # Calculée depuis le plan de vol

    # Post-vol (remplis a posteriori)
    actual_time: Optional[datetime]     # Heure de passage réelle (GPX)
    observation: Optional[ObservationData]  # METAR le plus proche de actual_time

@dataclass
class ModelResult:
    """Météogramme pour un modèle donné."""
    model: ForecastModel
    model_run_time: datetime            # Run du modèle (UTC)
    points: list[ModelPoint]            # Un par waypoint, même ordre

@dataclass
class ModelPoint:
    """Prévision et indice VFR pour un point, selon un modèle."""
    waypoint_index: int                 # Référence vers WaypointContext
    forecast: ForecastData
    vfr_index: VFRIndex
```

### 2.2 Prévisions (forecast)

```python
class ForecastModel(Enum):
    AROME_FRANCE = "arome_france"       # 1.5 km, horaire, 48h
    AROME_HD = "arome_hd"              # 1.5 km, 15 min, 48h
    ARPEGE_EUROPE = "arpege_europe"    # 10 km, horaire, 102h
    ARPEGE_WORLD = "arpege_world"      # 25 km, 3h, 96h

@dataclass
class ForecastData:
    """Données de prévision pour un point à un instant donné."""

    # Température
    temperature_2m: Optional[float]     # °C (au sol)
    dewpoint_2m: Optional[float]        # °C
    temperature_levels: dict[int, float]  # {hPa: °C} ex: {1000: 12.5, 925: 8.1, 850: 3.2}

    # Vent (en kt)
    wind_speed_10m: Optional[float]     # kt (au sol)
    wind_direction_10m: Optional[int]   # ° (au sol)
    wind_gusts_10m: Optional[float]     # kt
    wind_speed_levels: dict[int, float]     # {hPa: kt}
    wind_direction_levels: dict[int, int]   # {hPa: °}

    # Nébulosité
    cloud_cover: Optional[int]          # % total
    cloud_cover_low: Optional[int]      # % nuages bas
    cloud_cover_mid: Optional[int]      # % nuages moyens
    cloud_cover_high: Optional[int]     # % nuages hauts

    # Visibilité & précipitations
    visibility: Optional[int]           # m
    precipitation: Optional[float]      # mm
    pressure_msl: Optional[float]       # hPa

    # Code météo WMO
    weather_code: Optional[int]
```

### 2.3 Observations

```python
@dataclass
class ObservationData:
    """Observation météo réelle (METAR + SYNOP complémentaire)."""
    observation_time: datetime
    icao: str

    # Vent (kt)
    wind_direction: Optional[int]       # ° (None si calme)
    wind_speed: Optional[float]         # kt
    wind_gust: Optional[float]          # kt

    # Température
    temperature: Optional[float]        # °C
    dewpoint: Optional[float]           # °C

    # Visibilité & nuages
    visibility: Optional[int]           # m
    ceiling: Optional[int]              # ft (base BKN/OVC la plus basse)
    clouds: list[CloudLayer]
    flight_category: Optional[str]      # VFR / MVFR / IFR / LIFR

    # Pression
    altimeter: Optional[float]          # hPa (QNH)

    # Brut
    raw_metar: Optional[str]

@dataclass
class CloudLayer:
    cover: str      # CLR, FEW, SCT, BKN, OVC
    base_ft: int    # Altitude base en ft
```

### 2.4 Indice VFR

```python
@dataclass
class VFRIndex:
    """Évaluation des conditions VFR pour un point."""
    status: VFRStatus                   # GREEN / YELLOW / RED
    visibility_ok: bool
    ceiling_ok: bool
    wind_ok: bool
    details: str                        # Explication textuelle

class VFRStatus(Enum):
    GREEN = "green"     # VMC confortable
    YELLOW = "yellow"   # VMC marginales
    RED = "red"         # Conditions IFR ou dangereuses
```

---

## 3. Niveaux de pression

Les données de vent et température en altitude sont collectées par niveau de pression.

| Niveau | Altitude approx. | Usage |
|--------|-------------------|-------|
| **1000 hPa** | ~300 ft AMSL | Vent au sol, T/O et L/D |
| **925 hPa** | ~2500 ft AMSL | Croisière basse altitude |
| **850 hPa** | ~5000 ft AMSL | Croisière moyenne altitude |
| **700 hPa** | ~10000 ft AMSL | Croisière haute altitude |

**Règle critique** : utiliser le vent au niveau de vol prévu en croisière (pas le vent au sol METAR/TAF).

| Situation | Source vent |
|-----------|-------------|
| Décollage / atterrissage | Vent 1000 hPa ou vent au sol METAR |
| Croisière FL025 | Vent 925 hPa |
| Croisière FL050 | Vent 850 hPa |
| Croisière FL100 | Vent 700 hPa |

---

## 4. Sources de données

### 4.1 Open-Meteo (prévisions)

**API** : `https://api.open-meteo.com/v1/meteofrance`

| Modèle | Résolution | Horizon | Usage |
|--------|------------|---------|-------|
| Modèle | Résolution | Horizon | Mise à jour | Usage |
|--------|------------|---------|-------------|-------|
| AROME France HD | 1.5 km, horaire | 48h | toutes les 3h | J-1 à J-0 (précision maximale) |
| AROME HD 15min | 1.5 km, 15 min | 48h | toutes les 3h | Haute résolution temporelle |
| ARPEGE Europe | 10 km, horaire | 102h | toutes les 6h | J-4 à J-2 |
| ARPEGE World | 25 km, 3h | 96h | toutes les 6h | Fallback longue échéance |

#### Identification du run de modèle

Chaque modèle expose un endpoint de métadonnées qui permet d'identifier le run courant **avant** d'appeler l'API de prévision :

```
GET https://api.open-meteo.com/data/{model_slug}/static/meta.json
```

| Modèle | `model_slug` |
|--------|-------------|
| AROME France HD | `meteofrance_arome_france_hd` |
| AROME HD 15min | `meteofrance_arome_france_hd_15min` |
| ARPEGE Europe | `meteofrance_arpege_europe` |
| ARPEGE World | `meteofrance_arpege_world025` |

La réponse contient trois timestamps Unix :

| Champ | Description |
|-------|-------------|
| `last_run_initialisation_time` | **Heure d'initialisation du run** (00Z, 06Z, 12Z, 18Z). C'est cette valeur qui alimente `ModelResult.model_run_time`. |
| `last_run_modification_time` | Fin du traitement des données par Open-Meteo. |
| `last_run_availability_time` | Moment où les données sont effectivement disponibles via l'API. |

Ainsi, chaque `WeatherSimulation` enregistre précisément quel run de chaque modèle a été utilisé, permettant de tracer et comparer les résultats entre simulations successives.

#### Sélection des modèles

La simulation interroge **tous les modèles dont l'horizon couvre la date de navigation**. L'horizon est calculé entre `simulated_at` et `navigation_datetime`.

| Horizon | Modèles interrogés |
|---------|-------------------|
| <= 48h | AROME France, AROME HD, ARPEGE Europe |
| 48h — 96h | ARPEGE Europe, ARPEGE World |
| > 96h | ARPEGE Europe (seul modèle, horizon 102h) |

L'utilisateur obtient ainsi plusieurs météogrammes à comparer, avec des résolutions et des caractéristiques différentes.

#### Variables collectées

```
# Température par niveau
temperature_1000hPa, temperature_925hPa, temperature_850hPa, temperature_700hPa

# Vent par niveau
wind_speed_1000hPa, wind_speed_925hPa, wind_speed_850hPa, wind_speed_700hPa
wind_direction_1000hPa, wind_direction_925hPa, wind_direction_850hPa, wind_direction_700hPa
wind_gusts_10m

# Nébulosité & visibilité
cloud_cover, cloud_cover_low, cloud_cover_mid, cloud_cover_high
visibility

# Précipitations
precipitation, rain, snowfall
```

### 4.2 NOAA Aviation Weather Center (METAR)

**API** : `https://aviationweather.gov/api/data/metar`

Fournit les METAR pour un code OACI. Utilisé pour :
- Les observations J-0 (briefing avant vol)
- La collecte a posteriori des observations aux heures de passage réelles

### 4.3 Météo-France API (TAF) - à développer

Source pour les TAF des aérodromes français. Endpoint et format à valider.

---

## 5. WeatherService

### 5.1 Interface

```python
class WeatherService:
    """Service de simulation météo multi-modèles sur une route."""

    async def simulate(
        self,
        route_id: str,
        waypoints: list[RouteWaypoint],
        navigation_datetime: datetime,
    ) -> WeatherSimulation:
        """Lance une simulation multi-modèles sur les points clés de la route.
        - Détermine les modèles éligibles selon l'horizon
        - Collecte les prévisions de chaque modèle pour chaque point
        - Calcule l'indice VFR par point et par modèle
        - Stocke le résultat complet
        """

    async def collect_observations(
        self,
        simulation_id: str,
        actual_times: dict[int, datetime],  # {waypoint_index: heure passage réelle}
    ) -> WeatherSimulation:
        """Collecte a posteriori les observations METAR aux heures de passage réelles.
        Enrichit les WaypointContext avec observation et actual_time.
        Ne concerne que les points qui sont des aérodromes.
        """

    async def get_aerodrome_weather(
        self,
        icao: str,
    ) -> dict:
        """METAR + TAF courants pour un aérodrome."""

    async def list_simulations(
        self,
        route_id: str,
    ) -> list[WeatherSimulation]:
        """Liste toutes les simulations pour une route, ordonnées par date."""
```

### 5.2 Pipeline de simulation

```
┌──────────────────────────────────────────────────────────────────┐
│                   WeatherService.simulate()                       │
│                                                                  │
│  ENTRÉE                                                          │
│    route_id, waypoints[], navigation_datetime                    │
│                                                                  │
│  1. CONSTRUIRE WAYPOINT CONTEXTS                                 │
│     Pour chaque point clé :                                      │
│       → Calculer l'heure de passage estimée                      │
│         (navigation_datetime + timings du plan de vol)           │
│       → Créer WaypointContext (partagé entre modèles)            │
│                                                                  │
│  2. SÉLECTION DES MODÈLES                                       │
│     horizon = navigation_datetime - now()                        │
│     Sélectionner tous les modèles dont l'horizon couvre le vol   │
│     (ex: horizon 36h → AROME France + AROME HD + ARPEGE Europe) │
│                                                                  │
│  3. COLLECTE PRÉVISIONS (par modèle, parallélisable)            │
│     Pour chaque modèle éligible :                                │
│       → Récupérer le run_time courant du modèle                  │
│       → Pour chaque point clé :                                  │
│         → Open-Meteo API au (lat, lon) à l'heure de passage     │
│         → Tous niveaux de pression (1000, 925, 850, 700 hPa)    │
│       → Produire un ModelResult                                  │
│                                                                  │
│  4. CALCUL INDICES VFR                                           │
│     Pour chaque modèle × chaque point :                          │
│       → Vérification VMC (visibilité, plafond, vent)             │
│       → Attribution GREEN / YELLOW / RED                         │
│                                                                  │
│  5. STOCKAGE                                                     │
│     → WeatherSimulation persistée dans Firestore                 │
│     → Identifiant retourné pour consultation ultérieure          │
│                                                                  │
│  SORTIE                                                          │
│    WeatherSimulation (N météogrammes + indices VFR)              │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Collecte d'observations a posteriori

```
┌──────────────────────────────────────────────────────────────────┐
│              WeatherService.collect_observations()                 │
│                                                                  │
│  ENTRÉE                                                          │
│    simulation_id, actual_times = {waypoint_index: datetime}      │
│    (heures extraites du GPX de navigation réelle)                │
│                                                                  │
│  1. CHARGER SIMULATION                                           │
│     Récupérer la WeatherSimulation existante                     │
│                                                                  │
│  2. POUR CHAQUE POINT AÉRODROME                                 │
│     Si actual_time fournie :                                     │
│       → Rechercher METAR le plus proche de actual_time           │
│       → Stocker dans point.observation                           │
│       → Stocker actual_time dans point.actual_time               │
│                                                                  │
│  3. RECALCULER INDICES VFR                                       │
│     Comparer prévisions vs observations                          │
│     Mettre à jour l'indice VFR avec les données réelles          │
│                                                                  │
│  4. SAUVEGARDER                                                  │
│     Mise à jour de la simulation dans Firestore                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Météogramme

Le météogramme est la représentation des données météo le long de la route, point par point. Une simulation produit **un météogramme par modèle**, tous partageant les mêmes waypoints.

### 6.1 Données par point (par modèle)

| Donnée | Source | Unité |
|--------|--------|-------|
| Heure de passage (estimée ou réelle) | Plan de vol / GPX | UTC |
| Température au sol | forecast `temperature_2m` | °C |
| Température au niveau de croisière | forecast `temperature_{level}hPa` | °C |
| Vent au sol (direction, vitesse, rafales) | forecast `wind_*_10m` | °, kt |
| Vent en altitude (direction, vitesse) | forecast `wind_*_{level}hPa` | °, kt |
| Couverture nuageuse (total, bas, moyen, haut) | forecast `cloud_cover_*` | % |
| Visibilité | forecast `visibility` | m |
| Précipitations | forecast `precipitation` | mm |
| QNH | forecast `pressure_msl` | hPa |
| Indice VFR | calculé | GREEN / YELLOW / RED |

### 6.2 Comparaison inter-modèles

Pour un même point et une même variable, on peut comparer les valeurs entre modèles. Cela permet de :
- Évaluer la **confiance** dans la prévision (convergence entre modèles = confiance élevée)
- Identifier les **incertitudes** (divergence entre modèles = prudence)
- Comparer les indices VFR entre modèles pour un même point

### 6.3 Correspondance nébulosité forecast / observation

| Forecast (%) | Octas | Code METAR |
|--------------|-------|------------|
| 0% | 0 | CLR/SKC |
| 1-25% | 2 | FEW |
| 26-50% | 4 | SCT |
| 51-87% | 6 | BKN |
| 88-100% | 8 | OVC |

---

## 7. Analyse VFR

### 7.1 Vérification VMC

#### Sous la surface S (3000 ft AMSL ou 1000 ft/sol)

| Critère | Minimum |
|---------|---------|
| Visibilité | >= 1500 m |
| Nuages | Hors des nuages |

#### Au-dessus de la surface S

| Critère | Minimum |
|---------|---------|
| Visibilité | >= 5000 m |
| Distance horizontale nuages | >= 1500 m |
| Distance verticale nuages | >= 300 m (1000 ft) |

### 7.2 Altitude-densité

```
Altitude densité (ft) = Altitude pression (ft) + [120 x (T°C - T°C ISA)]

avec T°C ISA = 15 - (2 x Altitude pression / 1000)
```

### 7.3 Conversions d'unités

| Source | Unité source | Unité cible | Facteur |
|--------|-------------|-------------|---------|
| Open-Meteo vent | km/h | kt | x 0.539957 |
| Météo-France SYNOP vent | m/s | kt | x 1.94384 |
| NOAA visibilité | SM | m | x 1609.34 |

---

## 8. Stockage

### 8.1 Firestore

Chaque simulation est un document persisté. L'historique complet des simulations est conservé pour une route.

```
/users/{user_id}/routes/{route_id}/
└── simulations/{simulation_id} {
        simulated_at: datetime,
        navigation_datetime: datetime,

        waypoints: [                        # Partagés entre modèles
            {
                waypoint_name, waypoint_index,
                latitude, longitude, icao,
                estimated_time,
                actual_time: datetime | null,
                observation: { ... } | null
            },
            ...
        ],

        model_results: [                    # Un météogramme par modèle
            {
                model: str,
                model_run_time: datetime,
                points: [
                    {
                        waypoint_index: int,
                        forecast: { ... },
                        vfr_index: { status, details, ... }
                    },
                    ...
                ]
            },
            ...
        ]
    }
```

### 8.2 Lien avec le journal de navigation

Après le vol, l'import du GPX fournit les heures de passage réelles. Le processus :

1. Import GPX → extraction des heures de passage aux waypoints
2. Appel `collect_observations(simulation_id, actual_times)`
3. La simulation est enrichie avec `actual_time` et `observation` par point
4. Comparaison prévisions vs réalité disponible

---

## 9. Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/weather/route/{route_id}/simulate` | POST | Lancer une simulation météo |
| `/api/weather/route/{route_id}/simulations` | GET | Lister les simulations pour une route |
| `/api/weather/simulation/{id}` | GET | Récupérer un météogramme |
| `/api/weather/simulation/{id}/observations` | POST | Enrichir avec observations post-vol |
| `/api/weather/aerodrome/{icao}` | GET | METAR + TAF courants |

### POST `/api/weather/route/{route_id}/simulate`

| Paramètre | Type | Description |
|-----------|------|-------------|
| `navigation_datetime` | datetime | Date/heure prévue du vol (UTC). Si omis, utilise celle de la route. |

### POST `/api/weather/simulation/{id}/observations`

| Paramètre | Type | Description |
|-----------|------|-------------|
| `actual_times` | dict | `{waypoint_index: datetime}` — heures de passage réelles |

Ou bien :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `gpx_file` | file | Fichier GPX de la navigation réelle |

---

*Document créé le : 2026-02-01*
*Version : 0.3 - Simulations multi-modèles, séparation waypoints/modèles, comparaison inter-modèles*
