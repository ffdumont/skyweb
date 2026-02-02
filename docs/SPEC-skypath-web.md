# Spécification — Migration SkyPath vers SkyWeb

## 1. Objectif

Reprendre l'ensemble des fonctionnalités de **SkyPath** (analyse d'espaces aériens, pipeline ETL, visualisation 3D) dans **SkyWeb**, avec quatre différences structurantes :

| Axe | SkyPath (actuel) | SkyWeb (cible) |
|-----|-------------------|----------------|
| **Base de données** | SQLite/SpatiaLite local | GCP (Firestore + SpatiaLite sur GCS) |
| **Visualisation** | Google Earth Desktop (KML) | Client web 3D — CesiumJS |
| **Performance affichage** | Hors périmètre (fichiers KML) | Critique — streaming, LOD, tiling |
| **Concurrence** | Mono-utilisateur | Multi-utilisateurs, mises à jour cohérentes |

---

## 2. Périmètre fonctionnel

### 2.1 Fonctionnalités SkyPath à reprendre

Toutes les capacités SkyPath sont reprises. Le tableau ci-dessous détaille le mapping :

| # | Fonctionnalité SkyPath | Composant source | Reprise SkyWeb | Remarques |
|---|------------------------|------------------|----------------|-----------|
| F1 | **Pipeline ETL XML SIA** | `workflow/extract`, `load`, `transform`, `validate` | Oui — service backend | Déclenché par admin, résultat partagé entre utilisateurs |
| F2 | **Chargement bulk XML → SQLite** | `workflow/load/load.py` | Oui — Cloud SQL ou GCS + SpatiaLite | Cible : base de référence partagée |
| F3 | **Transformation spatiale (6 phases)** | `workflow/transform/spatial_indexer.py` | Oui — job batch GCP | Exécution asynchrone (Cloud Run Job ou Cloud Tasks) |
| F4 | **Validation XML/XSD** | `workflow/validate/validate.py` | Oui — étape du pipeline admin | |
| F5 | **Requêtes spatiales 3D** | `AirspaceQueryAPI` | Oui — service backend | API REST exposée au client web |
| F6 | **Analyse de route** | `RouteAnalyzerService` | Oui — service backend | Résultats en JSON + visualisation Cesium |
| F7 | **Export KML 3D espaces aériens** | `KMLVolumeExporter` | Remplacé — rendu Cesium | Plus de génération KML ; les géométries sont servies directement au client |
| F8 | **Correction altitudes SDVFR** | `KMLPointsExtractor` / `route_corrector` | Oui — service backend | Inchangé fonctionnellement |
| F9 | **Service d'élévation** | `ElevationService` (Google, IGN, etc.) | Oui — service backend | Cache partagé entre utilisateurs |
| F10 | **Coloration espaces aériens** | `AirspaceColoringService` | Oui — côté client Cesium | Configuration JSON partagée |
| F11 | **GUI analyse de route** | `gui/route_analyzer_gui.py` (CustomTkinter) | Remplacé — interface web | |
| F12 | **GUI pipeline ETL** | `gui/update_gui.py` (CustomTkinter) | Remplacé — interface admin web | |
| F13 | **CLI `sky`** | `cli/` (Typer, 12 commandes) | Partiel — commandes admin conservées localement si besoin | L'essentiel passe en API REST |

### 2.2 Nouvelles capacités (absentes de SkyPath)

| # | Capacité | Description |
|---|----------|-------------|
| N1 | **Visualisation web 3D** | Globe CesiumJS avec espaces aériens, routes, profil vertical |
| N2 | **Tiling géospatial** | Servir les géométries par tuiles pour performance à l'échelle |
| N3 | **Multi-utilisateurs** | Gestion concurrence sur données partagées (AIRAC) et privées (routes) |
| N4 | **Temps réel** | Notifications de mise à jour AIRAC, invalidation cache client |
| N5 | **Profil vertical interactif** | Vue coupe verticale de la route avec espaces traversés |

---

## 3. Architecture cible

