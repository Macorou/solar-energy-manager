# Dernière référence Peugeot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Utiliser automatiquement le dernier SOC Peugeot, même antérieur au suivi, sans saisie manuelle.
**Architecture:** ChargingTracker conserve la date et le SOC constructeur ; l'index disponible le plus ancien devient la base quand la mesure précède l'historique. Une nouvelle mesure recale l'estimation ; une répétition ne la remet pas à zéro. Retirer le formulaire et la route de référence manuelle.
**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript/Vitest/Playwright.
**Spec:** Correction explicite du 28/10/2026 : « il doit toujours se basé sur la dernière valeur remonté par Peugeot ». Elle remplace l'exigence de confirmation manuelle du plan charge-accounting.

## Global Constraints
- Conserver l'arrêt sur SOC estimé, le suivi d'énergie/coût, les limites électriques et les données persistées.
- Accepter une dernière mesure constructeur valide ancienne ; aucune énergie inconnue avant le suivi n'est inventée.
- Une référence manuelle persistée de 0.1.10 doit être remplacée par Peugeot, même si sa date est plus récente.
- Aucun changement HA, commande réelle, déploiement, fusion main ou déplacement de tag.
- Publication privée du correctif 0.1.11 autorisée dans la continuité du patch.

## Review Focus
- Ancien SOC dès le premier index : 75 % + 2 kWh / 40 kWh = 80 %, sans confirmation.
- Dernier relevé valide en cache pendant indisponibilité Peugeot : ne pas effacer la référence.
- Nouveau relevé retardé et relevé répété : recalage chronologique sans double cumul.
- Migration des ancres manuelles ou couvertes=false ; redémarrage et nouvelle session.
- Aucun formulaire ni appel de confirmation en mobile ; arrêt effectif à 80 % avec API ancienne.

### Task 1 : corriger la référence et retirer la saisie
**Files:** backend/app/runtime/charging.py, backend/app/api/devices.py, frontend/src/components/DeviceCard.tsx, SocReference.tsx/test, dashboard.css, api/types.ts/schema.ts ; tests/backend/test_charging_accounting.py ; frontend/tests/e2e/configuration.spec.ts ; ChargingDashboard.test.tsx.
**Interfaces:** Consumes VehicleTelemetry et index OCPP ; produces soc/soc_usable/soc_reference_at. Plus de POST soc-reference.
- [x] Tests RED : remplacer refus du SOC ancien par référence automatique, migration manuelle, nouvelle donnée avant historique, répétition/reboot et arrêt runtime avec ancien SOC ; absence du champ dans la vraie carte.
- [x] Ajuster l'ancre et la base d'énergie au premier point disponible, garder les règles de perte d'index et le recalage d'une mesure plus récente ; supprimer la saisie/route/type manuel.
- [x] GREEN : pytest complet, Vitest complet, schéma/types/build et navigateur (6 parcours), revue indépendante du correctif.
- [x] Corriger les éventuels défauts importants reproduits et committer.

### Task 2 : livrer 0.1.11
**Files:** versions backend/frontend/compose, docs/deployment/patch-0.1.11.md, livrable outputs.
- [x] Bump 0.1.11, générer schéma et guide ciblé ; contrôles puis commit/tag immuable.
- [ ] Push branche privée/tag, attendre CI et publication image privée ; vérifier digest/pull dans le workflow.
- [ ] Publier la préversion et son guide, vérifier l'asset ; documenter le résultat, conserver le worktree/PR en brouillon.
