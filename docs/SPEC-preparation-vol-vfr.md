# Spécification Générale - Automatisation Préparation Vol VFR

## 1. Objectif

Développer un outil d'aide à la préparation de vols VFR permettant de collecter automatiquement les informations nécessaires à partir de sources officielles et de pré-remplir les documents de navigation.

**Contexte utilisateur** : Pilote VFR basé en région parisienne (LFXU - Les Mureaux), utilisant un CT-LS (F-HBCT) et/ou DR400-120, avec un système Excel existant très complet pour le log de navigation et les calculs.

**Déploiement cible** : Google Cloud Platform (GCP)

---

## 2. Analyse du système existant (Log Nav V2)

### 2.1 Structure actuelle du fichier Excel

Le fichier `Modèle Log Nav V2.xlsx` contient **17 feuilles** :

| Feuille | Fonction | Automatisation possible |
|---------|----------|------------------------|
| `fplAlign` | Import plan de vol (SkyDemon/Garmin) | 🎯 Point d'entrée |
| `LOG` | Log de navigation imprimable | ⚡ Sortie générée |
| `CALCULS BRANCHES` | Calculs par segment (Rm, Cm, Vs, Tv, F) | ✅ Automatisable |
| `WAYPOINTS` | Base de données waypoints (lat/lon) | ✅ Enrichissable |
| `FREQUENCES` | Répertoire fréquences radio | ✅ Automatisable |
| `CARBURANT` | Bilan carburant réglementaire | ✅ Automatisable |
| `CTLS_FF` | Consommation CT-LS | 📋 Configuration |
| `AUTONOMIE` | Calcul autonomie | ✅ Automatisable |
| `CTLS_CENTRAGE` | Masse & centrage CT-LS | ⚠️ Saisie partielle |
| `DR400_CENTRAGE` | Masse & centrage DR400-120 | ⚠️ Saisie partielle |
| `CTLS-LSA_PERFORMANCE` | Abaques performances CT-LS | ✅ Déjà numérisés ! |
| `DR400120_PERFORMANCE` | Abaques performances DR400 | ✅ Déjà numérisés ! |
| `PERFORMANCE` | Calculs performances actuels | ✅ Automatisable |
| `WINTEM` | Données vent/température | 🌤️ Source météo |
| `TRIANGULATION CARTE` | Outil géométrique | 🔧 Utilitaire |
| `BILAN ACTIVITE` | Suivi heures de vol | 📊 Reporting |
| `READ ME !` | Documentation | 📖 Info |

### 2.2 Données calculées automatiquement (feuille CALCULS BRANCHES)

| Colonne | Description | Formule/Source |
|---------|-------------|----------------|
| `From` / `To` | Waypoints segment | Import FPL |
| `HE` / `HR` | Heure estimée / réelle | Calcul cumulé |
| `Compteur` | Hobbs estimé | Calcul |
| `Dist (NM)` | Distance segment | Coordonnées WPT |
| `Rv (°)` | Route vraie | Coordonnées WPT |
| `Dm (°)` | Déclinaison magnétique | À automatiser (WMM) |
| `Zi` | Altitude segment | Saisie / Import |
| `TAS (KTS)` | Vitesse vraie | Fonction altitude |
| `Ve (KTS)` | Composante vent effectif | Calcul trigonométrique |
| `Vs (KTS)` | Vitesse sol | TAS ± Ve |
| `X (°)` | Dérive | Calcul trigonométrique |
| `FF (L/H)` | Fuel flow | Config avion |
| `Cm (°)` | Cap magnétique | Rv + Dm + X |
| `T (MIN)` | Temps sans vent | D / TAS |
| `Tw (MIN)` | Temps avec vent | D / Vs |
| `F (L)` / `Fw (L)` | Carburant segment | FF × T |
| `ReqFuel` | Réserve requise segment | Calcul |
| `BurnedFuel` | Carburant brûlé cumulé | Somme |

