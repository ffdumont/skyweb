# Plan : Architecture Stub-First pour SkyWeb

## Objectif

Créer une architecture maintenable et évolutive avec des **bouchons (stubs)** pour valider le design avant d'implémenter les intégrations réelles.

**Principe clé** : SkyWeb est un **orchestrateur** qui expose les services existants de skytools (NorthStar, SkyPath, SkyCheck, SkyVerify) via une API unifiée. Il ne recrée pas les modèles de données existants.

**Priorité** : Infrastructure GCP + Pipeline CI/CD + Authentification **avant** le code métier.

> Voir [DESIGN-preparation-vol-vfr.md](DESIGN-preparation-vol-vfr.md) pour le modèle de données détaillé et le mapping services → endpoints.

---

## 1. Infrastructure GCP (Phase 0)

### 1.1 Services GCP à provisionner

| Service | Usage | Justification |
|---------|-------|---------------|
| **Cloud Run** | API FastAPI | Serverless, scale to zero |
| **Cloud Storage** | Fichiers KML, exports | Upload/download fichiers |
| **Secret Manager** | Clés API (Météo-France, etc.) | Sécurité credentials |
| **Artifact Registry** | Images Docker | Registry privé |
| **Cloud Build** | CI/CD | Pipeline automatisé |
| **Firestore** (optionnel) | Données capitalisées VAC | NoSQL pour données utilisateur |

### 1.2 Organisation des données

#### Taxonomie des données

| Catégorie | Données | Cycle de vie | Partage |
|-----------|---------|--------------|---------|
| **Référence AIRAC** | Espaces aériens, AD (pistes, freq), zones R/D/P | 28 jours (cycle AIRAC) | Commun |
| **Référence enrichie** | Notes VAC capitalisées, sens TDP, altitudes circuit | Stable + corrections | Commun (communauté) |
| **Utilisateur - Routes** | KML importés, routes sauvegardées | Persistant | Privé |
| **Utilisateur - Vols** | Plan de vol, fiche préparation | Par vol | Privé |
| **Utilisateur - Météo vol** | METAR, TAF, vents le long de la route | Contextuel au vol | Privé |
| **Utilisateur - NOTAM vol** | NOTAM actifs pour la route | Contextuel au vol | Privé |
| **Utilisateur - Préférences** | Avion, base, paramètres | Persistant | Privé |

#### Architecture stockage

```
┌─────────────────────────────────────────────────────────────────┐
│                    DONNÉES DE RÉFÉRENCE                          │
│                    (partagées, read-only)                        │
├─────────────────────────────────────────────────────────────────┤
│  Cloud Storage: gs://skyweb-reference/                          │
│  ├── airac/                                                     │
│  │   ├── 2501/                    # Cycle AIRAC 2501            │
│  │   │   ├── xml_sia.xml          # Source XML SIA              │
│  │   │   ├── skypath.db           # Base SpatiaLite générée     │
│  │   │   └── metadata.json        # Date, hash, version         │
│  │   └── current -> 2501/         # Symlink cycle actif         │
│  │                                                              │
│  └── community/                   # Données enrichies communauté │
│      ├── vac_notes.json           # Notes VAC capitalisées      │
│      ├── tdp_database.json        # Sens TDP, altitudes circuit │
│      └── ad_supplements.json      # Infos AD hors XML SIA       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    DONNÉES UTILISATEUR                           │
│                    (privées, read-write)                         │
├─────────────────────────────────────────────────────────────────┤
│  Firestore: /users/{user_id}/                                   │
│  ├── profile                      # Préférences, avion par défaut│
│  ├── aircraft/{aircraft_id}       # Config avions (centrage)    │
│  ├── routes/{route_id}            # Routes sauvegardées         │
│  │   ├── name, waypoints, created_at                            │
│  │   └── kml_ref → Storage        # Référence fichier KML       │
│  └── flights/{flight_id}          # Plans de vol                │
│      ├── route_ref, date                                        │
│      ├── weather_snapshot         # Météo figée pour ce vol     │
│      ├── notam_snapshot           # NOTAM figés pour ce vol     │
│      ├── airspace_analysis        # Zones traversées (calculé)  │
│      ├── prep_sheet_ref → Storage # Fiche générée               │
│      └── status (draft/ready/completed)                         │
│                                                                 │
│  Cloud Storage: gs://skyweb-users/{user_id}/                    │
│  ├── routes/                      # Fichiers KML bruts          │
│  ├── exports/                     # PDF/Markdown générés        │
│  └── uploads/                     # Fichiers temporaires        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    CACHE TECHNIQUE                               │
│                    (optimisation, pas de données métier)         │
├─────────────────────────────────────────────────────────────────┤
│  Redis (Memorystore) ou Cache in-memory:                        │
│  ├── api_response:{hash}          # Cache réponses API externes │
│  └── session:{token}              # Sessions utilisateur        │
│                                                                 │
│  Note: La météo et les NOTAM sont stockés avec le vol           │
│  (Firestore flight.weather_snapshot, flight.notam_snapshot)     │
│  car ils sont contextuels à la route et à la date du vol.       │
└─────────────────────────────────────────────────────────────────┘
```