### 3.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT WEB (SPA)                             │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │  CesiumJS    │  │  Panneau analyse │  │  Profil vertical      │ │
│  │  Globe 3D    │  │  (route, espaces)│  │  (coupe latérale)     │ │
│  └──────┬───────┘  └────────┬─────────┘  └───────────┬───────────┘ │
│         │                   │                         │             │
│         └───────────────────┼─────────────────────────┘             │
│                             │                                       │
│                    API REST / WebSocket                              │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────┐
│                       GCP BACKEND                                   │
│                              │                                       │
│  ┌──────────────────────────┴──────────────────────────────────┐   │
│  │                    API Gateway (Cloud Run)                    │   │
│  │                    FastAPI + Firebase Auth                    │   │
│  └──┬──────────┬──────────┬──────────┬──────────┬──────────────┘   │
│     │          │          │          │          │                    │
│  ┌──┴───┐  ┌──┴───┐  ┌──┴───┐  ┌──┴───┐  ┌──┴──────────┐        │
│  │Route │  │Airsp.│  │Weather│  │Aero. │  │  Tile       │        │
│  │Svc   │  │Svc   │  │Svc   │  │Svc   │  │  Service    │        │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬──────────┘        │
│     │         │         │         │           │                     │
│  ┌──┴─────────┴─────────┴─────────┴───────────┴──────────────┐    │
│  │                    DATA LAYER                               │    │
│  │                                                             │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐ │    │
│  │  │ Firestore   │  │ SpatiaLite   │  │ Cloud Storage     │ │    │
│  │  │ (user data) │  │ (from GCS)   │  │ (db, tiles, ref)  │ │    │
│  │  └─────────────┘  └──────────────┘  └───────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              PIPELINE ADMIN (Cloud Run Jobs)                   │  │
│  │  ETL XML SIA → Transform spatial → Generate tiles             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Choix technologiques

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| **Globe 3D** | CesiumJS (open source) | Standard industrie pour la géovisualisation web 3D, support natif des entités géospatiales, terrain, et formats aéronautiques |
| **Client web** | React + TypeScript | Écosystème mature, intégration Cesium via `resium` ou wrapper custom |
| **API backend** | FastAPI (Python 3.11+) | Cohérent avec SkyPath, async natif, validation Pydantic |
| **Base référence** | SpatiaLite sur GCS | Réutilisation directe du code SkyPath, coût quasi-nul (voir §3.3) |
| **Base utilisateur** | Firestore | Déjà défini dans SkyWeb (voir DESIGN-contracts.md) |
| **Stockage** | Cloud Storage | Tiles pré-générées, KML archivés, fichiers utilisateur |
| **Auth** | Firebase Auth | Déjà défini dans SkyWeb |
| **Temps réel** | Firestore listeners + WebSocket | Notifications AIRAC, invalidation cache |

### 3.3 Base de données de référence — SpatiaLite sur GCS

La base de référence aéronautique (espaces aériens, aérodromes) réutilise directement le format SkyPath existant.

#### Principe

| Aspect | Détail |
|--------|--------|
| **Fonctionnement** | La base `skypath.db` générée par le pipeline ETL est stockée sur GCS. Chaque instance Cloud Run la télécharge au démarrage et la charge en mémoire |
| **Coût** | Quasi-nul — stockage GCS uniquement (~200 Mo × quelques versions) |
| **Migration code** | **Aucune** — les requêtes SQL SpatiaLite de `AirspaceQueryAPI` fonctionnent telles quelles |
| **Concurrence** | Adaptée — la base est en lecture seule, chaque instance Cloud Run a sa propre copie |
| **Performance** | Identique à SkyPath une fois chargée en mémoire (requêtes 10-50 ms/segment) |
| **Startup** | Téléchargement GCS → disque local au cold start (~200 Mo, quelques secondes) |

#### Pourquoi c'est suffisant

La base de référence AIRAC est **read-only** par nature — seul le pipeline admin y écrit, lors d'un changement de cycle (tous les 28 jours). Il n'y a jamais d'écriture concurrente en production. Le pattern "fichier SQLite servi en lecture" est un cas d'usage classique et performant pour Cloud Run.

#### Cycle de vie

