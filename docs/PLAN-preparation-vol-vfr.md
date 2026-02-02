# Planification - Automatisation Préparation Vol VFR

## 1. Périmètre MVP

### MVP Phase 1 : Analyse de route (réutilisation SkyPath)

**Entrée** : KML exporté de SD VFR Next
**Sortie** : JSON/Markdown avec :
- Liste des segments avec waypoints
- Zones traversées par segment (type, classe, limites)
- Fréquences associées
- MSA par segment

**Effort** : Faible (wrapping services existants)

### MVP Phase 2 : Données aérodromes

**Entrée** : Codes OACI (départ, arrivée, dégagements)
**Sortie** : Infos structurées (pistes, fréquences, altitude)

**Effort** : Moyen (extraction depuis XML SIA existant)

### MVP Phase 3 : Météo route

**Entrée** : Coordonnées route + date/heure vol
**Sortie** :
- Vents par segment et altitude
- Température
- Plafond nuageux
- METAR/TAF aérodromes

**Effort** : Moyen (intégration APIs Open-Meteo + MF)

### MVP Phase 4 : Génération documents

**Entrée** : Données collectées phases 1-3
**Sortie** :
- Fiche préparation vol pré-remplie (format 4120)
- Export FPL Garmin

**Effort** : Moyen

---

## 2. Prochaines étapes

### Phase 0 : Validation accès données (prioritaire)

- [ ] **Proto Eurocontrol EAD** - Créer compte, tester accès gratuit, évaluer coûts B2B
  - Vérifier si usage personnel/non-commercial est gratuit
  - Tester ICAO API (100 appels gratuits) comme alternative
  - Évaluer Notamify (endpoints publics ?)
- [ ] Documenter résultats et décider source NOTAM/SUP AIP

### Phase 1 : MVP sans NOTAM

- [ ] Créer wrapper FastAPI autour de SkyPath (zones, fréquences)
- [ ] Extraire données AD de l'XML SIA (ADExtractor)
- [ ] Tester API Open-Meteo (vents, plafond)
- [ ] Tester API Météo-France (METAR/TAF)
- [ ] Définir format export fiche 4120 (Markdown ? JSON ?)

### Phase 2 : Déploiement

- [ ] Setup projet GCP (Cloud Run)
- [ ] Intégrer source NOTAM/SUP AIP validée

---

*Document créé le : 2026-01-21*
*Version : 0.1*
