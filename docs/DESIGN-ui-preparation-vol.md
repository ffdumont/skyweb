# Design Interface - Préparation Vol VFR

## 1. Concept central : le Dossier de Vol

### 1.1 Définition

Le **Dossier de Vol** est l'entité centrale de SkyWeb. Il regroupe l'ensemble des données nécessaires à la préparation d'un vol VFR, depuis l'import de la route jusqu'à la génération des documents de navigation.

Un Dossier de Vol est un **agrégat CRUD** : il peut être créé, dupliqué, modifié, archivé et supprimé. Il est autonome — toutes les données collectées au moment de la préparation sont gelées (snapshot) pour constituer un dossier de référence consultable après le vol.

### 1.2 Composition

```
Dossier de Vol
├── Contexte
│   ├── Route (référence ou copie)
│   ├── Avion (immatriculation, type, config)
│   ├── Date/heure de départ prévue
│   ├── Équipage (PIC, passagers avec masses)
│   └── AD de dégagement sélectionnés
│
├── Invariants (données stables, indépendantes de la date)
│   ├── Caractéristiques des aérodromes (SIA + notes VAC)
│   ├── Espaces aériens traversés (zones, classes, limites)
│   ├── Segments de route (Rv, Rm, Dis, ΣDis)
│   ├── Fréquences radio ordonnées sur la route
│   └── Profil de vol (relief, surfaces 3000ft ASFC, TA)
│
├── Variables (données dépendant de la date/heure du vol)
│   ├── Météo (METAR, TAF, vents altitude, températures)
│   ├── NOTAM / AZBA / SUP AIP
│   ├── Éléments de navigation (Cm, X, Te, Vsol par segment)
│   ├── Bilan carburant (EMN, délestage, autonomie)
│   ├── Masse et centrage (départ et arrivée)
│   └── Performances (TOD, LD, vent travers, HCS)
│
├── Analyse
│   ├── Évaluation GO/NO-GO
│   ├── Analyse TEM (menaces, erreurs, contremesures)
│   └── Alertes et contraintes identifiées
│
└── Documents générés
    ├── Journal de navigation (lognav)
    ├── Fiche préparation 4120
    ├── Export FPL Garmin
    └── Checklist emport
```

### 1.3 Cycle de vie

| Statut | Description | Transitions possibles |
|--------|-------------|----------------------|
| **Brouillon** | Dossier créé, route importée, données incomplètes | → En préparation |
| **En préparation** | Collecte de données en cours (météo, NOTAM, calculs) | → Prêt, → Brouillon |
| **Prêt** | Toutes les sections complètes, documents générables | → Archivé, → En préparation |
| **Archivé** | Vol effectué ou dossier clos, lecture seule | → (suppression) |

### 1.4 Opérations CRUD

| Opération | Description |
|-----------|-------------|
| **Créer** | Nouveau dossier vierge ou à partir d'un import KML |
| **Dupliquer** | Copie d'un dossier existant (même route, nouvelle date) — conserve les invariants, vide les variables |
| **Modifier** | Édition libre de toutes les sections tant que le dossier n'est pas archivé |
| **Archiver** | Passage en lecture seule après le vol |
| **Supprimer** | Suppression définitive (avec confirmation) |

---

## 2. Architecture des vues

### 2.1 Layout principal

L'application comporte deux niveaux de navigation :

**Niveau 1 — Barre de navigation supérieure (app-level)** :
- Logo SkyWeb
- Lien « Mes dossiers » (retour à la liste)
- Indicateur cycle AIRAC en cours
- Menu profil utilisateur (avions, préférences)