#### Administration des données partagées

Les données de référence nécessitent des fonctions d'administration distinctes des fonctions utilisateur.

| Fonction | Fréquence | Déclencheur | Action |
|----------|-----------|-------------|--------|
| **MAJ cycle AIRAC** | 28 jours | Manuel ou scheduled | Upload XML SIA → Génère skypath.db → Publie nouveau cycle |
| **Bascule cycle actif** | 28 jours | Manuel | Met à jour symlink `current` vers nouveau cycle |
| **MAJ notes VAC** | Ponctuel | Manuel | Édition vac_notes.json, tdp_database.json |
| **Rollback cycle** | Exceptionnel | Manuel | Repointe `current` vers cycle précédent |

```
┌─────────────────────────────────────────────────────────────────┐
│                    API ADMINISTRATION                            │
│                    (accès restreint, rôle admin)                 │
├─────────────────────────────────────────────────────────────────┤
│  POST /admin/airac/upload         # Upload nouveau XML SIA      │
│       → Valide XML                                              │
│       → Génère skypath.db (pipeline SkyPath)                    │
│       → Stocke dans gs://skyweb-reference/airac/{cycle}/        │
│                                                                 │
│  POST /admin/airac/activate       # Active un cycle             │
│       → Vérifie intégrité                                       │
│       → Met à jour pointeur "current"                           │
│       → Log audit                                               │
│                                                                 │
│  GET  /admin/airac/list           # Liste cycles disponibles    │
│  GET  /admin/airac/current        # Cycle actif + metadata      │
│                                                                 │
│  PUT  /admin/community/vac-notes  # MAJ notes VAC               │
│  PUT  /admin/community/tdp        # MAJ base TDP                │
│  GET  /admin/community/export     # Export données communauté   │
└─────────────────────────────────────────────────────────────────┘

Authentification admin:
- Firebase Auth avec custom claim "role": "admin"
- Ou service account pour jobs automatisés (Cloud Scheduler)
```

**Pipeline MAJ AIRAC** (manuel ou Cloud Scheduler) :
```
1. Télécharger XML SIA depuis data.gouv.fr
2. POST /admin/airac/upload (avec XML)
3. Backend:
   - Valide structure XML
   - Exécute pipeline SkyPath (extract → load → transform)
   - Génère skypath.db
   - Upload vers gs://skyweb-reference/airac/{cycle}/
   - Crée metadata.json (date, hash, stats)
4. POST /admin/airac/activate (cycle={cycle})
5. Notifications utilisateurs (optionnel)
```

#### Flux de données typique (préparation vol)

```
1. Import route KML
   └─→ Stocké dans gs://skyweb-users/{user_id}/routes/
   └─→ Metadata dans Firestore /users/{user_id}/routes/{id}

2. Analyse espaces aériens
   └─→ Lecture gs://skyweb-reference/airac/current/skypath.db
   └─→ Résultat calculé à la volée (pas stocké)

3. Récupération données AD
   └─→ XML SIA (référence) + community/vac_notes.json (enrichi)
   └─→ Fusionné à la volée

4. Météo
   └─→ API externe → Cache Redis (TTL court)
   └─→ Snapshot sauvé dans Firestore flight.weather_snapshot

5. Génération fiche préparation
   └─→ Assemblage données 1-4
   └─→ PDF stocké gs://skyweb-users/{user_id}/exports/
   └─→ Référence dans Firestore flight.prep_sheet_ref
```

### 1.3 Authentification : Firebase Auth ✅

**Choix retenu** : Firebase Auth
- Création de compte email/password
- Google Sign-In
- Gratuit jusqu'à 50k utilisateurs/mois
- Intégré GCP

**Flux** :
```
Client → Firebase Auth (email ou Google) → JWT Token → Cloud Run (vérification)
```

**Configuration Firebase** :
1. Créer projet Firebase (ou lier au projet GCP existant)
2. Activer Authentication avec providers : Email/Password + Google
3. Récupérer la config Firebase pour le frontend (si applicable)
4. Backend vérifie les JWT via Firebase Admin SDK

### 1.4 Pipeline CI/CD (Cloud Build)

```yaml
# cloudbuild.yaml
steps:
  # 1. Tests
  - name: 'python:3.11'
    entrypoint: 'bash'
    args: ['-c', 'pip install -e .[test] && pytest']

  # 2. Build image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_REGION}-docker.pkg.dev/${PROJECT_ID}/skyweb/api:$COMMIT_SHA', '.']

  # 3. Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGION}-docker.pkg.dev/${PROJECT_ID}/skyweb/api:$COMMIT_SHA']

  # 4. Deploy to Cloud Run
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'skyweb-api'
      - '--image=${_REGION}-docker.pkg.dev/${PROJECT_ID}/skyweb/api:$COMMIT_SHA'
      - '--region=${_REGION}'
      - '--platform=managed'
```