```
Pipeline ETL (Cloud Run Job)
    │
    ├── Génère skypath.db (phases 0-5 SkyPath)
    ├── Upload → gs://skyweb-reference/airac/{cycle}/skypath.db
    └── Met à jour metadata Firestore

Instance Cloud Run (API)
    │
    ├── Au démarrage : télécharge skypath.db depuis GCS → /tmp/
    ├── Ouvre connexion SQLite read-only
    └── Sert les requêtes spatiales (identique à SkyPath)

Changement de cycle AIRAC
    │
    ├── Nouvelle base uploadée sur GCS
    ├── Notification Firestore → clients
    └── Prochaines instances Cloud Run chargeront la nouvelle version
        (les instances existantes continuent avec l'ancienne jusqu'à recyclage)
```

#### Évolution future (si nécessaire)

Si le besoin d'écriture concurrente ou de requêtes multi-instances lourdes se confirmait, une migration vers Cloud SQL PostgreSQL + PostGIS serait possible. Les fonctions spatiales sont quasi-identiques (`ST_Intersects`, `ST_Buffer`, etc.). Cette option n'est pas retenue pour l'instant en raison de son coût (~30-50€/mois).

---

## 4. Visualisation web — CesiumJS

### 4.1 Remplacement de Google Earth Desktop

| Fonction GE Desktop | Équivalent CesiumJS |
|---------------------|---------------------|
| KML 3D extrudé (espaces aériens) | `Cesium.Entity` avec `polygon` extrudé ou `Cesium3DTileset` |
| Coloration par classe/type | `ColorMaterialProperty` dynamique, même palette JSON |
| Labels (nom, classe, altitudes) | `Cesium.LabelGraphics` attachés aux entités |
| Navigation caméra | Natif CesiumJS (orbit, fly-to, zoom) |
| Terrain 3D | `CesiumTerrainProvider` (Cesium World Terrain) |
| Overlay route | `Cesium.PolylineGraphics` avec altitude |

### 4.2 Couches d'affichage

Le client web organise les données en couches superposables :

| Couche | Source | Chargement | Interactivité |
|--------|--------|------------|---------------|
| **Terrain** | Cesium World Terrain | Streaming natif | — |
| **Espaces aériens** | Tile service backend | Par tuiles (viewport) | Click → détails (classe, limites, fréquences) |
| **Route** | API analyse | À la demande | Survol → infos leg, click → détails intersection |
| **Aérodromes** | API référence | Par viewport | Click → fiche AD complète |
| **Météo** | API weather | À la demande | Overlay vent, plafond, indice VFR par point |
| **Intersections** | API analyse | Avec la route | Surlignage des zones traversées |

### 4.3 Performance d'affichage

La performance est critique pour le rendu de 63 000+ espaces / 255 000+ géométries. Stratégie en trois niveaux :

#### Niveau 1 — Tiling côté serveur (pré-traitement)

```
Pipeline ETL existant
    │
    ▼
Phase 6 (nouvelle) — Génération de tuiles
    │
    ├── Découpage géographique en tuiles (grille ou quadtree)
    ├── Simplification géométrique par niveau de zoom (Douglas-Peucker)
    ├── Formats : GeoJSON tuilé ou Cesium 3D Tiles
    └── Stockage : Cloud Storage (CDN-ready)
```

| Niveau de zoom | Contenu | Simplification |
|----------------|---------|----------------|
| Z0-Z5 (pays) | FIR, TMA majeures | Forte (tolérance 0.01°) |
| Z6-Z8 (région) | TMA, CTR, SIV, D, R, P | Moyenne (tolérance 0.001°) |
| Z9-Z12 (local) | Tous espaces, aérodromes | Minimale (géométries complètes) |

#### Niveau 2 — Chargement intelligent côté client

| Technique | Description |
|-----------|-------------|
| **Viewport culling** | Ne charger que les tuiles visibles dans le frustum caméra |
| **LOD (Level of Detail)** | Détail croissant au zoom — géométries simplifiées en vue large |
| **Lazy loading** | Chargement progressif : contours d'abord, détails au zoom |
| **Cache client** | IndexedDB pour les tuiles déjà chargées (invalidées par version AIRAC) |

#### Niveau 3 — Optimisation du rendu Cesium

| Technique | Description |
|-----------|-------------|
| **Primitive batching** | Regrouper les polygones par type/classe en `Cesium.Primitive` (vs Entity individuelle) |
| **Entity clustering** | Regrouper les labels/icônes en zoom large |
| **Altitude clamping** | `heightReference: CLAMP_TO_GROUND` pour les espaces à sol |
| **Extrusion conditionnelle** | Extruder uniquement les espaces dont floor ≠ GND au zoom local |

