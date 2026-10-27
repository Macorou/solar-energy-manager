# Patch 0.1.4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution. Native implementation requested by the user's instruction to make this narrowly scoped patch now; preserve the existing worktree.

**Goal:** Débloquer les valeurs inchangées relues avec succès et montrer la dernière batterie connue.
**Architecture:** Date de vérification HA distincte de la date de valeur ; disponibilité Peugeot distincte de son âge ; affichage explicite des anciennes données.
**Tech Stack:** Python 3.12/FastAPI, React/TypeScript, pytest, Vitest, Playwright, GitHub Actions/GHCR.
**Spec:** `docs/superpowers/specs/2026-10-27-unchanged-measurements-patch-design.md`.

## Global Constraints

- Uniquement ces deux demandes ; pas de modification des accès, modes ou automatismes de production.
- Conserver les dates fournisseur et les confirmations physiques après commande.
- Source inaccessible, valeur absente/invalide, limites, armement et réservations restent contrôlés.
- Image privée Linux amd64 0.1.4, volume et ports Portainer conservés.

## Review Focus

- Valeur constante 0 W avec HA disponible ; même cas après perte de liaison.
- Réponse HA incohérente pendant une transition : conserver la réservation jusqu’à l’observation physique.
- Ancien SOC récupéré récemment puis échec fournisseur ; aucune nouvelle charge automatique sur erreur.
- Affichage SOC 0, 100, absent, hors plage et ancien sans annoncer une charge observée.
- Nouvelle image : compatibilité des réglages 0.1.3 et aucune modification non demandée.

### Task 1 — Mesures et pilotage

Files: `backend/app/domain/measurements.py`, `domain/vehicles.py`, `connectors/home_assistant/mapping.py`, `connectors/home_assistant/client.py`, `engine/budget.py`, `engine/engine.py`, `runtime/coordinator.py` ; tests `tests/backend/test_ha_measurements.py`, `tests/runtime/test_freshness.py`, `tests/runtime/test_unchanged_measurements.py`.

- [x] Écrire les régressions 0 W ancien / source disponible, manuel et automatique, SOC ancien, valeurs invalides et source perdue ; constater les échecs.
- [x] Ajouter la confirmation de disponibilité sans modifier la date fournisseur ; conserver l’actualisation HA même sur un flux d’événements occupé ; séparer SOC utilisable/récent et invalider après erreur.
- [x] Exécuter les tests ciblés puis la suite Python et consigner le résultat : 87 réussis, 1 test Docker réservé à CI.

### Task 2 — Affichage batterie

Files: `frontend/src/components/DeviceCard.tsx`, son test et les types si nécessaire ; parcours `frontend/tests/e2e`.

- [x] Écrire les tests ancien/récent/absent/invalide/0 %, date en fuseau configuré et statut de charge inchangé ; constater les échecs.
- [x] Afficher le dernier SOC valide, « Donnée ancienne » et date fournisseur.
- [x] Exécuter Vitest, build et parcours navigateur bureau/mobile : 20 tests UI, build et 4 parcours réussis.

### Task 3 — Distribution vérifiée

- [x] Version 0.1.4, régénérer OpenAPI/types, notes ciblées et Compose pour l’utilisateur.
- [x] Revue indépendante du diff : aucun défaut actionnable relevé ; 23 tests ciblés réexécutés par le reviewer.
- [ ] Commit/push sur la branche existante, tag neuf v0.1.4 ; attendre CI et publication privée GHCR, vérifier le digest et les tests Docker en CI.
- [ ] Livrer la référence exacte et les instructions de redéploiement, sans agir sur Portainer.