**Niveau 2 — Contenu principal** :
- Soit la **vue Liste des dossiers** (page d'accueil)
- Soit la **vue Dossier ouvert** (quand un dossier est sélectionné)

### 2.2 Vue « Dossier ouvert »

Lorsqu'un dossier est ouvert, la vue se compose de :

**En-tête fixe du dossier** :
- Nom du dossier (éditable)
- Résumé contextuel : route (ex. `LFXU → LFBP`), avion (ex. `F-HBCT CT-LS`), date
- Badge de statut (Brouillon / En préparation / Prêt / Archivé)
- **Indicateurs de complétion** : pastilles colorées par section (vert = complet, orange = partiel, gris = vide)

**Navigation par onglets horizontaux** :
Les onglets correspondent aux étapes du workflow de préparation, inspirés du synoptique du Manuel ACAT (p.9). Le pilote peut naviguer librement entre les onglets — il n'y a pas de progression forcée.

**Zone de contenu** :
Occupe tout l'espace disponible sous les onglets. Le contenu varie selon l'onglet sélectionné.

Le **globe 3D CesiumJS** n'est pas un arrière-plan permanent. Il est embarqué comme composant dans les onglets qui le nécessitent (Route, Espaces & Zones), occupant une partie de la zone de contenu (ex. moitié gauche ou panneau dédié).

### 2.3 Liste des onglets

| # | Onglet | Étapes PDF correspondantes | Globe 3D |
|---|--------|---------------------------|----------|
| 1 | **Résumé** | — (vue transversale) | Non |
| 2 | **Route** | §4 Caractéristiques route, §6.1 Segments et points | Oui |
| 3 | **Aérodromes** | §4 Caractéristiques des AD | Non |
| 4 | **Espaces & Zones** | §5 Espaces aériens, §6.2 Communications | Oui |
| 5 | **NOTAM** | §7 NOTAM, Activités Défense, SUP AIP | Non |
| 6 | **Météo** | §8 Situation météorologique | Non |
| 7 | **Navigation** | §6 Invariants + §9 Éléments variables | Non |
| 8 | **Carburant & Masse** | §10 Emport carburant et chargement | Non |
| 9 | **Performances** | §11 Limitations opérationnelles | Non |
| 10 | **Documents** | §12 Documents à emporter, §13 Plan de vol | Non |

---

## 3. Description des sections

### 3.0 Liste des dossiers (Home)

**Objectif** : Vue d'ensemble des dossiers de vol du pilote, point d'entrée de l'application.

**Données affichées** :
- Tableau/liste des dossiers avec colonnes : nom, route (départ → arrivée), avion, date, statut, complétion globale
- Dossiers triés par date décroissante (les plus récents en haut)

**Interactions** :
- **Créer un dossier** : bouton principal. Ouvre un dialogue demandant la route (import KML ou sélection route existante), l'avion, et la date prévue
- **Dupliquer** : crée une copie en conservant les invariants (route, AD), en vidant les variables (météo, NOTAM)
- **Ouvrir** : clic sur une ligne ouvre le dossier dans la vue à onglets
- **Archiver / Supprimer** : actions contextuelles par dossier
- Filtres : par statut, par route, par période

**Complétion** : N/A (c'est la vue d'accueil)

---

### 3.1 Résumé

**Objectif** : Vue d'ensemble synthétique du dossier, tableau de bord de la préparation.

**Réf. PDF** : Vue transversale couvrant l'ensemble du synoptique (p.9).

**Données affichées** :
- Carte miniature de la route (image statique ou composant léger, pas le globe complet)
- Informations contextuelles : route, avion, date, heure de départ, équipage
- **Tableau de complétion** : une ligne par section avec indicateur vert/orange/gris et résumé (ex. « 3/4 AD renseignés », « Météo collectée il y a 2h »)
- **Panneau d'alertes** : contraintes identifiées automatiquement, classées par gravité
  - Rouge : bloquant (masse > MTOW, VMC non respectées, piste trop courte)
  - Orange : attention (NOTAM actif, vent de travers proche limite, météo marginale)
  - Vert : RAS
- **Analyse TEM** (Threat & Error Management) :
  - Liste des menaces identifiées (automatiques + saisie pilote)
  - Contremesures associées
  - Sert de base au briefing pré-vol
- Liens rapides vers les documents générés (lognav, fiche 4120)

**Interactions** :
- Clic sur une section dans le tableau de complétion → navigation vers l'onglet correspondant
- Ajout/modification des menaces TEM (texte libre + catégories prédéfinies)
- Bouton « Marquer prêt » quand toutes les sections sont complètes
- Bouton « Archiver » après le vol

**Source de données** : Agrégation de toutes les sections du dossier.

**Complétion** : Cette section est complète quand toutes les autres sections sont au moins « partiellement remplies » et qu'il n'y a pas d'alerte rouge non acquittée.

---

### 3.2 Route

**Objectif** : Définir et valider la route, ses segments et ses waypoints. Correspond au tracé initial sur carte aéronautique et à la définition des jalons (§4 et §6.1 du PDF).

**Réf. PDF** : §4 « Tracer sommairement la route », §6.1 « Segments et points de route, éléments de vérification, points d'appui et repères de garde ».

**Données affichées** :

*Panneau carte (gauche ou haut)* :
- Globe 3D CesiumJS avec la route tracée
- Waypoints matérialisés (marqueurs cliquables)
- Profil terrain sous la route

*Panneau données (droite ou bas)* :
- **Tableau des waypoints** (ordonné du départ à l'arrivée) :

  | Champ | Description | Éditable |
  |-------|-------------|----------|
  | Séquence | Ordre 1..N | Non (réordonnancement par drag) |
  | Nom | Nom du waypoint | Oui |
  | Type | AD / VRP / User / INT | Oui |
  | Lat / Lon | Coordonnées WGS84 | Oui (via carte ou saisie) |
  | Altitude prévue (ft) | Altitude de croisière sur le segment suivant | Oui |
  | Notes pilote | Éléments de vérification, points d'appui, repères de garde | Oui |

- **Tableau des segments** (calculé automatiquement) :

  | Champ | Description | Source |
  |-------|-------------|--------|
  | De → À | Waypoints extrémités | Route |
  | Distance (NM) | Distance orthodromique | Calcul |
  | Rv (°) | Route vraie | Calcul |
  | Dm (°) | Déclinaison magnétique | WMM |
  | Rm (°) | Route magnétique (Rv + Dm) | Calcul |
  | Altitude (ft) | Altitude prévue du segment | Saisie |

- **Profil de vol vertical** : coupe latérale montrant le relief, l'altitude prévue par segment, les surfaces 3000ft ASFC et « S »

**Interactions** :
- **Import KML** : bouton pour charger un fichier KML (SD VFR Next). Peuple automatiquement les waypoints et segments
- Ajout / suppression / réordonnancement de waypoints
- Édition des altitudes prévues par segment
- Saisie des notes pilote par waypoint (éléments de vérification)
- Zoom/pan sur le globe pour valider visuellement le tracé
- Sélection des waypoints Topnav (début navigation) et point d'arrivée

**Source de données** :
- Import : `POST /api/route/upload` (KML)
- Segments : `GET /api/route/{id}/segments`
- Élévations : service d'élévation (Google/IGN)
- Déclinaison : World Magnetic Model (WMM)

**Complétion** : Route importée avec au moins 2 waypoints, altitudes de croisière renseignées pour chaque segment.

---

### 3.3 Aérodromes

**Objectif** : Consulter et analyser les caractéristiques des aérodromes de départ, destination et dégagement. Correspond à l'analyse des VAC et au remplissage de la fiche Aérodromes-Zones-NOTAM (§4 du PDF).

**Réf. PDF** : §4 « Caractéristiques des aérodromes et de la route » — extraction VAC, consignes particulières, fiche AERODROMES-ZONES-NOTAM (annexe 14.3).

**Données affichées** :

*Liste des AD concernés* (en-tête ou sidebar) :
- AD de départ (issu de la route)
- AD de destination (issu de la route)
- AD de dégagement (sélection manuelle, avec suggestion automatique basée sur la proximité de la route)
- AD en route (aérodromes proches de la route, pour information)

*Fiche détaillée par AD* (sélectionné dans la liste) :

| Section | Données | Source |
|---------|---------|--------|
| **Identification** | Code OACI, nom complet, statut (CAP/restreint), VFR, ouverture | XML SIA |
| **Localisation** | Coordonnées, altitude terrain (ft), déclinaison magnétique, température de référence | XML SIA |
| **Pistes** | Pour chaque piste : désignation (QFU), longueur, largeur, revêtement, TODA, ASDA, LDA, déclivité, altitude seuils | XML SIA |
| **Services ATS** | Type (TWR/AFIS/...), indicatif d'appel, langue, horaires | XML SIA |
| **Fréquences** | Par service : fréquence MHz, espacement (25/8.33 kHz), horaires, secteur | XML SIA |
| **Carburant** | Disponibilité, type, horaires avitaillement | XML SIA |
| **Notes VAC** | Sens du circuit, altitude de circuit, piste préférentielle, obstacles, périmètres urbanisés, consignes particulières, procédure panne radio, itinéraires arrivée/départ | Saisie utilisateur (capitalisée) |

**Interactions** :
- Sélection d'un AD dans la liste → affichage de sa fiche
- **Ajout d'un AD de dégagement** : recherche par code OACI ou par proximité (rayon autour de la route)
- **Édition des notes VAC** : formulaire de saisie pour les informations non disponibles dans le XML SIA (direction circuit, obstacles, consignes...)
- Les notes VAC sont **capitalisées** : une fois saisies pour un AD, elles sont réutilisables dans tous les dossiers futurs

**Source de données** :
- Données SIA : `GET /api/aerodrome/{icao}`, `/runways`, `/frequencies`
- Notes VAC : `GET/PUT /api/aerodrome/{icao}/vac-notes`
- Suggestion dégagements : `GET /api/route/{id}/nearby-aerodromes`

**Complétion** : Au moins les AD de départ et destination identifiés avec fiches chargées. Au moins un AD de dégagement sélectionné.

---

### 3.4 Espaces & Zones

**Objectif** : Identifier et analyser les espaces aériens, régions et zones traversés par la route. Déterminer les fréquences de communication dans l'ordre chronologique. Correspond au §5 du PDF et à la partie Communications du §6.2.

**Réf. PDF** : §5 « Espaces aériens, régions et secteurs d'information de vol, zones » — relevé des EAC, FIR, SIV, zones D/R/P ; §6.2 « Éléments pour les communications ».

**Données affichées** :

*Panneau carte (gauche ou haut)* :
- Globe 3D CesiumJS avec :
  - Route tracée
  - Espaces aériens colorés par classe (code couleur aviation standard)
  - Zones D/R/P visibles
  - FIR/SIV délimités

*Panneau données (droite ou bas)* :

- **Tableau des zones traversées** (par segment) :

  | Champ | Description |
  |-------|-------------|
  | Segment | De → À |
  | Zone | Identifiant (ex. TMA PARIS, SIV PARIS) |
  | Type | TMA, CTR, SIV, D, R, P, ZBA |
  | Classe | A à G |
  | Plancher (ft) | Limite inférieure |
  | Plafond (ft) | Limite supérieure |
  | Intersection | CROSSES / INSIDE / CORRIDOR |
  | Fréquence | Fréquence de contact |

- **Liste des fréquences** (ordonnée chronologiquement le long de la route) :

  | Champ | Description |
  |-------|-------------|
  | Ordre | Séquence chronologique |
  | Organisme | Indicatif d'appel (ex. « PARIS Info ») |
  | Service | TWR / APP / SIV / AFIS |
  | Fréquence (MHz) | Fréquence à utiliser |
  | Segment | Depuis quel segment |
  | Remarque | Conditions (clairance requise, VFR spécial...) |

- **Zones D/R/P** : tableau spécifique avec nature de l'activité, horaires d'activation, conditions de perméabilité

**Interactions** :
- Clic sur une zone dans le globe → mise en surbrillance dans le tableau (et inversement)
- Filtrage par type de zone (EAC, D, R, P, SIV)
- Toggle affichage/masquage des couches sur le globe
- Identification des points tournants de contournement si nécessaire
- Possibilité d'ajouter des notes (ex. « clairance à demander 5 min avant »)

**Source de données** :
- Analyse spatiale : `GET /api/route/{id}/airspaces`
- Fréquences route : `GET /api/route/{id}/frequencies`
- Détails zones : base SpatiaLite (SIA)

**Complétion** : Analyse des espaces aériens effectuée (au moins une exécution de l'analyse spatiale sur la route). Fréquences identifiées.

---

### 3.5 NOTAM

**Objectif** : Consulter les NOTAM, activités Défense (AZBA) et SUP AIP pertinents pour le vol. Correspond au §7 du PDF.

**Réf. PDF** : §7 « NOTAM, Activités Défense, SUP AIP » — repérer les informations pouvant impacter la préparation et l'exécution du voyage.

**Données affichées** :

- **NOTAM par catégorie** :
  - NOTAM aérodromes (départ, destination, dégagements)
  - NOTAM zones et espaces traversés
  - NOTAM FIR empruntées
  - AZBA (activations zones basse altitude du RTBA)
  - SUP AIP

- **Par NOTAM** :
  | Champ | Description |
  |-------|-------------|
  | Identifiant | Série + numéro |
  | ICAO / FIR | Localisation concernée |
  | Validité | De — À |
  | Texte | Contenu du NOTAM |
  | Impact | Évaluation de l'impact sur le vol (auto ou manuelle) |

**Interactions** :
- Rafraîchissement des NOTAM (collecte depuis la source)
- Filtrage par catégorie, période, pertinence
- Marquage « lu / pris en compte » par le pilote
- Ajout de notes personnelles sur un NOTAM

**Source de données** :
- `GET /api/notam/route/{route_id}`
- `GET /api/notam/aerodrome/{icao}`
- Source externe : Eurocontrol EAD ou ICAO API (à intégrer — non disponible actuellement)

**Complétion** : NOTAM consultés et acquittés par le pilote. *Note : cette section sera marquée « Non disponible » tant que la source NOTAM n'est pas intégrée, avec un rappel de consulter SOFIA-Briefing manuellement.*

---

### 3.6 Météo

**Objectif** : Analyser la situation météorologique pour la période du vol, déterminer les altitudes et niveaux de vol appropriés. Correspond au §8 du PDF.

**Réf. PDF** : §8 « Situation météorologique » — recueil du dossier météo (vents, températures, TEMSI, METAR, TAF, SIGMET), analyse VMC.

**Données affichées** :

- **METAR / TAF** des aérodromes concernés :
  - Texte brut (raw) + décodage structuré
  - Mise en évidence : QNH, vent (direction, force, rafales), visibilité, plafond, température
  - Indicateur de catégorie de vol (VFR / MVFR / IFR / LIFR)

- **Vents en altitude** (tableau WINTEM par segment) :

  | Segment | FL020 | FL050 | FL100 |
  |---------|-------|-------|-------|
  | LFXU → WPT1 | 270°/15kt, +8°C | 280°/25kt, +2°C | 290°/35kt, -5°C |
  | WPT1 → WPT2 | ... | ... | ... |

- **Évaluation VFR** :
  - Par segment : conditions VMC respectées ? (oui/non/marginal)
  - Plafond nuageux vs altitude prévue
  - Visibilité
  - Indice VFR global (bon / marginal / défavorable)

- **Cartes TEMSI** : images des cartes de temps significatif (si disponibles via Aeroweb)

**Interactions** :
- **Collecte météo** : bouton pour lancer/rafraîchir la collecte des données météo pour la route et la date du vol
- Horodatage de la dernière collecte (les données météo ont une durée de validité)
- Sélection du niveau de vol pour afficher les vents correspondants
- Toggle entre vue résumée et vue détaillée (raw METAR/TAF)
- Saisie manuelle de l'évaluation Go/No-Go météo par le pilote

**Source de données** :
- Météo route : `GET /api/weather/route/{route_id}?date={date}`
- METAR/TAF : `GET /api/weather/aerodrome/{icao}`
- Vents altitude : `GET /api/weather/winds-aloft?lat={lat}&lon={lon}&alt={alt}`
- Modèle : Open-Meteo (AROME/ICON) + NOAA (METAR)

**Complétion** : Données météo collectées pour la date du vol (< 6h). Évaluation VFR effectuée. Pas d'alerte IFR non acquittée.

---

### 3.7 Navigation

**Objectif** : Calculer les éléments de navigation : temps de vol, caps magnétiques, vitesses sol. Ce sont les « éléments variables » du PDF qui dépendent de la météo (vents). Correspond aux §6 (invariants déjà calculés dans Route) et §9 du PDF.

**Réf. PDF** : §9 « Éléments variables de la navigation (temps de vol et caps) » — calcul du Fb, Tsv, Xm, Cm, Te ; graduation de la carte en minutes ; profil de vol annoté.

**Données affichées** :

- **Tableau du log de navigation** (pré-rempli, cœur de cette section) :

  | Champ | Description | Source |
  |-------|-------------|--------|
  | De → À | Segment | Route |
  | Dis (NM) | Distance | Route (invariant) |
  | Rv (°) | Route vraie | Route (invariant) |
  | Dm (°) | Déclinaison magnétique | WMM (invariant) |
  | Rm (°) | Route magnétique | Calcul (invariant) |
  | Z (ft) | Altitude segment | Saisie |
  | Vent | Direction/force au FL du segment | Météo |
  | X (°) | Dérive | Calcul (Xm × sin Ø) |
  | Cm (°) | Cap magnétique (Rm ± X) | Calcul |
  | Vp (kt) | Vitesse propre | Config avion |
  | Vsol (kt) | Vitesse sol (Vp ± Veff) | Calcul |
  | Tsv (min) | Temps sans vent (Dis × Fb) | Calcul |
  | Te (min) | Temps estimé (avec vent) | Calcul |
  | ΣDis (NM) | Distance cumulée | Calcul |
  | ΣTe (min) | Temps cumulé | Calcul |
  | HE | Heure estimée de passage | Calcul |

- **Profil de vol annoté** :
  - Coupe verticale avec annotations :
    - Lieux de changement de calage altimétrique (QNH → 1013)
    - Application de la règle semi-circulaire
    - Points de contact radio
    - Début de descente (Tad, Dia)
  - Altitudes prévues vs relief

- **Synthèse temps de vol** : ΣTsv (sans vent), ΣTe (estimé), HEA (heure estimée d'arrivée)

- **Dérive maximum** aux FL020, FL050, FL100

**Interactions** :
- Le tableau se recalcule automatiquement quand la météo ou la route change
- Possibilité de forcer manuellement un vent par segment (override)
- Ajustement de la vitesse propre de croisière (Vpc)
- Choix de l'heure de départ → recalcul des HE par waypoint

**Source de données** :
- Route + segments : store local (déjà chargé)
- Météo : données de la section Météo
- Config avion : `GET /api/user/aircraft/{id}`
- Calculs : logique client ou `GET /api/flight/{id}` (calculs serveur)

**Complétion** : Météo collectée, tous les segments ont un cap magnétique et temps estimé calculés.

---

### 3.8 Carburant & Masse

**Objectif** : Établir le bilan carburant réglementaire et vérifier la masse et le centrage. Correspond au §10 du PDF.

**Réf. PDF** : §10 « Emport carburant et chargement (masse et centrage) » — fiches EMPORT CARBURANT (annexe 14.4) et CHARGEMENT (annexe 14.5).

**Données affichées** :

*Sous-section Carburant* (cf. fiche annexe 14.4 du PDF) :

| Ligne | Description | Valeur | Source |
|-------|-------------|--------|--------|
| Te | Temps estimé jusqu'à AD destination | min | Navigation |
| Dpda | Durée procédures départ & arrivée (10+5 min std) | min | Config / saisie |
| **Ttve** | **Temps total de vol estimé** (Te + Dpda) | min | Calcul |
| Dadgt | Durée du vol vers AD de dégagement | min | Calcul |
| Mops | Marge opérationnelle (Plan B et aléas) | 30 min | Config / saisie |
| Rfin | Réserve finale (NCO : VFR jour 30 min) | 30 min | Réglementaire |
| **Rt** | **Réserve totale** (Dadgt + Mops + Rfin) | min | Calcul |
| **AMNd** | **Autonomie minimum au départ** (Ttve + Rt) | min | Calcul |
| Cltr/h | Consommation horaire selon PWR et altitude | ltr/h | Config avion |
| **EMN** | **Emport minimum** (AMNd × Cltr/h ÷ 60) | ltr | Calcul |
| Del | Délestage (Ttve × Cltr/h ÷ 60) | ltr | Calcul |
| Masse EMN | EMN × 0.72 | kg | Calcul |
| Masse Del | Del × 0.72 | kg | Calcul |

*Sous-section Masse & Centrage* (cf. fiche annexe 14.5 du PDF) :

| Élément | Masse (kg) | Bras de levier (m) | Moment (kg.m) |
|---------|------------|---------------------|----------------|
| Avion vide | (fiche de pesée) | (fiche de pesée) | (fiche de pesée) |
| Pilote | (saisie) | (config avion) | (calcul) |
| Passager(s) avant | (saisie) | (config avion) | (calcul) |
| Passager(s) arrière | (saisie) | (config avion) | (calcul) |
| Essence rés. principal | (saisie/calcul) | (config avion) | (calcul) |
| Essence rés. supplémentaire | (saisie) | (config avion) | (calcul) |
| Bagages | (saisie) | (config avion) | (calcul) |
| **Avion chargé** | **Σ** | — | **Σ** |
| - Délestage rés. principal | (calcul) | (config avion) | (calcul) |
| - Délestage rés. supplémentaire | (calcul) | (config avion) | (calcul) |
| **Avion délesté** | **Σ** | — | **Σ** |

| Vérification | Valeur | Limite | Statut |
|-------------|--------|--------|--------|
| Masse au décollage | Σ avion chargé | MTOW | ✅ / ❌ |
| Masse à l'atterrissage | Σ avion délesté | MLW | ✅ / ❌ |
| Centrage départ | XX% MAC | Limites avant/arrière | ✅ / ❌ |
| Centrage arrivée | XX% MAC | Limites avant/arrière | ✅ / ❌ |

- **Diagramme de centrage** : graphique interactif montrant l'enveloppe de centrage de l'avion avec les points « départ » et « arrivée » positionnés

**Interactions** :
- Saisie des masses : pilote, passagers, bagages, carburant au roulage
- Choix du régime moteur en croisière (RPM → consommation)
- Ajustement de la répartition du carburant si réservoirs multiples
- Modification de la marge opérationnelle
- Les calculs se mettent à jour en temps réel à chaque saisie
- Alerte visuelle immédiate si masse ou centrage hors limites

**Source de données** :
- Config avion : `GET /api/user/aircraft/{id}` (masse vide, bras de levier, limites)
- Navigation (Te, distances) : données de la section Navigation
- Consommation : tables de performance numérisées (config avion)

**Complétion** : Masses de l'équipage saisies, carburant renseigné, masse totale ≤ MTOW, centrage dans les limites au départ ET à l'arrivée.

---

### 3.9 Performances & Limitations

**Objectif** : Vérifier que l'avion chargé peut opérer sur les pistes prévues dans les conditions du jour. Correspond au §11 du PDF.

**Réf. PDF** : §11 « Limitations opérationnelles » — distances TOD/LD, vent de travers, heure coucher soleil, QFU.

**Données affichées** :

- **Distances requises vs disponibles** :

  | | Décollage (AD départ) | Atterrissage (AD destination) | Atterrissage (AD dégagement) |
  |---|---|---|---|
  | Distance requise | TOD = XXX m | LD = XXX m | LD = XXX m |
  | Longueur disponible | TODA = XXX m | LDA = XXX m | LDA = XXX m |
  | Marge | +XX m ✅ | +XX m ✅ | +XX m ✅ |

  Les distances requises sont calculées à partir des abaques numérisés en tenant compte de :
  - Masse de l'avion chargé
  - Altitude-densité de la piste
  - Température au sol
  - Vent effectif (composante face/arrière)
  - Coefficients correcteurs (herbe, pente, humidité, expérience pilote)

- **Vent de travers** :

  | AD | QFU | Vent au sol | Composante travers | Limite démontrée | Statut |
  |---|---|---|---|---|---|
  | Départ | XX | XXX°/XX kt | XX kt | XX kt | ✅ / ⚠️ / ❌ |
  | Destination | XX | XXX°/XX kt | XX kt | XX kt | ✅ / ⚠️ / ❌ |

- **Limitations temporelles** :

  | Élément | Valeur |
  |---------|--------|
  | Heure coucher du soleil (HCS) à destination | HH:MM UTC |
  | Heure limite d'atterrissage (HLA) = HCS - 30 min | HH:MM UTC |
  | Heure estimée d'arrivée (HEA) | HH:MM UTC |
  | Marge temporelle | +XX min ✅ / ❌ |

- **QFU probable** à destination (déterminé à partir du vent prévu)
- **Type de montée initiale** recommandé sur l'AD de départ (Vx ou Vy selon obstacles)

**Interactions** :
- Sélection de la piste (QFU) si multiple pistes à l'AD
- Toggle des coefficients correcteurs (herbe haute, pente, humidité)
- Saisie de l'état de la piste (observation terrain)
- Les calculs se recalculent avec la météo (vent, température)

**Source de données** :
- Performances avion : tables numérisées dans config avion
- Données piste : section Aérodromes (TODA, LDA)
- Météo au sol : section Météo (METAR)
- Masse avion : section Carburant & Masse

**Complétion** : Toutes les distances calculées, aucune insuffisance de piste, vent de travers dans les limites, HEA avant HLA.

---

### 3.10 Documents

**Objectif** : Générer, prévisualiser et exporter les documents de navigation. Vérifier la checklist des éléments à emporter. Correspond aux §12 et §13 du PDF.

**Réf. PDF** : §12 « Documents et éléments à emporter », §13 « Plan de Vol VFR ».

**Données affichées** :

- **Journal de navigation (Lognav)** : aperçu du document pré-rempli, format A5 imprimable
  - Tableau des segments avec tous les éléments calculés (Cm, Te, Vsol, fréquences...)
  - En-tête : route, avion, date, QNH, vent
  - Colonne « Heure réelle » vide (à remplir en vol)

- **Fiche de préparation 4120** : aperçu du document pré-rempli
  - Section 1 : Informations générales
  - Section 2 : Aérodromes
  - Section 3 : Route et segments
  - Section 4 : Météo
  - Section 5 : Carburant et masse
  - Section 6 : Performances

- **Export FPL Garmin** : fichier .fpl prêt à charger dans le GPS

- **Checklist « Emport »** :
  - Documents pilote (licence, médical, carnet de vol)
  - Documents avion (CDN, certificat d'immatriculation, carnet de route, fiche de pesée, manuel de vol, assurance)
  - Documents passagers
  - Équipements (gilets si traversée maritime, etc.)
  - Cartes aéronautiques
  - Documents de navigation imprimés
  - Chaque item est cochable (✅ / ☐)

**Interactions** :
- Bouton **Générer** pour chaque document (déclenche la génération côté serveur)
- **Prévisualisation** dans la page avant impression
- Boutons **Exporter PDF** et **Imprimer** pour chaque document
- **Télécharger FPL** pour le fichier Garmin
- Cocher les items de la checklist emport

**Source de données** :
- Génération lognav/4120 : `GET /api/flight/{id}/prep-sheet`
- Export FPL : `GET /api/flight/{id}/export/fpl`
- Données : agrégation de toutes les sections du dossier

**Complétion** : Lognav et fiche 4120 générés. Checklist emport entièrement cochée.

---

## 4. Mapping synoptique PDF (p.9) → Onglets SkyWeb

| # | Étape du synoptique PDF | Onglet(s) SkyWeb | Ce que SkyWeb automatise |
|---|------------------------|-----------------|--------------------------|
| 1 | Analyser les caractéristiques des aérodromes et de la route | **Route** + **Aérodromes** | Import KML, extraction données SIA, calcul distances/routes |
| 2 | Prendre en compte les espaces aériens, régions et zones | **Espaces & Zones** | Analyse spatiale 3D automatique, identification fréquences |
| 3 | Déterminer les invariants de la navigation | **Route** (Rv, Rm, Dis) + **Navigation** (Fb, Tsv) | Tous les calculs géométriques et temporels |
| 4 | Consulter les NOTAM, Activités Défense et SUP AIP | **NOTAM** | Collecte automatique (quand source disponible) |
| 5 | Analyser la situation météorologique | **Météo** | Collecte METAR/TAF/vents, évaluation VMC |
| 6 | Déterminer les éléments variables de la navigation | **Navigation** | Triangle des vitesses, cap magnétique, temps estimé |
| 7 | Établir l'emport carburant et le chargement | **Carburant & Masse** | Bilan carburant réglementaire, calcul masse/centrage |
| 8 | Vérifier les limites de masse et centrage | **Carburant & Masse** | Diagramme centrage, alertes hors limites |
| 9 | Analyser les limitations opérationnelles | **Performances** | Distances TOD/LD vs pistes, vent travers, HCS |
| 10 | Finaliser le journal de navigation et entrer le plan de vol | **Documents** | Génération lognav, fiche 4120, export FPL |

La boucle de retour « Contraintes ? » du synoptique (entre NOTAM et Météo) se traduit dans SkyWeb par les **alertes transversales** visibles dans l'onglet Résumé et dans chaque section concernée. Le pilote peut naviguer librement entre les onglets pour résoudre les contraintes identifiées.

---

## 5. Composants partagés

### 5.1 Barre de complétion

Affichée dans l'en-tête fixe du dossier, elle montre une pastille par section :
- **Gris** : section non commencée
- **Orange** : section partiellement remplie
- **Vert** : section complète
- **Rouge** : section avec alerte bloquante

Cliquer sur une pastille navigue vers la section correspondante.

### 5.2 Système d'alertes

Les alertes sont **transversales** : elles sont générées par les données d'une section mais peuvent impacter d'autres sections. Exemples :
- Météo IFR → alerte dans Résumé + Météo + Performances
- Masse > MTOW → alerte dans Résumé + Carburant & Masse + Performances
- Piste trop courte → alerte dans Résumé + Performances + Aérodromes

Chaque alerte a un niveau (Rouge/Orange/Vert) et peut être **acquittée** par le pilote (avec commentaire optionnel).

### 5.3 Globe 3D (CesiumJS)

Composant réutilisable présent uniquement dans les onglets **Route** et **Espaces & Zones**. Couches activables :
- Route (polyline 3D)
- Waypoints (marqueurs)
- Espaces aériens (volumes colorés)
- Aérodromes (icônes)
- Relief / élévation

### 5.4 Tableaux éditables

Composant générique pour les vues tabulaires (waypoints, segments, masses, fréquences). Fonctionnalités :
- Tri par colonne
- Édition en ligne (cellules éditables)
- Lignes de résumé / totaux
- Export CSV

---

## 6. Modèle de données côté client

Le Dossier de Vol côté client (store Zustand) pourrait s'organiser ainsi :

```
flightDossierStore
├── dossier: {id, name, status, route_id, aircraft_id, departure_datetime}
├── route: {waypoints[], legs[]}
├── aerodromes: {departure, destination, alternates[]}
├── airspaces: {intersections[], frequencies[]}
├── notams: {items[], lastFetched}
├── weather: {metar{}, taf{}, windsAloft[], lastFetched}
├── navigation: {segments[] avec Cm, Te, Vsol...}
├── fuel: {fuelPlan, weightBalance}
├── performance: {takeoff, landing, crosswind, sunset}
├── documents: {lognav, prepSheet, fpl, checklist[]}
├── tem: {threats[], countermeasures[]}
└── completion: {bySection: {route: 'complete', meteo: 'partial', ...}}
```

Ce store correspond côté serveur au `FlightContext` défini dans `DESIGN-preparation-vol-vfr.md` (§2.4).

---

*Document créé le : 2026-02-04*
*Basé sur : Manuel de Préparation d'une Navigation VFR de jour (ACAT Toulouse, J. Loury, 2023)*
*Version : 0.1*
