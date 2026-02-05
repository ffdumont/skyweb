# Design : Onglet Météo

## Vue d'ensemble

L'onglet météo permet de visualiser les prévisions météorologiques le long de la route, avec possibilité de lancer des simulations pour différentes heures et de comparer les modèles.

## Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Route Profile (réutilisé de RouteTab)                              │
│  [===LFPG====LFBO=====LFML===] avec heures de passage              │
├─────────────────────────────────────────────────────────────────────┤
│  Contrôles simulation                                               │
│  [Date/heure: ____] [Vitesse: 100kt] [▶ Lancer simulation]         │
│  Simulations: [2024-01-15 12:00 ▼] [🗑]                             │
├─────────────────────────────────────────────────────────────────────┤
│  Filtres: [☑ AROME] [☑ ARPEGE] [☐ GFS] [☐ ICON]                    │
│           [☑ Temp] [☑ Vent cruise] [☑ Vent sol] [☐ Nuages]         │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─ AROME (run 06Z, horizon +12h) ─────────────────────────────────┐│
│  │         │ LFPG    │ LFBO    │ LFML    │                         ││
│  │         │ 08:00   │ 09:30   │ 11:00   │                         ││
│  │─────────┼─────────┼─────────┼─────────┼                         ││
│  │ Temp    │ 15°C    │ 18°C    │ 22°C    │                         ││
│  │ Vent FL │ 270/25  │ 280/30  │ 290/20  │                         ││
│  │ Vent sol│ 180/10  │ 200/08  │ 220/12  │                         ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─ ARPEGE (run 00Z, horizon +24h) ────────────────────────────────┐│
│  │         │ LFPG    │ LFBO    │ LFML    │                         ││
│  │  ...                                                            ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Modèles météo

| Modèle | Source | Résolution | Runs | Horizon |
|--------|--------|------------|------|---------|
| AROME | Météo-France | 1.3km | 00/03/06/12/18/21Z | +42h |
| ARPEGE | Météo-France | 10km | 00/06/12/18Z | +102h |
| GFS | NOAA | 25km | 00/06/12/18Z | +384h |
| ICON | DWD | 13km | 00/06/12/18Z | +180h |

## Variables météo

| Variable | Unité | Description |
|----------|-------|-------------|
| temp_cruise | °C | Température à l'altitude de croisière |
| wind_cruise | °/kt | Vent à l'altitude de croisière (dir/vitesse) |
| wind_ground | °/kt | Vent au sol (10m) |
| cloud_low | % ou oktas | Couverture nuageuse basse (<6500ft) |
| cloud_mid | % ou oktas | Couverture nuageuse moyenne (6500-20000ft) |
| cloud_high | % ou oktas | Couverture nuageuse haute (>20000ft) |
| precip | mm/h | Précipitations |
| visibility | km | Visibilité horizontale |
| cape | J/kg | Énergie convective disponible |
| freezing_level | ft | Niveau de l'isotherme 0°C |

## Calcul des heures de passage

```
departure_time = dossier.departure_datetime_utc
cruise_speed_kt = aircraft.cruise_speed_kt ?? 100

for each waypoint:
    distance_from_start_nm = sum(leg distances)
    flight_time_hours = distance_from_start_nm / cruise_speed_kt
    passage_time = departure_time + flight_time_hours
```

## API Backend

### GET /api/weather/models
Liste des modèles disponibles avec leur dernier run.

```json
{
  "models": [
    {
      "id": "arome",
      "name": "AROME",
      "provider": "Météo-France",
      "latest_run": "2024-01-15T06:00:00Z",
      "horizon_hours": 42
    }
  ]
}
```

### POST /api/weather/simulations
Lance une simulation météo pour une route.

Request:
```json
{
  "route_id": "abc123",
  "dossier_id": "def456",
  "departure_datetime_utc": "2024-01-15T08:00:00Z",
  "cruise_speed_kt": 100,
  "cruise_altitude_ft": 5500,
  "models": ["arome", "arpege"],
  "variables": ["temp_cruise", "wind_cruise", "wind_ground"]
}
```