### 4.4 Formats de données serveur → client

| Approche | Format | Usage |
|----------|--------|-------|
| **Tuiles statiques** | Cesium 3D Tiles (`.b3dm` / `.json`) | Espaces aériens pré-tuilés — performance maximale |
| **Données dynamiques** | GeoJSON via API REST | Route analysée, intersections, résultats météo |
| **Quantized mesh** | Terrain tiles | Terrain 3D (fourni par Cesium Ion ou auto-hébergé) |

### 4.5 Profil vertical interactif

Vue en coupe le long de la route, affichée en panneau latéral :

```
Alt (ft)
  5000│
      │         ┌─────────TMA PARIS 1──────────┐
  4000│         │    Classe D [1500-4500ft]     │
      │    ╭────┤                               │
  3000│────╯    │  ══════ Route ════════════    │
      │         │                               │
  2000│         └───────────────────────────────┘
      │    ┌──CTR──┐
  1500│    │  C    │
      │ ───╯      ╰───
  1000│
      │ ░░░░░░ Terrain ░░░░░░░░░░░░░░░░░░░░░░░
   500│
      └────────────────────────────────────────── Distance (NM)
       LFXU  MOR  PXSW  HOL  ARNOU  OXWW  LFFU
```

Composant séparé (Canvas 2D ou bibliothèque de charts), synchronisé avec la vue Cesium :
- Survol du profil → highlight du segment sur le globe
- Click sur un espace dans le profil → zoom Cesium sur la zone
- Données : altitudes route, terrain (élévation), espaces intersectés avec leurs limites verticales

---

## 5. Base de données GCP

### 5.1 Séparation des données

La séparation existante est maintenue et renforcée :

```
┌───────────────────────────────────────────────────────────────┐
│                     DONNÉES DE RÉFÉRENCE                       │
│                 (partagées, read-only pour les utilisateurs)   │
│                                                                │
│  SpatiaLite sur GCS (skypath.db par cycle AIRAC)              │
│  ├── Espaces aériens (63 000+)                                │
│  │   ├── Territoire, Espace, Partie, Volume, Geometrie       │
│  │   ├── Index spatial R-tree / GiST                          │
│  │   └── Vue matérialisée airspace_spatial_indexed            │
│  ├── Fréquences (8 000+)                                      │
│  ├── Aérodromes (voir DESIGN-preparation-vol-vfr.md §5.2)    │
│  └── Cache élévation                                          │
│                                                                │
│  Mise à jour : cycle AIRAC (28 jours)                         │
│  Responsable : admin uniquement                               │
│  Versionnée par cycle AIRAC                                   │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                     DONNÉES UTILISATEUR                        │
│                 (privées, read-write par propriétaire)         │
│                                                                │
│  Firestore                                                     │
│  /users/{user_id}/                                             │
│  ├── user_waypoints/{id}     → UserWaypoint                   │
│  ├── routes/{id}             → Route + legs                   │
│  │   └── simulations/{id}    → WeatherSimulation              │
│  ├── aircraft/{id}           → Aircraft                       │
│  └── flights/{id}            → Flight + Track                 │
│                                                                │
│  Mise à jour : temps réel par l'utilisateur                   │
│  Isolation : un utilisateur ne voit que ses données            │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                     DONNÉES COMMUNAUTÉ                          │
│                 (partagées, write par utilisateurs autorisés)  │
│                                                                │
│  Firestore                                                     │
│  /community/                                                   │
│  ├── vac_notes/{icao}        → Notes VAC capitalisées         │
│  └── tdp_database/{icao}     → Sens et altitude TDP           │
│                                                                │
│  Mise à jour : collaborative, modérée                         │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                     TUILES PRÉ-CALCULÉES                       │
│                 (statiques, générées par pipeline admin)       │
│                                                                │
│  Cloud Storage (CDN)                                           │
│  gs://skyweb-tiles/{airac_cycle}/                              │
│  ├── airspaces/                                                │
│  │   ├── {z}/{x}/{y}.json   → GeoJSON tuilé par zoom          │
│  │   └── tileset.json        → Manifest Cesium 3D Tiles        │
│  ├── aerodromes/                                               │
│  │   └── {z}/{x}/{y}.json                                      │
│  └── metadata.json            → Cycle, date génération, stats  │
│                                                                │
│  Regénérées à chaque cycle AIRAC                               │
│  Servies directement par GCS (pas de compute)                 │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 Versionnement AIRAC

Chaque cycle AIRAC produit un jeu complet de données (base SpatiaLite + tuiles). Plusieurs versions coexistent sur GCS :

```
gs://skyweb-reference/
├── airac/
│   ├── 2602/                          # Cycle AIRAC 2602
│   │   ├── skypath.db                 # Base SpatiaLite complète
│   │   ├── metadata.json              # Stats, date, version
│   │   └── status: "archived"
│   ├── 2603/                          # Cycle AIRAC 2603 (actif)
│   │   ├── skypath.db
│   │   ├── metadata.json
│   │   └── status: "active"
│   └── 2604/                          # Cycle AIRAC 2604 (prêt)
│       ├── skypath.db
│       ├── metadata.json
│       └── status: "ready"
└── current_cycle → 2603               # Pointeur vers cycle actif

