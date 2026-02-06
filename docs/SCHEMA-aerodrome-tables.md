# Schema des tables Aérodromes dans skypath.db

Documentation des tables AD ajoutées à la base de données SkyPath.

**Date:** 2026-02-06
**Base de données:** `%LOCALAPPDATA%/SkyPath/database/skypath.db`

---

## Vue d'ensemble

Trois nouvelles tables ont été ajoutées pour stocker les données aérodromes issues du XML SIA:

| Table | Description | Rows |
|-------|-------------|------|
| `aerodrome` | Informations principales des aérodromes | 565 |
| `aerodrome_runway` | Pistes des aérodromes | 778 |
| `aerodrome_service` | Services ATS (TWR, AFIS, APP...) | 806 |

---

## Table `aerodrome`

Stocke les informations principales de chaque aérodrome.

### Schema

```sql
CREATE TABLE aerodrome (
    -- Identification
    icao            TEXT PRIMARY KEY,   -- Code OACI (sans préfixe LF)
    name            TEXT NOT NULL,      -- Nom complet
    status          TEXT,               -- Statut (CAP/Restreint)
    vfr             TEXT,               -- Trafic VFR autorisé (oui/non)
    private         TEXT,               -- Aérodrome privé (oui/non)

    -- Localisation
    latitude        REAL NOT NULL,      -- Latitude ARP (WGS84)
    longitude       REAL NOT NULL,      -- Longitude ARP (WGS84)
    elevation_ft    INTEGER,            -- Altitude de référence (ft AMSL)
    mag_variation   REAL,               -- Déclinaison magnétique (°)
    ref_temperature REAL,               -- Température de référence (°C)

    -- Horaires & Services
    ats_hours       TEXT,               -- Horaires ATS (texte)
    fuel_available  TEXT,               -- Carburant disponible
    fuel_remarks    TEXT,               -- Remarques carburant
    met_centre      TEXT,               -- Centre météo
    met_briefing    TEXT,               -- Briefing météo

    -- Sécurité
    sslia_category  INTEGER,            -- Catégorie SSLIA

    -- Contact
    management      TEXT,               -- Organisme gestionnaire
    phone           TEXT,               -- Téléphone
    remarks         TEXT,               -- Remarques générales

    -- Metadata
    airac_cycle     TEXT,               -- Cycle AIRAC (non utilisé)
    loaded_at       TEXT,               -- Date de chargement (ISO 8601)
    pk              INTEGER,            -- Clé primaire SIA
    lk              TEXT                -- Clé logique SIA
);
```

### Mapping XML → SQLite

| Champ XML SIA | Colonne SQLite |
|---------------|----------------|
| `Ad.AdCode` | `icao` |
| `Ad.AdNomComplet` | `name` |
| `Ad.AdStatut` | `status` |
| `Ad.TfcVfr` | `vfr` |
| `Ad.TfcPrive` | `private` |
| `Ad.ArpLat` | `latitude` |
| `Ad.ArpLong` | `longitude` |
| `Ad.AdRefAltFt` | `elevation_ft` |
| `Ad.AdMagVar` | `mag_variation` |
| `Ad.AdRefTemp` | `ref_temperature` |
| `Ad.HorAtsTxt` | `ats_hours` |
| `Ad.SvcEscaleFuel` | `fuel_available` |
| `Ad.SvcEscaleFuelRem` | `fuel_remarks` |
| `Ad.MetCentre` | `met_centre` |
| `Ad.MetBriefing` | `met_briefing` |
| `Ad.SsliaCat` | `sslia_category` |
| `Ad.AdGestion` | `management` |
| `Ad.AdTel` | `phone` |
| `Ad.AdRem` | `remarks` |

### Exemple

```sql
SELECT icao, name, latitude, longitude, elevation_ft, status
FROM aerodrome
WHERE icao = 'XU';
-- XU | LES MUREAUX | 48.9986 | 1.9417 | 91 | CAP
```

---

## Table `aerodrome_runway`

Stocke les informations des pistes de chaque aérodrome.

### Schema

```sql
CREATE TABLE aerodrome_runway (
    id              INTEGER PRIMARY KEY,
    icao            TEXT NOT NULL,      -- Référence vers aerodrome.icao
    designator      TEXT NOT NULL,      -- Désignation (ex: "10L/28R")
    length_m        INTEGER,            -- Longueur (m)
    width_m         INTEGER,            -- Largeur (m)
    is_main         TEXT,               -- Piste principale (oui/non)
    surface         TEXT,               -- Type de revêtement
    pcn             TEXT,               -- Résistance PCN
    orientation_geo REAL,               -- Orientation géographique (°)
    lat_thr1        REAL,               -- Latitude seuil 1
    lon_thr1        REAL,               -- Longitude seuil 1
    alt_ft_thr1     INTEGER,            -- Altitude seuil 1 (ft)
    lat_thr2        REAL,               -- Latitude seuil 2
    lon_thr2        REAL,               -- Longitude seuil 2
    alt_ft_thr2     INTEGER,            -- Altitude seuil 2 (ft)
    lda1_m          INTEGER,            -- LDA seuil 1 (m)
    lda2_m          INTEGER,            -- LDA seuil 2 (m)
    pk              INTEGER,            -- Clé primaire SIA
    lk              TEXT                -- Clé logique SIA
);
```

### Mapping XML → SQLite