### 2.3 Avions configurés

**CT-LS F-HBCT** :
- Masse à vide : 352.3 kg
- Bras de levier carburant : 210 mm
- Abaques performances numérisés (distances décollage/atterrissage par altitude-densité et masse)
- Coefficients correcteurs : usure (1.1), expérience pilote (1.15), herbe haute, pente, vent arrière...

**DR400-120 F-GSRK** :
- Masse à vide : 577.5 kg
- 4 places (pilote, passager AV, passagers AR)
- Abaques par température (-20°C à +20°C) et altitude-densité (0 à 8000 ft)
- Corrections : vent effectif, type de surface (dur/herbe)

---

## 3. Inventaire des informations automatisables

### 3.1 Données aérodromes (priorité haute)

| Information | Source | Automatisable | Existant |
|-------------|--------|---------------|----------|
| Code OACI | SIA / OpenAIP | ✅ | Via FPL |
| Coordonnées | SIA / OpenAIP | ✅ | WAYPOINTS |
| Altitude terrain | VAC / OpenAIP | ✅ | ❌ À ajouter |
| Fréquences | VAC / SIA | ✅ | FREQUENCES (manuel) |
| Pistes (QFU, longueur) | VAC | ✅ | ❌ À ajouter |
| TODA / LDA | VAC | ✅ | ❌ À ajouter |
| Altitude TDP | VAC | ✅ | ❌ À ajouter |
| NOTAM | Olivia/SIA | ✅ | ❌ À ajouter |

### 3.2 Données espaces aériens

| Information | Source | Automatisable | Existant |
|-------------|--------|---------------|----------|
| Zones traversées | OpenAIP / SIA | ✅ | ❌ Manuel |
| Classe d'espace | OpenAIP / SIA | ✅ | ❌ Manuel |
| Limites verticales | OpenAIP / SIA | ✅ | ❌ Manuel |
| Fréquences secteur | SIA | ✅ | FREQUENCES |
| MSA (altitude mini sûreté) | Calcul terrain | ✅ | ❌ À ajouter |

### 3.3 Données météorologiques

| Information | Source | Automatisable | Usage |
|-------------|--------|---------------|-------|
| METAR | Aeroweb / OGIMET | ✅ | QNH, vent sol |
| TAF | Aeroweb | ✅ | Prévisions |
| Vent en altitude | WINTEM / Open-Meteo | ✅ | Calcul Cm, Vs |
| Température altitude | WINTEM / Open-Meteo | ✅ | Altitude-densité |
| QNH | METAR | ✅ | Altimétrie |
| TEMSI / Cartes | Aeroweb | ⚠️ Images | Affichage |

### 3.4 Calculs navigation (déjà implémentés dans Excel)

| Calcul | Automatisable | État |
|--------|---------------|------|
| Distance segment | ✅ | ✅ Fait |
| Route vraie/magnétique | ✅ | ✅ Fait |
| Dérive, Cap magnétique | ✅ | ✅ Fait |
| Vitesse sol | ✅ | ✅ Fait |
| Temps de vol | ✅ | ✅ Fait |
| Carburant | ✅ | ✅ Fait |
| Heures estimées | ✅ | ✅ Fait |

### 3.5 Performances (déjà implémentées)

| Calcul | Automatisable | État |
|--------|---------------|------|
| Distance décollage | ✅ | ✅ Abaques numérisés |
| Distance atterrissage | ✅ | ✅ Abaques numérisés |
| Coefficients correcteurs | ✅ | ✅ Configurés |

---

## 4. Informations nécessitant saisie manuelle

| Information | Raison |
|-------------|--------|
| Choix de la route / waypoints | Décision pilote |
| Altitude de croisière par segment | Décision pilote |
| Masse pilote / passagers / bagages | Variable par vol |
| Carburant au roulage | Jauge avion |
| Heure de départ prévue | Planning |
| Conditions piste (herbe haute, humide...) | Observation |
| Décision GO/NO-GO | Jugement pilote |