gs://skyweb-tiles/
├── 2603/                              # Tuiles du cycle actif
│   ├── airspaces/{z}/{x}/{y}.json
│   └── tileset.json
└── 2604/                              # Tuiles pré-générées
    └── ...

Firestore /admin/
└── airac_cycles/{cycle_id}            # Metadata + status
```

#### Activation d'un nouveau cycle

```
POST /admin/airac/activate {cycle: "2604"}
    │
    ├── Mettre à jour le pointeur GCS (current_cycle → 2604)
    ├── Mettre à jour Firestore /admin/current_cycle
    ├── Notifier les clients (Firestore listener)
    │   └── Bandeau : "Nouvelles données AIRAC — Recharger"
    └── Les nouvelles instances Cloud Run chargeront skypath.db 2604
        (instances existantes : recyclées naturellement par Cloud Run)
```

---

## 6. Gestion multi-utilisateurs

### 6.1 Modèle de concurrence

| Type de données | Stratégie | Détail |
|-----------------|-----------|--------|
| **Référence AIRAC** | Lecture seule | Aucune concurrence — données identiques pour tous |
| **Tuiles** | Lecture seule (CDN) | Servies depuis GCS, versionnées par AIRAC |
| **Données utilisateur** | Isolation par `user_id` | Chaque utilisateur a son espace Firestore |
| **Notes VAC communauté** | Last-write-wins + audit | Firestore `updated_at` + `updated_by` |
| **Cache élévation** | Partagé, append-only | Cache en lecture ; écriture par le pipeline admin uniquement |

### 6.2 Scénarios de concurrence

#### Mise à jour AIRAC en cours d'utilisation

```
Utilisateur A analyse une route
    │
    ├── Requête airspace → SpatiaLite cycle N (en mémoire)
    │
    │   [Admin active le cycle N+1]
    │
    ├── Client reçoit notification "nouveau cycle AIRAC disponible"
    ├── Affiche un bandeau : "Nouvelles données aéronautiques disponibles — Recharger"
    └── L'utilisateur décide quand recharger (pas de rupture en cours d'analyse)
```

#### Notes VAC collaborative

```
Utilisateur A édite les notes de LFXU
Utilisateur B édite les notes de LFXU (même document)
    │
    ├── Firestore : dernier écrivain gagne
    ├── Champs `updated_at` et `updated_by` tracent l'historique
    └── Optionnel : Firestore `onSnapshot` pour diff temps réel
```

### 6.3 Authentification et autorisation

| Rôle | Capacités |
|------|-----------|
| **Anonyme** | Consultation globe (espaces aériens, aérodromes) — lecture seule |
| **Utilisateur** | Import route, analyse, météo, préparation vol, notes VAC |
| **Admin** | Pipeline AIRAC, activation cycle, gestion communauté |

---

## 7. Pipeline ETL migré

### 7.1 Pipeline actuel SkyPath (6 phases)

| Phase | Description | Durée actuelle |
|-------|-------------|----------------|
| 0 | Vérification prérequis | ~0.1s |
| 1 | Conversion WKT → géométries + R-tree | ~60s |
| 2 | Conversion altitudes FL → ft AMSL | ~15s |
| 3 | Élévation API (ASFC/SFC → AMSL) | ~1-2 min |
| 4 | Vue matérialisée optimisée | ~5s |
| 5 | Validation qualité | ~2s |

### 7.2 Pipeline SkyWeb (7 phases)

Les 6 phases existantes sont conservées. Une 7e phase est ajoutée :

| Phase | Description | Exécution |
|-------|-------------|-----------|
| 0-5 | **Identiques à SkyPath** (sortie : skypath.db sur GCS) | Cloud Run Job (batch) |
| **6** | **Génération tuiles Cesium** | Cloud Run Job (batch) |

#### Phase 6 — Génération de tuiles

```
Entrée : base SpatiaLite peuplée (phases 0-5, sur GCS)