| Champ XML SIA | Colonne SQLite |
|---------------|----------------|
| `Rwy.Rwy` | `designator` |
| `Rwy.Longueur` | `length_m` |
| `Rwy.Largeur` | `width_m` |
| `Rwy.Principale` | `is_main` |
| `Rwy.Revetement` | `surface` |
| `Rwy.Resistance` | `pcn` |
| `Rwy.OrientationGeo` | `orientation_geo` |
| `Rwy.LatThr1` | `lat_thr1` |
| `Rwy.LongThr1` | `lon_thr1` |
| `Rwy.AltFtThr1` | `alt_ft_thr1` |
| `Rwy.LatThr2` | `lat_thr2` |
| `Rwy.LongThr2` | `lon_thr2` |
| `Rwy.AltFtThr2` | `alt_ft_thr2` |
| `Rwy.Lda1` | `lda1_m` |
| `Rwy.Lda2` | `lda2_m` |

### Exemple

```sql
SELECT designator, length_m, width_m, surface
FROM aerodrome_runway
WHERE icao = 'XU';
-- 10L/28R | 1950 | 50 | non revêtue
-- 10R/28L | 1950 | 50 | non revêtue
```

---

## Table `aerodrome_service`

Stocke les services ATS associés à chaque aérodrome.

### Schema

```sql
CREATE TABLE aerodrome_service (
    id              INTEGER PRIMARY KEY,
    icao            TEXT NOT NULL,      -- Référence vers aerodrome.icao
    service_type    TEXT NOT NULL,      -- Type de service (TWR, AFIS, APP...)
    callsign        TEXT,               -- Indicatif d'appel
    indicator       TEXT,               -- Indicatif de service
    language        TEXT,               -- Langue (fr, en, fr-en...)
    hours_code      TEXT,               -- Code horaire (H24, HJ, HO...)
    hours_text      TEXT,               -- Horaires en texte
    remarks         TEXT,               -- Remarques
    pk              INTEGER,            -- Clé primaire SIA
    lk              TEXT                -- Clé logique SIA
);
```

### Mapping XML → SQLite

| Champ XML SIA | Colonne SQLite |
|---------------|----------------|
| `Service.Service` | `service_type` |
| `Service.IndicLieu` | `callsign` |
| `Service.IndicService` | `indicator` |
| `Service.Langue` | `language` |
| `Service.HorCode` | `hours_code` |
| `Service.HorTxt` | `hours_text` |
| `Service.Remarque` | `remarks` |

### Types de service disponibles

```sql
SELECT service_type, COUNT(*)
FROM aerodrome_service
GROUP BY service_type
ORDER BY COUNT(*) DESC;
```

| Type | Description | Count |
|------|-------------|-------|
| A/A | Air-to-Air | 500 |
| TWR | Tower | 328 |
| AFIS | Aerodrome Flight Information Service | 198 |
| ATIS | Automatic Terminal Information Service | 158 |
| VDF | VHF Direction Finding | 146 |
| APP | Approach | 122 |
| FIS | Flight Information Service | 66 |
| PAR | Precision Approach Radar | 36 |
| SRE | Surveillance Radar Element | 28 |
| UDF | UHF Direction Finding | 20 |
| D-ATIS | Digital ATIS | 10 |

---

## Relations entre tables

```
aerodrome (icao) ─────┬──── aerodrome_runway (icao)
                      │
                      └──── aerodrome_service (icao)
```

**Note:** Les tables utilisent `icao` comme clé de jointure, sans le préfixe "LF" du code OACI complet. Par exemple:
- LFPG → `icao = 'PG'`
- LFXU → `icao = 'XU'`
- LFBO → `icao = 'BO'`

---

## Coexistence avec les tables Espace

Ces tables AD coexistent avec les tables des espaces aériens dans la même base:

| Groupe | Tables |
|--------|--------|
| **Espaces** | Territoire, Espace, Partie, Volume, Service, Frequence |
| **Aérodromes** | aerodrome, aerodrome_runway, aerodrome_service |

**Note:** La table `Service` des espaces et `aerodrome_service` sont distinctes.

---

## Utilisation

### Chargement des données

```python
from workflow.load.load import UnifiedLoader
from pathlib import Path

db_path = Path(r'C:/Users/franc/AppData/Local/SkyPath/database/skypath.db')
loader = UnifiedLoader(element_type='Ad')
result = loader.bulk_load_configured(database_path=str(db_path), use_default_db=True)
```

### Requêtes SQL

```sql
-- Tous les aérodromes VFR ouverts
SELECT icao, name, elevation_ft
FROM aerodrome
WHERE vfr = 'oui' AND status = 'CAP';

-- Pistes de plus de 2000m
SELECT a.icao, a.name, r.designator, r.length_m
FROM aerodrome a
JOIN aerodrome_runway r ON a.icao = r.icao
WHERE r.length_m >= 2000
ORDER BY r.length_m DESC;

-- Aérodromes avec service TWR
SELECT DISTINCT a.icao, a.name
FROM aerodrome a
JOIN aerodrome_service s ON a.icao = s.icao
WHERE s.service_type = 'TWR';
```

---

## Fichiers source

| Fichier | Rôle |
|---------|------|
| `workflow/load/schema_generator.py` | Génération du schéma SQLite |
| `workflow/load/load.py` | Chargement des données (AdLoader, bulk_load_ad_from_file) |
| `workflow/extract/ad_extractor.py` | Extraction des données XML |
| `data/xml_sia/XML_SIA_AD.xsd` | Schéma XSD de validation |