Response:
```json
{
  "simulation_id": "sim123",
  "created_at": "2024-01-14T20:00:00Z",
  "departure_datetime_utc": "2024-01-15T08:00:00Z",
  "waypoints": [
    {
      "name": "LFPG",
      "lat": 49.0097,
      "lon": 2.5479,
      "passage_time_utc": "2024-01-15T08:00:00Z"
    },
    {
      "name": "LFBO",
      "lat": 43.6293,
      "lon": 1.3638,
      "passage_time_utc": "2024-01-15T09:45:00Z"
    }
  ],
  "forecasts": {
    "arome": {
      "model_run": "2024-01-15T06:00:00Z",
      "data": [
        {
          "waypoint": "LFPG",
          "temp_cruise": 15.2,
          "wind_cruise_dir": 270,
          "wind_cruise_speed": 25,
          "wind_ground_dir": 180,
          "wind_ground_speed": 10
        }
      ]
    }
  }
}
```

### GET /api/weather/simulations?dossier_id={id}
Liste des simulations pour un dossier.

### DELETE /api/weather/simulations/{simulation_id}
Supprime une simulation.

## Stockage

### WeatherSimulation (Firestore ou in-memory)

```python
class WeatherSimulation:
    id: str
    dossier_id: str
    route_id: str
    created_at: datetime
    departure_datetime_utc: datetime
    cruise_speed_kt: int
    cruise_altitude_ft: int
    models: list[str]
    variables: list[str]
    waypoints: list[WaypointForecast]
    forecasts: dict[str, ModelForecast]
```

## Frontend State (dossierStore extension)

```typescript
interface WeatherState {
  // Simulation management
  simulations: WeatherSimulation[];
  currentSimulationId: string | null;
  simulationLoading: boolean;

  // Display preferences
  selectedModels: Set<string>;
  selectedVariables: Set<string>;

  // Simulation parameters
  simulationDeparture: string; // ISO datetime
  cruiseSpeedKt: number;
}

interface WeatherActions {
  loadSimulations: (dossierId: string) => Promise<void>;
  runSimulation: (params: SimulationParams) => Promise<void>;
  deleteSimulation: (simulationId: string) => Promise<void>;
  selectSimulation: (simulationId: string) => void;
  toggleModel: (modelId: string) => void;
  toggleVariable: (variableId: string) => void;
  setSimulationDeparture: (datetime: string) => void;
  setCruiseSpeed: (speedKt: number) => void;
}
```

## Composants React

```
MeteoTab/
├── MeteoTab.tsx              # Container principal
├── RouteProfileWithTimes.tsx # Profil avec heures de passage
├── SimulationControls.tsx    # Date, vitesse, bouton run
├── SimulationSelector.tsx    # Dropdown simulations passées
├── ModelFilters.tsx          # Checkboxes modèles
├── VariableFilters.tsx       # Checkboxes variables
├── ModelSection.tsx          # Section par modèle
└── ForecastTable.tsx         # Tableau waypoints x variables
```

## Implémentation par phases

### Phase 1 : UI statique
- Layout complet avec données mock
- Profil route avec heures calculées
- Filtres modèles/variables fonctionnels (local state)

### Phase 2 : Backend simulation
- API endpoints
- Stockage simulations
- Mock data provider (pas d'API météo réelle)

### Phase 3 : Intégration API météo
- Connexion Open-Meteo ou autre
- Cache des données
- Gestion des runs modèles

## Sources de données météo potentielles

1. **Open-Meteo** (gratuit, open source)
   - API REST simple
   - Plusieurs modèles (GFS, ICON, etc.)
   - Pas AROME/ARPEGE

2. **Météo-France API** (gratuit avec inscription)
   - AROME, ARPEGE
   - Données françaises haute résolution

3. **NOAA GFS** (gratuit)
   - Données brutes GRIB
   - Nécessite parsing

Pour la phase 1-2, on utilisera des données mock réalistes.