1. Requêter toutes les géométries avec altitudes AMSL
2. Pour chaque niveau de zoom (Z5 → Z12) :
   a. Découper en tuiles selon grille XYZ
   b. Simplifier les géométries (Douglas-Peucker, tolérance par zoom)
   c. Filtrer les espaces pertinents au zoom (FIR seul en Z5, tout en Z12)
   d. Générer GeoJSON par tuile avec propriétés :
      - identifier, type, class, lower_ft, upper_ft, color_html
   e. Optionnel : convertir en Cesium 3D Tiles (.b3dm) pour rendu optimal
3. Uploader vers gs://skyweb-tiles/{cycle}/
4. Générer le manifeste (tileset.json)

Sortie : tuiles prêtes à servir via CDN
```

### 7.3 Orchestration

```
Déclenchement : POST /admin/airac/upload (admin authentifié)
    │
    ▼
Cloud Run Job "etl-pipeline"
    │
    ├── Phase 0-5 : identique SkyPath → skypath.db uploadée sur GCS
    ├── Phase 6 : génération tuiles → GCS
    │
    ├── En cas de succès :
    │   ├── Écriture Firestore /admin/airac_cycles/{id} status="ready"
    │   └── Notification admin
    │
    └── En cas d'erreur :
        ├── Log détaillé dans Cloud Logging
        └── Notification admin (erreur + phase)

Activation : POST /admin/airac/activate (admin authentifié)
    │
    ├── Mise à jour pointeur GCS + Firestore /admin/current_cycle
    ├── Notification clients (Firestore listener)
    └── Prochaines instances Cloud Run chargeront la nouvelle base
```

---

## 8. API Backend — Endpoints spécifiques visualisation

En complément des endpoints définis dans DESIGN-preparation-vol-vfr.md, les endpoints suivants supportent le client Cesium :

### 8.1 Espaces aériens (visualisation)

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/airspaces/tile/{z}/{x}/{y}` | GET | Tuile GeoJSON des espaces aériens (si tiling dynamique) |
| `/api/airspaces/bbox` | GET | Espaces aériens dans un bounding box (lat_min, lon_min, lat_max, lon_max, alt_min, alt_max) |
| `/api/airspaces/{id}` | GET | Détail complet d'un espace (géométrie, volumes, fréquences, services) |
| `/api/airspaces/search` | GET | Recherche par nom, type, classe |

**Note** : si les tuiles sont pré-générées (recommandé), les endpoints `/tile/` redirigent vers GCS ou sont remplacés par un accès direct au bucket.

### 8.2 Analyse de route (visualisation)

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/route/{id}/analysis` | GET | Analyse complète : intersections + géométries des espaces pour rendu Cesium |
| `/api/route/{id}/profile` | GET | Données du profil vertical (terrain + route + espaces intersectés) |
| `/api/route/{id}/corridor` | GET | Géométrie du couloir de vol (buffer horizontal + vertical) pour affichage |

### 8.3 Aérodromes (visualisation)

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/aerodromes/bbox` | GET | Aérodromes dans un bounding box |
| `/api/aerodromes/tile/{z}/{x}/{y}` | GET | Tuile d'aérodromes (icônes sur carte) |

### 8.4 Format de réponse pour Cesium

