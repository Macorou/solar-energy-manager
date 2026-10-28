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
- [ ] Écrire tests limites mono/tri, propre courant inclus, minimum et source absente,
  courant inexistant, réservation plusieurs bornes, normalisation tarif/A et trames énergie seules.
- [ ] Exécuter pytest ciblé et constater RED.
- [ ] Implémenter interfaces/validation et intégrer après budget avant réservation.
- [ ] GREEN ciblé et suite Python puis commit.

### Task2 : registre session, coût et SOC
Files runtime/charging.py, domain/vehicles.py, runtime/coordinator.py, engine/engine.py.
Consumes snapshots normalisés ; produces ChargingTracker.update(snapshot,config),
public device charging summary, effective telemetry + target latch.
- [ ] Tests75→80 arrêt, énergie seule, duplicate/reset/reboot, mesure retardée,
  mêmes anciennes75 répétées, véhicule changé, pauses, coût tarif variable/absence.
- [ ] RED puis implémentation persistée, source SOC, limites tous modes.
- [ ] GREEN ciblé + suite Python puis commit.

### Task3 : configuration et dashboard
Files pages/Settings.tsx/Devices.tsx, components/DeviceCard.tsx/Overview.tsx,
api/types.ts, dashboard.css, tests UI/browser.
Consumes schema réglages et public summaries ; produces champs phase/tarif/capacité/
rendement, courant par phase, état voiture, énergie/coût/%solaire/SOC estimé.
- [ ] Tests des seuils W/kW et rendu état/coût/source estimée, sauvegarde réglages.
- [ ] RED, génération schema, implémentation responsive préservant dessins.
- [ ] UI GREEN, TypeScript/build et Python suite puis commit.

### Task4 : revue et livraison
- [ ] Revue fraîche du diff complet15933fa..HEAD ; corrections importantes RED→GREEN.
- [ ] Bump0.1.9 et guide avec limites/configuration ; schema/build/Compose.
- [ ] Commit/tag immuable et publication privée autorisée ; CI Python/UI/browser/Docker.
- [ ] Vérifier image privée/digest, release et guide ; aucun déploiement matériel.