---

## 5. Sources de données identifiées

### 5.1 Projet SkyPath existant (`C:\Users\franc\dev\skytools\skypath`)

**Projet mature et production-ready** avec :

| Composant | Description | Réutilisable |
|-----------|-------------|--------------|
| **AirspaceQueryAPI** | Requêtes 3D espaces aériens (SpatiaLite) | ✅ Clé |
| **RouteAnalyzerService** | Analyse segments vs espaces | ✅ Clé |
| **KMLPointsExtractor** | Extraction/correction routes KML SD VFR | ✅ Clé |
| **ElevationService** | Élévations multi-sources (Google, IGN) | ✅ |
| **Pipeline ETL** | Chargement XML SIA → SQLite/SpatiaLite | ✅ |
| **Base SkyPath** | 3,941 espaces aériens français (données XML SIA) | ✅ |

> **Fonctionnement SkyPath** : Le XML SIA est téléchargé manuellement depuis data.gouv.fr, puis chargé dans une base SQLite avec extension SpatiaLite pour les requêtes géospatiales. Ce n'est pas une API temps réel.

**Capacités existantes :**
- ✅ Import KML depuis SD VFR
- ✅ Correction altitudes (élévations sol + interpolation montée/descente)
- ✅ Détection zones traversées (TMA, CTR, SIV, D, R, P, etc.)
- ✅ Classes OACI et limites verticales
- ✅ Export KML 3D Google Earth
- ✅ Coloration standardisée aviation

### 5.2 Sources officielles françaises

| Source | Accès | Données | État |
|--------|-------|---------|------|
| **XML SIA** | ✅ Téléchargement data.gouv.fr | Espaces, pistes, aérodromes | ✅ Exploité par SkyPath |
| VAC (PDF) | ❌ Pas de données structurées | Cartes, procédures | Manuel |
| SOFIA-Briefing | ❌ Interface web uniquement | NOTAM, SUP AIP | Pas d'accès programmatique |
| Aeroweb | Compte requis | METAR, TAF, TEMSI, WINTEM | Alternative |

> **Note** : Le terme "API SIA" est un abus de langage. Le SIA fournit des fichiers XML statiques (`XML_SIA_aaaa-mm-jj.xml`) mis à jour tous les cycles AIRAC (28 jours). SkyPath charge ce XML et l'exploite via une base SQLite/SpatiaLite.

### 5.3 APIs météo disponibles

| Source | API | Données | Accès |
|--------|-----|---------|-------|
| **Open-Meteo** | REST gratuit | Vents altitude, température, plafond | ✅ Confirmé |
| **Météo-France** | API publique | METAR, TAF, données officielles | ✅ Confirmé |
| OGIMET | Web scraping | METAR/TAF historiques | Backup |

### 5.4 Import depuis applications

| Application | Format | Usage |
|-------------|--------|-------|
| **SD VFR Next** | **KML** | ✅ Point d'entrée principal |
| Garmin | FPL | Export final (via conversion) |

---

## 6. Workflow utilisateur cible

### 6.1 Point de départ : SD VFR Next

L'utilisateur prépare sa route sur **SD VFR Next** qui fournit :
- Liste des waypoints (codes OACI, points utilisateur)
- Coordonnées géographiques
- Export possible (format à confirmer : FPL Garmin ? GPX ? CSV ?)

### 6.2 APIs disponibles confirmées

| API | Accès | Données exploitables |
|-----|-------|---------------------|
| **API SIA** | ✅ Disponible | VAC, NOTAM, SUP AIP, espaces aériens |
| **Open-Meteo** | ✅ Gratuit | Vents altitude, température, prévisions |
| **Météo-France** | ✅ Disponible | METAR, TAF, données officielles |

### 6.3 Flux de données envisagé