Les endpoints de visualisation retournent du GeoJSON enrichi, directement consommable par Cesium :

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lon, lat], ...]]
      },
      "properties": {
        "identifier": "TMA PARIS 1",
        "airspace_type": "TMA",
        "airspace_class": "D",
        "lower_limit_ft": 1500,
        "upper_limit_ft": 4500,
        "color_html": "#0066CC",
        "color_kml": "FFCC6600",
        "intersection_type": "crosses",
        "services": [
          {
            "callsign": "PARIS APPROCHE",
            "type": "APP",
            "frequencies": ["119.250"]
          }
        ]
      }
    }
  ]
}
```

---

## 9. Client web — Architecture

### 9.1 Structure applicative

```
src/
├── components/
│   ├── globe/
│   │   ├── CesiumViewer.tsx         # Wrapper CesiumJS
│   │   ├── AirspaceLayer.tsx        # Couche espaces aériens
│   │   ├── RouteLayer.tsx           # Couche route + intersections
│   │   ├── AerodromeLayer.tsx       # Couche aérodromes
│   │   └── WeatherOverlay.tsx       # Overlay météo (vent, plafond)
│   ├── analysis/
│   │   ├── RouteAnalysisPanel.tsx   # Panneau résultats analyse
│   │   ├── AirspaceDetail.tsx       # Détail espace (fréquences, limites)
│   │   ├── VerticalProfile.tsx      # Profil vertical interactif
│   │   └── LegDetail.tsx            # Détail d'un leg (intersections, météo)
│   ├── route/
│   │   ├── RouteImport.tsx          # Upload KML
│   │   └── RouteEditor.tsx          # Édition waypoints/altitudes
│   └── common/
│       ├── LayerControl.tsx         # Toggle couches d'affichage
│       └── AiracBanner.tsx          # Notification cycle AIRAC
├── services/
│   ├── airspaceService.ts           # Client API espaces aériens
│   ├── routeService.ts              # Client API routes
│   ├── tileService.ts               # Chargement tuiles + cache
│   └── realtimeService.ts           # WebSocket / Firestore listeners
├── stores/
│   ├── mapStore.ts                  # État de la carte (viewport, couches)
│   ├── routeStore.ts                # Route active + analyse
│   └── airacStore.ts                # Cycle AIRAC courant
└── utils/
    ├── cesiumHelpers.ts             # Conversions GeoJSON → Cesium entities
    ├── colorScheme.ts               # Palette aviation (from airspace_colors.json)
    └── units.ts                     # Conversions ft/NM/kt
