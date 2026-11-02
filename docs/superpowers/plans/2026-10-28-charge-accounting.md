# Recharge dynamique et comptabilité — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Réguler par phase, suivre énergie/coût/solaire et arrêter sur SOC effectif.
**Architecture:** Échantillons HA/OCPP normalisés ; limiteur courant pur porté
du principe EVCC ; registre de session SQLite et estimateur commun au runtime/UI.
**Tech Stack:** Python/FastAPI/Pydantic/SQLite, React/TypeScript/Vitest.
**Spec:** docs/superpowers/specs/2026-10-28-charge-accounting-design.md

## Global Constraints
- Plafond voiture3700W conservé ; réglages existants et secrets préservés.
- Aucun matériel commandé, aucune mutation HA ni déploiement.
- Solaire0€/kWh initial réglable, phases/capteurs non imposés.
- Une unique revue finale indépendante ; tests avant code.
- Source EVCC MIT référencée et notice livrée dans l'image.

## Review Focus
- Réponses hors ordre, reboot et compteur OCPP remis à zéro sans double cumul.
- Courant en attente non consommé deux fois, ni crédit commandé à tort.
- SOC constructeur retardé/relu, objectif déjà atteint et cible augmentée.
- Tarif absent/changement HC en plein intervalle sans effacer coût acquis.
- Sources facultatives malformées et ancienne configuration chargée sans panne.

### Task1 : sources et régulation
Files settings.py, domain/site.py/devices.py, connectors/home_assistant/client.py,
connectors/ocpp/station.py, engine/phase_limits.py, engine/engine.py, runtime/coordinator.py.
Consumes Sample, DeviceConfig ; produces phase_power_limit(snapshot,device,desired_w)
et snapshots phase_currents/voltages/powers/tariff, index/courant OCPP horodatés.
- [x] Écrire tests limites mono/tri, propre courant inclus, minimum et source absente,
  courant inexistant, réservation plusieurs bornes, normalisation tarif/A et trames énergie seules.
- [x] Exécuter pytest ciblé et constater RED.
- [x] Implémenter interfaces/validation et intégrer après budget avant réservation.
- [x] GREEN ciblé et suite Python puis commit.

### Task2 : registre session, coût et SOC
Files runtime/charging.py, domain/vehicles.py, runtime/coordinator.py, engine/engine.py.
Consumes snapshots normalisés ; produces ChargingTracker.update(snapshot,config),
public device charging summary, effective telemetry + target latch.
- [x] Tests75→80 arrêt, énergie seule, duplicate/reset/reboot, mesure retardée,
  mêmes anciennes75 répétées, véhicule changé, pauses, coût tarif variable/absence.
- [x] RED puis implémentation persistée, source SOC, limites tous modes.
- [x] GREEN ciblé + suite Python puis commit.

### Task3 : configuration et dashboard
Files pages/Settings.tsx/Devices.tsx, components/DeviceCard.tsx/Overview.tsx,
api/types.ts, dashboard.css, tests UI/browser.
Consumes schema réglages et public summaries ; produces champs phase/tarif/capacité/
rendement, courant par phase, état voiture, énergie/coût/%solaire/SOC estimé.
- [x] Tests des seuils W/kW et rendu état/coût/source estimée, sauvegarde réglages.
- [x] RED, génération schema, implémentation responsive préservant dessins.
- [x] UI GREEN, TypeScript/build et Python suite puis commit.

### Task4 : revue et livraison
- [x] Revue fraîche du diff complet15933fa..HEAD ; corrections importantes RED→GREEN.
- [x] Bump0.1.10 et guide avec limites/configuration ; schema/build/Compose.
- [x] Commit/tag immuable et publication privée autorisée ; CI Python/UI/browser/Docker.
- [x] Vérifier image privée/digest, release et guide ; aucun déploiement matériel.

Livraison : tag v0.1.10 au commit b8f87041855d33f2d8772305c7119e094d5cc2fc,
workflow 40755012215 réussi ; Python230, UI42, navigateur6, Docker1.
Release privée publiée comme préversion avec guide identique au livrable local
(SHA256 fbe329772a716c92c65f2734d37fbc301b52bbe74774c975fb2dc407b30101b2).
Image et digest vérifiés par le workflow ; aucune fusion ni action matérielle.