```
┌─────────────────┐
│  SD VFR Next    │──── Export route (waypoints, altitudes)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              OUTIL D'AUTOMATISATION                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   API SIA    │  │  Open-Meteo  │  │ Météo-France │  │
│  │              │  │              │  │              │  │
│  │ • VAC        │  │ • Vent alt.  │  │ • METAR      │  │
│  │ • NOTAM      │  │ • Temp alt.  │  │ • TAF        │  │
│  │ • Espaces    │  │ • Prévisions │  │ • QNH        │  │
│  │ • Fréquences │  └──────────────┘  └──────────────┘  │
│  └──────────────┘                                       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │            MOTEUR DE CALCUL                        │ │
│  │  • Navigation (Cm, Vs, Tv, dérive)                │ │
│  │  • Carburant (étapes + réserves)                  │ │
│  │  • Performances (distances T/O, L/D)              │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                    SORTIES                               │
│                                                          │
│  • Mise à jour Excel "Log Nav V2" existant              │
│  • Ou génération nouveau fichier pré-rempli             │
│  • Export fiche préparation vol (Markdown/PDF)          │
│  • Checklist items restants à vérifier                  │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Priorités utilisateur (confirmées)

### Priorité 1 : Informations segments / Zones traversées (section 1.3 du 4120)

**Objectif** : Pour chaque segment de la route, récupérer automatiquement :

| Information | Source | Existant dans SkyPath |
|-------------|--------|----------------------|
| Zones traversées (indicatif) | XML SIA | ✅ RouteAnalyzerService |
| Classe d'espace | XML SIA | ✅ AirspaceQueryAPI |
| Limites verticales | XML SIA | ✅ Normalisé ft AMSL |
| Fréquences | XML SIA | ✅ Table `Frequence` |
| MSA / Zmax | Calcul élévation | ✅ ElevationService |
| Contournements suggérés | À développer | ❌ |
| SUP AIP | Eurocontrol EAD | ❌ Non inclus dans XML SIA |
| NOTAM | Eurocontrol EAD / ICAO | ❌ Non inclus dans XML SIA |

### Priorité 2 : Caractéristiques aérodromes (section 2 du 4120)

| Information | Source | Existant |
|-------------|--------|----------|
| Code OACI | KML SD VFR | ✅ |
| Indicatif appel | XML SIA (AD) | ⚠️ ADExtractor existe |
| Fréquence | XML SIA | ⚠️ À extraire |
| Altitude terrain | XML SIA / Elevation | ✅ |
| Pistes (QFU, longueur) | XML SIA | ⚠️ À extraire |
| TODA / LDA | XML SIA | ⚠️ À extraire |
| Altitude circuit | VAC (manuel) | ❌ Non dans XML SIA |
| Consignes particulières | VAC (PDF manuel) | ❌ |
| NOTAM AD | Eurocontrol EAD / ICAO | ❌ Non dans XML SIA |

### Priorité 3 : Tâches "avant J-4" (section 6 du 4120)

Automatiser au maximum la checklist de préparation :

| Tâche | Automatisable | Comment |
|-------|---------------|---------|
| Tracé initial (SD VFR) | ✅ | Import KML |
| Sélection AD dégagements | ⚠️ | Suggérer AD proches route |
| Analyse VAC | ❌ | PDF manuel |
| Analyse segments (zones, fréquences) | ✅ | SkyPath existant |
| Initialisation Log de Nav | ✅ | Export vers Excel |
| Briefing Arrivée | ⚠️ | Pré-remplir données disponibles |
| Export FPL Garmin | ✅ | Conversion KML → FPL |
| Bilan centrage | ⚠️ | Saisie masses requise |
| Distances T/O & L/D | ✅ | Si conditions connues |

### Priorité 4 : Météo le long de la route

| Information | Source | Usage |
|-------------|--------|-------|
| Vent en altitude | Open-Meteo | Calcul Cm, Vs, Tv |
| Température altitude | Open-Meteo | Altitude-densité |
| Plafond nuageux | Open-Meteo / MF | Conditions VFR |
| METAR | Météo-France | QNH, vent sol |
| TAF | Météo-France | Prévisions |

---

## 8. Questions ouvertes

### 8.1 NOTAM - Sources identifiées ✅

#### Option 1 : Eurocontrol EAD (recommandé pour l'Europe) 🇪🇺

**[European AIS Database (EAD)](https://www.eurocontrol.int/service/european-ais-database)** - Base centralisée de référence

| Accès | Description | Prérequis |
|-------|-------------|-----------|
| **EAD Pro (B2C)** | Interface web prête à l'emploi | Compte EAD |
| **MyEAD (B2B)** | API AIMSL (web services) | Agreement + développement |

**Données disponibles** :
- NOTAM internationaux (séries mondiales)
- SNOWTAM, ASHTAM
- PIB (Pre-flight Information Bulletins)
- Format AIXM 5.1 (Digital NOTAM)

**Types de briefing** :
- Par aérodrome, zone ou rayon
- Par route (départ/destination + FIR)
- Par route étroite (plan de vol)

**Accès B2B (MyEAD)** :
- Signature d'un "EAD Data User Agreement"
- Documentation technique API fournie
- 2 certificats gratuits, puis 200€/certificat
- Équipe dédiée pour l'intégration

**⚠️ À valider** : Coût réel pour usage personnel/non-commercial ? Prévoir prototype pour évaluer.

**Contact** : https://www.ead.eurocontrol.int/

---

#### Option 2 : ICAO API Data Service

**https://applications.icao.int/dataservices/**

| API | Description | Mise à jour |
|-----|-------------|-------------|
| **Stored NOTAMs** | Par État/location, filtrable par Q-code | Toutes les 3h |
| **Realtime NOTAMs** | Par location (liste requise) | Temps réel |

**Tarification** :
- 100 appels gratuits à l'inscription
- Booster packs jusqu'à 40k appels
- Option appels illimités (contacter ICAOAPI@icao.int)

---

#### Alternatives tierces

| Service | Avantage | Lien |
|---------|----------|------|
| [Notamify](https://notamify.com/notam-api) | API V2, interprétation enrichie | Endpoints publics |
| [Aviation Edge](https://aviation-edge.com/notam-api/) | Temps réel | Commercial |
| [Laminar Data](https://developer.laminardata.aero/documentation/notamdata/v2) | GeoJSON | Commercial |

---

#### France - SOFIA-Briefing (pas d'API)

- Interface web : https://sofia-briefing.aviation-civile.gouv.fr/
- Mise à jour novembre 2025
- Pas d'accès programmatique documenté

### 8.2 Données VAC

Les VAC sont des PDF, pas de données structurées exploitables automatiquement.

**Approche retenue** :
- **XML SIA** : Exploiter au maximum les données disponibles (pistes, fréquences, altitude terrain)
- **Capitalisation manuelle** : Permettre de saisir et stocker les informations extraites manuellement des VAC

#### Analyse VAC selon le manuel de préparation

**Caractéristiques AD** :
| Information | Dans XML SIA | À capitaliser |
|-------------|--------------|---------------|
| Ouverture CAP / Usage Restreint | ✅ | - |
| Altitude terrain | ✅ | - |
| Indicatif d'appel | ✅ | - |
| Fréquences (info, contrôle) | ✅ | - |
| TODA / ASDA / LDA | ✅ | - |
| Déclivité piste | ✅ | - |
| Aires de circulation / stationnement | ❌ | ✅ (texte) |
| Horaires services ATS | ✅ | - |
| Horaires avitaillement | ❌ | ✅ |

**Éléments exploités en vol** :
| Information | Dans XML SIA | À capitaliser |
|-------------|--------------|---------------|
| Points/repères au sol | ❌ | ✅ |
| Obstacles (direction, distance) | ❌ | ✅ |
| AD et Navaids au voisinage | ✅ (partiel) | ✅ |
| Géométrie circuit de piste | ✅ (calculable) | - |
| Altitude/hauteur circuit | ✅ (base existante) | - |
| Sens du TDP | ✅ (base existante) | - |
| Périmètres urbanisés à éviter | ❌ | ✅ |
| Aire à signaux | ❌ | ✅ |
| Piste préférentielle | ❌ | ✅ |
| QFU(s) / Points d'entrée piste | ✅ | - |
| Pente PAPI | ❌ | ✅ |

> **Note** : Un algorithme de calcul de circuit de piste (export KML) existe déjà, basé sur les points d'entrée de piste et QFU du XML SIA. À réutiliser.

**Consignes particulières** :
| Information | À capitaliser |
|-------------|---------------|
| Activités spéciales (para, voltige) | ✅ |
| VFR Spécial (si CTR) - minima météo | ✅ |
| Points de compte-rendu | ✅ |
| Itinéraires arrivée/départ | ✅ |
| Procédure panne radio | ✅ |
| Intégration circuit | ✅ |

**Format de stockage** : Base locale (JSON/SQLite) indexée par code OACI, enrichie progressivement par l'utilisateur lors de chaque nouvelle destination.

> **Données existantes** : Une base de données sur les sens et altitudes TDP existe déjà (format Excel). À convertir/intégrer.

### 8.3 SUP AIP - Sources identifiées ✅

#### Eurocontrol EAD PAMS (Published AIP Management System)

L'EAD inclut les SUP AIP via le service **PAMS** :

| Données | Format | Accès |
|---------|--------|-------|
| AIPs complets | PDF/XML | EAD Basic (gratuit) |
| Amendments (AMDT) | PDF | EAD Basic |
| **Supplements (SUP)** | PDF | EAD Basic |
| AICs | PDF | EAD Basic |
| Charts | PDF | EAD Basic |

**Structure par pays** : Chaque État a sa structure documentaire (AIC, AIP, AMDT, Charts, SUP).

**Accès** :
- **EAD Basic** (gratuit) : https://www.ead.eurocontrol.int/ - consultation en ligne
- **MyEAD (B2B)** : API pour récupération automatisée (nécessite agreement)
- **EAD IFS** : Téléchargement par cycle AIRAC

#### SIA France - Pas de SUP AIP en XML

Le XML SIA (`XML_SIA_aaaa-mm-jj.xml`) ne contient **pas** les SUP AIP :
- Contient : espaces aériens, aérodromes, pistes, fréquences
- Ne contient pas : SUP AIP, NOTAM

**SUP AIP France disponibles sur** :
- [SOFIA-Briefing](https://sofia-briefing.aviation-civile.gouv.fr/sofia/pages/otherssupaip.html) - Interface web
- Site SIA - Téléchargement PDF manuel
- Eurocontrol EAD - Accès centralisé

#### Catégories SUP AIP France

| Catégorie | Zone |
|-----------|------|
| SUP AIP Métropole | France métropolitaine |
| SUP AIP CAR SAM NAM | Caraïbes, Amérique du Sud/Nord |
| SUP AIP PAC N | Pacifique Nord |
| SUP AIP PAC P | Pacifique |
| SUP AIP RUN | La Réunion |

---

## 9. Documents associés

| Document | Contenu |
|----------|---------|
| [DESIGN-preparation-vol-vfr.md](DESIGN-preparation-vol-vfr.md) | Architecture technique, stack, endpoints API |
| [PLAN-preparation-vol-vfr.md](PLAN-preparation-vol-vfr.md) | Périmètre MVP, phases, prochaines étapes |

---

*Document créé le : 2026-01-21*
*Version : 0.4 - Séparation spec / design / plan*