```

### 9.2 Gestion du cache client

```
┌─────────────────────────────────────────────────┐
│                 CACHE HIÉRARCHIQUE                │
│                                                   │
│  Niveau 1 : Mémoire (state React)               │
│  └── Entités Cesium déjà instanciées             │
│                                                   │
│  Niveau 2 : IndexedDB                            │
│  └── Tuiles GeoJSON par clé {airac}/{z}/{x}/{y}  │
│  └── Invalidé quand airac_cycle change           │
│                                                   │
│  Niveau 3 : Service Worker (optionnel)           │
│  └── Cache HTTP des requêtes GCS                 │
│                                                   │
│  Niveau 4 : CDN (Cloud Storage)                  │
│  └── Tuiles avec ETag basé sur cycle AIRAC       │
└─────────────────────────────────────────────────┘
```

---

## 10. Migration du code SkyPath

### 10.1 Code réutilisé directement

| Module SkyPath | Usage SkyWeb | Modifications |
|----------------|-------------|---------------|
| `workflow/extract/` | Pipeline ETL backend | Aucune |
| `workflow/validate/` | Pipeline ETL backend | Aucune |
| `workflow/load/` | Pipeline ETL backend | Aucune |
| `workflow/transform/spatial_indexer.py` | Pipeline ETL backend | Ajout phase 6 (génération tuiles) |
| `workflow/transform/altitude_converter.py` | Pipeline ETL backend | Aucune |
| `skypath_services/route_corrector/` | Service import route | Aucune |
| `skypath_services/airspace_coloring.py` | Configuration client | Export JSON uniquement |
| `core/spatialite_loader.py` | Si option B (SpatiaLite sur GCS) | Aucune |

### 10.2 Code adapté

| Module SkyPath | Adaptation | Raison |
|----------------|------------|--------|
| `skypath_services/airspace_api.py` | Chemin base configurable (GCS → local) | Le SQL reste identique (SpatiaLite inchangé) |
| `skypath_services/route_analyzer/analyzer.py` | Sortie JSON/GeoJSON au lieu de HTML/KML | Client web consomme du JSON |
| `skypath_services/kml_exporter.py` | Remplacé par tile generator | Plus de KML ; génération de tuiles GeoJSON/3D Tiles |
| `skypath_services/config/` | Migration vers GCP Secret Manager + env vars | Configuration cloud-native |

### 10.3 Code non repris

| Module SkyPath | Raison |
|----------------|--------|
| `cli/` | Remplacé par API REST + interface web admin |
| `gui/` | Remplacé par client web |
| Dépendance `customtkinter` | Desktop GUI inutile |
| Dépendance `matplotlib` | Profil altitude rendu côté client (Canvas/Chart) |

---

## 11. Plan de réalisation

### Phase 1 — Fondations

| Livrable | Description |
|----------|-------------|
| Backend API de base | FastAPI + Cloud Run, auth Firebase, health check |
| Base référence sur GCS | Pipeline ETL → skypath.db uploadée sur GCS, chargée par Cloud Run |
| Pipeline ETL adapté | Phases 0-5 fonctionnelles sur GCP |
| Client web minimal | CesiumJS globe avec terrain, navigation caméra |

### Phase 2 — Visualisation espaces aériens

| Livrable | Description |
|----------|-------------|
| Phase 6 ETL — Tiling | Génération tuiles GeoJSON par cycle AIRAC |
| Couche espaces aériens | Affichage sur globe Cesium, coloration, LOD |
| Détail espace | Click → panneau avec fréquences, services, limites |
| Performance | Viewport culling, LOD, cache IndexedDB |

### Phase 3 — Analyse de route

| Livrable | Description |
|----------|-------------|
| Import KML SDVFR | Upload + correction altitudes via API |
| Analyse espaces | `AirspaceQueryAPI` migrée, résultats JSON |
| Visualisation route | Route sur globe + espaces intersectés surlignés |
| Profil vertical | Vue coupe altitude avec terrain et espaces |

### Phase 4 — Fonctionnalités complètes

| Livrable | Description |
|----------|-------------|
| Météo le long de la route | Overlay Cesium + données dans profil vertical |
| Multi-utilisateurs | Auth, données isolées, notifications AIRAC |
| Notes VAC communauté | CRUD collaboratif |
| Interface admin | Pipeline AIRAC, activation cycle, monitoring |

---

## 12. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| **Performance Cesium avec 255k géométries** | Rendu lent, gel navigateur | Tiling + LOD + primitive batching (§4.3) |
| **Cold start Cloud Run** | Latence au premier appel (~200 Mo à charger depuis GCS) | Keep-alive minimum, pré-chargement, `min-instances=1` si budget le permet |
| **Latence API pour analyse route** | UX lente | Cache serveur + pré-calcul ; l'analyse SkyPath prend 1-5s, acceptable |
| **Taille des tuiles** | Bande passante | Compression gzip, simplification géométrique, chargement progressif |
| **Concurrence notes VAC** | Perte de données | Last-write-wins acceptable pour ce volume ; historique via `updated_at` |

---

## 13. Glossaire

| Terme | Définition |
|-------|------------|
| **AIRAC** | Aeronautical Information Regulation And Control — cycle de 28 jours pour les données aéronautiques |
| **SpatiaLite** | Extension SQLite pour les requêtes géospatiales |

| **LOD** | Level of Detail — technique d'affichage à résolution variable selon la distance |
| **3D Tiles** | Format OGC de tuiles 3D, nativement supporté par CesiumJS |
| **Viewport culling** | Ne charger/rendre que ce qui est visible dans le champ de la caméra |
| **Primitive batching** | Regrouper des entités en un seul appel GPU pour optimiser le rendu |

---

*Document créé le : 2026-02-02*
*Version : 0.2 — SpatiaLite/GCS comme choix par défaut (suppression option Cloud SQL/PostGIS)*
*Documents associés :*
- [SPEC-preparation-vol-vfr.md](SPEC-preparation-vol-vfr.md) — Spécification générale préparation vol
- [DESIGN-contracts.md](DESIGN-contracts.md) — Contrats de données
- [DESIGN-weather.md](DESIGN-weather.md) — Module météo
- [DESIGN-preparation-vol-vfr.md](DESIGN-preparation-vol-vfr.md) — Architecture technique
- [DESIGN-import-route-sdvfr.md](DESIGN-import-route-sdvfr.md) — Import route SD VFR