---

## 2. Structure du Projet (mise à jour)

```
skyweb/
├── pyproject.toml
├── Dockerfile
├── cloudbuild.yaml
├── .env.example
│
├── infra/                     # Infrastructure as Code
│   ├── terraform/             # Provisioning GCP (optionnel)
│   └── scripts/
│       ├── setup_gcp.sh       # Script setup initial
│       └── deploy.sh          # Deploy manuel
│
├── config/
│   ├── config.py              # ConfigManager
│   ├── config.toml            # Config par défaut
│   └── settings.py            # Env-based settings
│
├── core/
│   ├── contracts/             # Dataclasses
│   │   ├── route.py
│   │   ├── airspace.py
│   │   ├── aerodrome.py
│   │   ├── weather.py
│   │   ├── notam.py
│   │   └── result.py
│   │
│   ├── protocols/             # Interfaces
│   │   └── ...
│   │
│   └── auth/                  # Authentification
│       ├── firebase.py        # Firebase Auth client
│       └── middleware.py      # FastAPI auth middleware
│
├── services/
│   ├── factory.py
│   ├── storage/               # Nouveau: abstraction stockage
│   │   ├── storage_service.py
│   │   ├── gcs_storage.py     # Google Cloud Storage
│   │   └── local_storage.py   # Dev local
│   ├── route/
│   ├── airspace/
│   ├── weather/
│   ├── aerodrome/
│   ├── notam/
│   └── export/
│
├── api/
│   ├── main.py
│   ├── dependencies.py        # DI + auth
│   └── routes/
│
├── data/
│   └── stub_responses/
│       └── LFXU-LFFU/         # Données exemple route réelle
│
└── tests/
```

---

## 3. Plan d'Implémentation Révisé

### Phase 0 : Infrastructure GCP (à faire maintenant)

**0.1 Setup GCP**
- [ ] Créer projet GCP (ou utiliser existant)
- [ ] Activer APIs : Cloud Run, Storage, Secret Manager, Artifact Registry, Cloud Build
- [ ] Créer bucket `skyweb-data` avec structure (static/, user-data/, stub-data/)
- [ ] Configurer Artifact Registry pour images Docker

**0.2 Firebase Auth**
- [ ] Créer/lier projet Firebase
- [ ] Activer providers : Email/Password + Google
- [ ] Noter les credentials pour le backend

**0.3 Pipeline CI/CD**
- [ ] Créer `Dockerfile` minimal (FastAPI hello world)
- [ ] Créer `cloudbuild.yaml`
- [ ] Connecter repo Git à Cloud Build
- [ ] Configurer trigger (push sur main → deploy)

**0.4 Validation**
- [ ] Push test → build + deploy automatique
- [ ] Vérifier endpoint `/health` accessible

### Phase 1 : Fondations Code

- [ ] `pyproject.toml` avec dépendances
- [ ] `core/contracts/result.py` (ServiceResult)
- [ ] `core/contracts/route.py` (basé sur exemple LFXU-LFFU)
- [ ] `config/config.py` (ConfigManager)
- [ ] `services/factory.py` (ServiceFactory)
- [ ] `services/storage/` (abstraction GCS/local)
- [ ] `api/main.py` avec endpoint health check
- [ ] Tests basiques

### Phase 2 : Authentification

- [ ] `core/auth/firebase.py`
- [ ] `core/auth/middleware.py`
- [ ] Endpoints protégés
- [ ] Tests auth

### Phase 3+ : Services métier (stubs puis réel)

(Comme plan précédent : Route → Airspace → Weather → Aerodrome → NOTAM → Export)

---

## 4. Données Stub : Route LFXU-LFFU

Basé sur l'exemple existant dans SkyPath, créer :
- `data/stub_responses/LFXU-LFFU/route.json`
- `data/stub_responses/LFXU-LFFU/airspaces.json`
- `data/stub_responses/LFXU-LFFU/weather.json`

---

## 5. Vérification Phase 0

1. **Cloud Build** : Push sur main déclenche build + deploy
2. **Cloud Run** : API accessible via URL publique
3. **Health check** : `GET /health` retourne 200
4. **Auth** : Endpoint protégé rejette requêtes sans token

```bash
# Test health
curl https://skyweb-api-xxx.run.app/health

# Test auth (doit échouer)
curl https://skyweb-api-xxx.run.app/api/routes

# Test auth (avec token)
curl -H "Authorization: Bearer $TOKEN" https://skyweb-api-xxx.run.app/api/routes
```

---

## Décisions Prises

| Question | Décision |
|----------|----------|
| Authentification | Firebase Auth (email + Google Sign-In) |
| Infrastructure as Code | Scripts manuels (gcloud) |
| Données stub | Route LFXU-LFFU existante dans SkyPath |
