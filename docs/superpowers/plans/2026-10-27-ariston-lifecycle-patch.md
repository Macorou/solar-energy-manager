# Patch Ariston 0.1.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for the ongoing inline bugfix; reuse the existing isolated worktree.

**Goal:** Éviter `unsupported_native_control` lors d'un passage en manuel.
**Architecture:** Session Ariston indépendante du mode ; initialisation sérialisée
avec les commandes ; état invalidé lors d'un remplacement réel de connexion.
**Tech Stack:** Python 3.12, FastAPI, ariston 0.19.9, pytest, GitHub Actions/GHCR.
**Spec:** `docs/superpowers/specs/2026-10-27-ariston-lifecycle-patch-design.md`.

## Global Constraints

- Backend Ariston et coordination uniquement ; conserver le comportement 0.1.4.
- Aucune migration, aucune commande réelle ni modification de production.
- Ne pas supprimer automatiquement les résultats inconnus ou les réservations.
- Image privée Linux amd64 0.1.5 ; conserver volume, port 8090 et réglages.

## Review Focus

- Changement de mode pendant la connexion : aucun faux refus de capacité.
- Rapport demandé avant découverte : pas de capacités vides persistantes.
- Passerelle ou identifiants changés : pas de réutilisation de l'ancien état.
- Consigne modifiée : exécution sur la consigne courante, sans reconnecter.
- Ancien résultat inconnu : pas de reprise automatique lors de la mise à jour.

### Task 1 — Session et initialisation

Files: `backend/app/api/water_heaters.py`, `connectors/ariston/client.py`,
`runtime/coordinator.py`, `tests/runtime/test_ariston_lifecycle.py`.

- [x] Écrire les tests de régression et constater les échecs contre 0.1.4.
- [x] Conserver la session sur les réglages de pilotage, invalider un ancien état
  lors du remplacement, éviter le redémarrage du poller sur un changement de mode.
- [x] Sérialiser initialisation/exécution et ne pas conserver un rapport vide
  établi sans appareil découvert.
- [x] Tests ciblés puis suite pytest, avec les protections inconnus/réservations : 103 réussis, 1 Docker réservé CI.

### Task 2 — Distribution et validation

- [x] Version 0.1.5, notes de déploiement et schémas à jour.
- [x] Vitest/build, revue indépendante ciblée sur le diff et les cinq risques : deux défauts importants corrigés en une passe RED→GREEN, suite complète verte.
- [x] Publication privée par un tag neuf ; vérifier CI et téléchargement : v0.1.5 / 686fc10, run 40592551168 réussi, paquet privé et téléchargement authentifié vérifiés.
- [x] Fournir la référence exacte et la procédure utilisateur de sortie du
  défaut après vérification de l'arrêt ; ne rien acquitter sur la production.
