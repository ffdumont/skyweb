# Conception Technique - Import Route SD VFR

## 1. Contexte et problématique

### 1.1 Source : SD VFR Next

L'utilisateur prépare sa route VFR sur **SD VFR Next** (Sofia De Vol à Vue FR) et exporte un fichier **KML**. Ce fichier contient les waypoints de la route avec leurs coordonnées et des altitudes exprimées en **mètres**.

### 1.2 Problème des altitudes SDVFR

Le KML exporté par SDVFR présente des **altitudes incorrectes ou incohérentes** pour la représentation du profil de vol réel :

| Problème | Détail |
|----------|--------|
| **Altitudes waypoints ≠ altitude de croisière du segment** | SDVFR encode dans chaque waypoint une altitude qui ne correspond pas nécessairement à l'altitude de croisière prévue sur le segment |
| **Pas de montée/descente** | Le profil brut est "plat" entre waypoints, sans représenter les phases de montée initiale et d'approche finale |
| **Altitude arrivée à 0 m** | Le dernier waypoint (aérodrome d'arrivée) a souvent une altitude de `0` dans le KML brut |
| **Unité en mètres** | Les altitudes sont en mètres alors que la convention aéronautique est le **pied AMSL** |

### 1.3 Objectif

Transformer le KML brut SDVFR en un **modèle Route** fidèle au profil de vol réel, avec :
- Des altitudes correctes par segment en ft AMSL
- Des phases de montée et de descente réalistes
- Un départ et une arrivée à altitude sol + 1000 ft (tour de piste)

---

## 2. Structure du KML brut SDVFR

### 2.1 Structure générale

Le KML exporté contient deux parties principales :

```xml
<Document>
    <name>LFXU-LFFU</name>

    <!-- 1. Route LineString : tracé avec toutes les coordonnées -->
    <Placemark>
        <name>Navigation</name>
        <LineString>
            <altitudeMode>absolute</altitudeMode>
            <coordinates>lon1,lat1,alt1,lon2,lat2,alt2,...</coordinates>
        </LineString>
    </Placemark>

    <!-- 2. Dossier Points : chaque waypoint individuel -->
    <Folder>
        <name>Points</name>
        <Placemark>
            <name>LFXU - LES MUREAUX</name>
            <Point>
                <coordinates>1.941667,48.998611,426.72,</coordinates>
            </Point>
        </Placemark>
        <!-- ... autres waypoints ... -->
    </Folder>
</Document>
```

### 2.2 Format des coordonnées

Les coordonnées KML suivent le format `longitude,latitude,altitude` séparées par des virgules, avec les triplets séparés par des virgules également (pas d'espace).

| Champ | Unité | Exemple |
|-------|-------|---------|
| Longitude | degrés décimaux (WGS84) | `1.941667` |
| Latitude | degrés décimaux (WGS84) | `48.998611` |
| Altitude | **mètres** (mode `absolute` = AMSL) | `426.72` |

### 2.3 Exemple réel : route LFXU → LFFU

Waypoints extraits du KML brut SDVFR :

| # | Waypoint | Lon | Lat | Alt (m) | Alt (ft) | Observation |
|---|----------|-----|-----|---------|----------|-------------|
| 1 | LFXU - LES MUREAUX | 1.9417 | 48.9986 | 426.72 | 1400 | Départ |
| 2 | MOR1V | 1.9532 | 48.9412 | 426.72 | 1400 | |
| 3 | PXSW | 1.9305 | 48.8343 | 548.64 | 1800 | |
| 4 | HOLAN | 1.8721 | 48.7106 | 548.64 | 1800 | |
| 5 | ARNOU | 1.9318 | 48.5528 | 701.04 | 2300 | |
| 6 | OXWW | 1.9931 | 48.3817 | 944.88 | 3100 | |
| 7 | LFFF/OE | 2.0608 | 48.0778 | 944.88 | 3100 | |
| 8 | BEVRO | 2.1862 | 47.6059 | 883.92 | 2900 | |
| 9 | LFFU - CHATEAUNEUF | 2.3769 | 46.8711 | **0** | **0** | Arrivée — altitude manquante |

**Constat** : l'altitude SDVFR d'un waypoint encode l'altitude du *segment qui commence à ce waypoint*. Le waypoint de départ a l'altitude du premier segment (pas celle du sol), et le waypoint d'arrivée a une altitude de 0 (pas de segment suivant).

---

## 3. Pipeline de correction

### 3.1 Vue d'ensemble

```
KML brut SDVFR
    │
    ▼
┌────────────────────────────────────────────────┐
│ 1. EXTRACTION                                   │
│    Parse XML KML → Point[] + NavigationRoute[]  │
│    (altitudes en mètres)                        │
├────────────────────────────────────────────────┤
│ 2. SEGMENTATION                                 │
│    Waypoints consécutifs → RouteSegment[]       │
│    Conversion mètres → pieds                    │
│    L'altitude du segment = altitude du wp FROM  │
├────────────────────────────────────────────────┤
│ 3. ÉLÉVATION SOL                                │
│    Google Elevation API pour départ et arrivée  │
│    → GroundElevation (ft AMSL)                  │
├────────────────────────────────────────────────┤
│ 4. CORRECTION DES ALTITUDES                     │
│    Départ : élévation sol + 1000 ft             │
│    Intermédiaires : altitude segment précédent  │
│    Arrivée : élévation sol + 1000 ft            │
├────────────────────────────────────────────────┤
│ 5. POINTS INTERMÉDIAIRES                        │
│    Calcul points de montée/descente             │
│    Interpolation position par haversine         │
├────────────────────────────────────────────────┤
│ 6. EXPORT                                       │
│    → KML corrigé (pour analyse espaces aériens) │
│    → Modèle Route en base (pour SkyWeb)         │
└────────────────────────────────────────────────┘
```

### 3.2 Étape 1 — Extraction KML

**Entrée** : fichier `.kml`

**Parsing XML** via `xml.etree.ElementTree`, namespace KML 2.2.

**Deux extractions** :

1. **Waypoints** (`Placemark/Point`) → `List[Point]`
   - Recherche XPath : `.//kml:Placemark[kml:Point]`
   - Champs extraits : `name`, `longitude`, `latitude`, `altitude` (mètres), `description`, `visibility`

2. **Routes** (`Placemark/LineString`) → `List[NavigationRoute]`
   - Recherche XPath : `.//kml:Placemark[kml:LineString]`
   - Champs extraits : `name`, `coordinates[]` (triplets lon,lat,alt), `altitudeMode`

### 3.3 Étape 2 — Segmentation

Pour N waypoints, on crée N-1 segments. L'altitude de chaque segment est dérivée de l'altitude du waypoint **de départ du segment** (le waypoint `from`), convertie en pieds :

```
altitude_feet = from_waypoint.altitude_meters × 3.28084
```

| Segment | From → To | Altitude (ft) |
|---------|-----------|---------------|
| 1 | LFXU → MOR1V | 1400 |
| 2 | MOR1V → PXSW | 1400 |
| 3 | PXSW → HOLAN | 1800 |
| 4 | HOLAN → ARNOU | 1800 |
| 5 | ARNOU → OXWW | 2300 |
| 6 | OXWW → LFFF/OE | 3100 |
| 7 | LFFF/OE → BEVRO | 3100 |
| 8 | BEVRO → LFFU | 2900 |

**Sémantique SDVFR** : l'altitude portée par un waypoint dans le KML représente l'altitude de croisière du segment qui *part* de ce waypoint.

### 3.4 Étape 3 — Élévation sol

Requête **Google Elevation API** (via `ElevationService`) pour obtenir l'élévation du terrain au **premier** et au **dernier** waypoint.

```python
departure_result = elevation_service.get_elevation(lat_dep, lon_dep)
arrival_result   = elevation_service.get_elevation(lat_arr, lon_arr)
```

Le service supporte plusieurs sources avec fallback :
1. Google Elevation API (batch 512 pts)
2. IGN RGE ALTI (France, haute précision)
3. Open-Elevation (global)
4. USGS NED (USA)

Résultat : `GroundElevation` avec `ground_elevation_ft` en pieds AMSL.

### 3.5 Étape 4 — Construction des legs et correction des altitudes

Cette étape produit deux résultats distincts :
- les **legs** : altitude de croisière planifiée entre deux waypoints consécutifs
- les **altitudes waypoints** : altitude instantanée *au passage* du point (pour le profil continu)

#### 3.5.1 Construction des legs

Les legs sont construits directement depuis les segments SDVFR (§3.3). Chaque leg porte l'**altitude de croisière** prévue entre deux waypoints :

| Leg | From → To | Altitude croisière (ft) | Source SDVFR |
|-----|-----------|------------------------|--------------|
| 1 | LFXU → MOR1V | 1400 | altitude brute LFXU |
| 2 | MOR1V → PXSW | 1400 | altitude brute MOR1V |
| 3 | PXSW → HOLAN | 1800 | altitude brute PXSW |
| 4 | HOLAN → ARNOU | 1800 | altitude brute HOLAN |
| 5 | ARNOU → OXWW | 2300 | altitude brute ARNOU |
| 6 | OXWW → LFFF/OE | 3100 | altitude brute OXWW |
| 7 | LFFF/OE → BEVRO | 3100 | altitude brute LFFF/OE |
| 8 | BEVRO → LFFU | 2900 | altitude brute BEVRO |

L'altitude d'un leg provient directement de l'altitude SDVFR du waypoint `from` (convertie en ft). C'est l'**intention de croisière** du pilote pour ce tronçon.

#### 3.5.2 Correction des altitudes aux waypoints

L'altitude *au waypoint* représente l'altitude instantanée de l'avion au moment du survol. Elle sert au profil vertical continu et au calcul des points intermédiaires :

| Position | Règle | Justification |
|----------|-------|---------------|
| **Départ** | `élévation_sol + 1000 ft` | Altitude typique du circuit de piste (TDP) |
| **Waypoint intermédiaire** (index `i`) | `leg[i-1].altitude_ft` | L'avion arrive au point à l'altitude de croisière du leg qu'il vient de parcourir |
| **Arrivée** | `élévation_sol + 1000 ft` | Altitude typique du circuit de piste (TDP) |

> **Distinction clé** : l'altitude du waypoint ("j'arrive ici à X ft") est différente de l'altitude du leg ("je croise à Y ft entre ces deux points"). Le waypoint porte l'altitude de *sortie* du leg précédent. Le leg porte l'*intention de croisière*.

**Exemple sur LFXU → LFFU** (élévation sol départ ≈ 79 ft, arrivée ≈ 548 ft) :

| Waypoint | Alt. brute SDVFR | Alt. au point (corrigée) | Leg suivant | Alt. croisière leg |
|----------|-----------------|--------------------------|-------------|-------------------|
| LFXU | 1400 ft | **1079 ft** (sol+1000) | → MOR1V | 1400 ft |
| MOR1V | 1400 ft | **1400 ft** (leg 1) | → PXSW | 1400 ft |
| PXSW | 1800 ft | **1400 ft** (leg 2) | → HOLAN | 1800 ft |
| HOLAN | 1800 ft | **1800 ft** (leg 3) | → ARNOU | 1800 ft |
| ARNOU | 2300 ft | **1800 ft** (leg 4) | → OXWW | 2300 ft |
| OXWW | 3100 ft | **2300 ft** (leg 5) | → LFFF/OE | 3100 ft |
| LFFF/OE | 3100 ft | **3100 ft** (leg 6) | → BEVRO | 3100 ft |
| BEVRO | 2900 ft | **3100 ft** (leg 7) | → LFFU | 2900 ft |
| LFFU | 0 ft | **1548 ft** (sol+1000) | — | — |

On voit la distinction : PXSW a une altitude *au point* de 1400 ft (il arrive du leg 2 à 1400 ft), mais le leg qui *part* de PXSW est à 1800 ft. La montée se fait entre PXSW et HOLAN.

### 3.6 Étape 5 — Points intermédiaires de montée/descente

Quand deux waypoints consécutifs ont des altitudes corrigées différentes (delta ≥ 100 ft), un **point intermédiaire** est calculé pour matérialiser la phase de montée ou descente.

**Paramètres de configuration** :

| Paramètre | Valeur par défaut | Description |
|-----------|-------------------|-------------|
| `climb_descent_rate_fpm` | 500 ft/min | Taux de montée/descente |
| `ground_speed_kt` | 100 kt | Vitesse sol pour le calcul de distance |

**Algorithme** :

```
1. delta_altitude = |alt_next - alt_current|
2. Si delta < 100 ft → pas d'intermédiaire
3. time_minutes = delta_altitude / climb_rate_fpm
4. distance_nm = ground_speed_kt × time_minutes / 60
5. distance_totale_segment = haversine(wp_current, wp_next)
6. Si distance_nm ≥ distance_totale → pas d'intermédiaire (trop court)
7. ratio = distance_nm / distance_totale
8. Position intermédiaire = interpolation linéaire lat/lon selon ratio
```

**Cas du dernier segment** (approche) : le ratio est calculé **depuis l'arrivée** (`1.0 - ratio`) pour que la descente se termine au seuil de piste.

**Nommage** :
- Montée : `CLIMB_{altitude_cible}` (ex: `CLIMB_1400`)
- Descente : `DESC_{altitude_cible}` (ex: `DESC_2900`)

### 3.7 Étape 6 — Export

#### KML corrigé

Le KML de sortie conserve la structure SDVFR originale :
- **LineString principale** : tous les waypoints (originaux + intermédiaires), altitudes converties en mètres (`ft × 0.3048`)
- **Dossier Points** : chaque waypoint avec son altitude corrigée

Ce KML corrigé sert d'entrée au `RouteAnalyzerService` pour l'analyse 3D des espaces aériens traversés.

#### Modèle Route en base

Le modèle final persisté dans SkyWeb sépare trois concepts :
- **Waypoint** : un lieu géographique (réutilisable entre routes)
- **RouteWaypoint** : le passage d'une route par un waypoint (position dans la séquence)
- **RouteLeg** : l'intention de croisière entre deux waypoints consécutifs

```python
class Waypoint:
    id: str                        # MD5(name:lat:lon)[:16]
    name: str                      # "LFXU - LES MUREAUX", "MOR1V", ...
    lat: float                     # WGS84
    lon: float                     # WGS84
    waypoint_type: WaypointType    # NORMAL | AD

class Route:
    id: int | None
    name: str                      # ex: "LFXU-LFFU"
    waypoints: list[RouteWaypoint]
    legs: list[RouteLeg]
    created_at: datetime

class RouteWaypoint:
    waypoint: Waypoint
    sequence_order: int            # Ordre séquentiel 1..N

class RouteLeg:
    from_sequence_order: int       # Référence RouteWaypoint.sequence_order
    to_sequence_order: int         # = from_sequence_order + 1
    planned_altitude_ft: int       # Altitude de croisière du leg
```

**Principes** :
- Le `Waypoint` est un **lieu pur** — pas d'altitude, pas de contexte route
- Le `RouteWaypoint` est un **passage** — ordre dans la séquence, rien d'autre
- Le `RouteLeg` porte l'**intention de croisière** — altitude explicite par tronçon
- Les altitudes *au point* (profil continu) et les points intermédiaires (CLIMB/DESC) sont **calculés** à la demande, jamais persistés

---

## 4. Schéma de données

### 4.1 Tables SQLite (`navlog.db`)

```sql
CREATE TABLE waypoints (
    id            TEXT PRIMARY KEY,       -- MD5(name:lat:lon)[:16]
    name          TEXT NOT NULL,
    lat           REAL NOT NULL,
    lon           REAL NOT NULL,
    waypoint_type TEXT DEFAULT 'normal'   -- 'normal' | 'aerodrome'
);

CREATE TABLE routes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL             -- ISO 8601
);

CREATE TABLE route_waypoints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id        INTEGER NOT NULL REFERENCES routes(id),
    waypoint_id     TEXT NOT NULL REFERENCES waypoints(id),
    sequence_order  INTEGER NOT NULL,
    UNIQUE(route_id, sequence_order)
);

CREATE TABLE route_legs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id            INTEGER NOT NULL REFERENCES routes(id),
    from_sequence_order INTEGER NOT NULL,
    to_sequence_order   INTEGER NOT NULL,
    planned_altitude_ft INTEGER NOT NULL,  -- Altitude de croisière du leg
    UNIQUE(route_id, from_sequence_order),
    FOREIGN KEY (route_id, from_sequence_order)
        REFERENCES route_waypoints(route_id, sequence_order),
    FOREIGN KEY (route_id, to_sequence_order)
        REFERENCES route_waypoints(route_id, sequence_order)
);
```

> **Note** : `route_waypoints` ne porte plus d'altitude. L'altitude de croisière appartient au `route_leg`. L'altitude *au point* (profil continu) est calculée à la demande depuis les legs adjacents (§3.5.2).

### 4.2 Mapping KML → Base

| Source KML | Transformation | Destination DB |
|------------|----------------|----------------|
| `Placemark/name` | Trim | `waypoints.name` |
| `Point/coordinates` lon | Direct | `waypoints.lon` |
| `Point/coordinates` lat | Direct | `waypoints.lat` |
| Nom contient "LF" + 2 chars | → `waypoint_type = 'aerodrome'` | `waypoints.waypoint_type` |
| `Document/name` | Direct | `routes.name` |
| Position dans la liste | Index 1-based | `route_waypoints.sequence_order` |
| MD5(name:lat:lon)[:16] | Calcul | `waypoints.id` |
| `Point/coordinates` alt du wp `i` | × 3.28084 → ft | `route_legs.planned_altitude_ft` (leg `i` → `i+1`) |

**Règle de mapping des legs** : l'altitude brute SDVFR du waypoint à l'index `i` (convertie en ft) devient l'altitude de croisière du leg `i → i+1`. Le dernier waypoint (arrivée) n'a pas de leg sortant — son altitude brute SDVFR (souvent 0) est ignorée.

---

## 5. Exemple complet : LFXU → LFFU

### 5.1 Profil brut SDVFR

```
3100 ft  ─────────────────────────────╮
2900 ft                               │──────────╮
2300 ft  ──────────╮                              │
1800 ft  ────╮     │                              │
1400 ft  ──╮ │     │                              │
    0 ft   │ │     │                              ╰── ← arrivée à 0
         LFXU MOR PXSW HOL ARNOU OXWW LFFF BEV  LFFU
```

### 5.2 Profil corrigé

```
3100 ft                        ╭────────────╮
2900 ft                        │            ╰──╮
2300 ft               ╭───────╮│               │
1800 ft          ╭───╮│  ↗    ╰╯               │
1548 ft          │   ╰╯                        ╰──╮ ← sol+1000
1400 ft     ╭──╮↗                                  │
1079 ft ──╮↗   │                                   ╰── LFFU
        LFXU  MOR PXSW HOL ARNOU OXWW LFFF BEVRO  LFFU
            ↑     ↑         ↑      ↑            ↑
          CLIMB CLIMB     CLIMB  CLIMB        DESC
          _1400 _1800     _2300  _3100        _2900
```

Points intermédiaires insérés :
- `CLIMB_1400` entre LFXU (1079 ft) et MOR1V (1400 ft)
- `CLIMB_1800` entre PXSW (1400 ft) et HOLAN (1800 ft)
- `CLIMB_2300` entre ARNOU (1800 ft) et OXWW (2300 ft)
- `CLIMB_3100` entre OXWW (2300 ft) et LFFF/OE (3100 ft)
- `DESC_2900` entre BEVRO (3100 ft) et le début de descente vers LFFU (1548 ft)

---

## 6. Configuration

```yaml
route_corrector:
  climb_descent_rate_fpm: 500    # ft/min — taux montée/descente
  ground_speed_kt: 100           # kt — vitesse sol pour calcul distance
```

---

## 7. Conventions d'unités

| Grandeur | Unité stockage | Unité KML | Conversion |
|----------|---------------|-----------|------------|
| Altitude | ft AMSL | mètres | ft = m × 3.28084 |
| Position | degrés décimaux WGS84 | degrés décimaux | aucune |
| Distance | NM (calcul) | — | haversine, R = 3440.065 NM |

---

## 8. Implémentation existante (SkyPath)

| Composant | Fichier | Rôle |
|-----------|---------|------|
| `KMLPointsExtractor` | `skypath_services/route_corrector/route_corrector.py` | Parsing KML, correction altitudes, interpolation, export |
| `ElevationService` | `workflow/transform/altitude_converter.py` | Requête élévation sol multi-sources |
| `correct_route_command` | `cli/commands/correct_route.py` | Commande CLI `sky correct-route` |
| Config | `config.yaml` → `route_corrector` | Paramètres montée/descente |

### 8.1 Commande CLI

```bash
# Correction simple
sky correct-route route_sdvfr.kml

# Avec profil d'altitude PNG
sky correct-route route_sdvfr.kml --profile

# Sortie personnalisée
sky correct-route route_sdvfr.kml --output mon_vol
```

**Sorties** :
- `{basename}_corrected.kml` — KML avec altitudes corrigées
- `{basename}_corrected_report.json` — Rapport d'analyse détaillé
- `{basename}_corrected_profile.png` — Profil d'altitude (optionnel)

---

## 9. Intégration SkyWeb

### 9.1 Endpoint d'import

```
POST /api/route/upload
Content-Type: multipart/form-data
Body: kml_file (fichier .kml)
```

### 9.2 Pipeline côté serveur

```
Upload KML
    │
    ▼
Extraction waypoints + validation
    │
    ▼
Segmentation + conversion ft
    │
    ▼
Requête élévation sol (départ + arrivée)
    │
    ▼
Correction altitudes
    │
    ▼
Calcul points intermédiaires (optionnel)
    │
    ▼
Persistance : waypoints + route + route_waypoints + route_legs
    │
    ▼
Retour : Route avec id, waypoints, legs
```

### 9.3 Séparation des concepts persistés vs calculés

Le modèle distingue clairement ce qui est **persisté** de ce qui est **calculé** :

| Concept | Persisté | Calculé à la demande |
|---------|----------|---------------------|
| Waypoints (lieux) | `waypoints` | — |
| Séquence de la route | `route_waypoints` | — |
| Altitude de croisière par tronçon | `route_legs` | — |
| Altitude instantanée au waypoint (profil) | — | Depuis legs adjacents (§3.5.2) |
| Points intermédiaires CLIMB/DESC | — | Depuis legs + config montée/descente |
| KML corrigé (pour analyse espaces) | — | Généré à la volée |
| Segments (distance, cap) | — | Depuis waypoints consécutifs |

**Principe** : on persiste les **intentions du pilote** (waypoints + altitudes de croisière). Tout ce qui relève de la **modélisation du profil** (montée, descente, altitude instantanée) est dérivé.

### 9.4 Extensibilité du modèle RouteLeg

La table `route_legs` peut accueillir des colonnes supplémentaires sans impact sur le reste du schéma :

| Extension future | Colonne | Usage |
|-----------------|---------|-------|
| Vitesse croisière par leg | `planned_speed_kt` | Calcul temps de vol par tronçon |
| Règle de vol | `flight_rules` | VFR / VFR spécial / IFR |
| Remarque pilote | `remarks` | Notes libres par segment |

---

*Document créé le : 2026-02-02*
*Version : 0.2 — Introduction du concept RouteLeg, séparation waypoint/leg*
