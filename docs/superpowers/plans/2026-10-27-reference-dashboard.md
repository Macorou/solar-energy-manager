# Reference Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reprendre fidèlement la composition de la photo approuvée par l’utilisateur dans le tableau de bord fonctionnel.

**Architecture:** Garder FastAPI et React. Extraire la vue d’ensemble, ses valeurs dérivées et son planning ; réutiliser les routes de commandes existantes. Illustrations SVG locales et CSS responsive sans dépendance ajoutée.

**Tech Stack:** React, TypeScript, CSS, Vitest, Playwright, Docker/GHCR.

**Spec:** docs/superpowers/specs/2026-10-27-reference-dashboard-design.md

## Global Constraints

- Référence graphique de la photo : quatre indicateurs, deux cartes illustrées, planning et carte HA.
- Aucune valeur fictive dans l’état réel ; Maison calculée seulement sur des mesures cohérentes à 2 secondes.
- Conserver activation explicite, commandes temporaires de 30 minutes et état confirmé par mesures.
- Conserver tous les appareils, programmes et plages HC ; aucune nouvelle connexion réelle.
- Pas de nouvelle dépendance, pas de changement au moteur de pilotage.

## Review Focus

- Mesures absentes, périmées, non finies, bilan négatif ou décalage temporel : Maison reste inconnue.
- Injection réseau : signe conservé dans le bilan de la maison.
- Plages traversant minuit et plusieurs programmes : bandes et légendes fidèles aux créneaux configurés.
- Observation, commande en attente et puissance non confirmée : pas de fausse confirmation et pas de démarrage permis avant activation.
- Absence d’appareils ou plusieurs appareils et écran mobile 390 px : vue lisible sans débordement.

## Task 1: Composition et données affichées

**Files:** créer `frontend/src/components/Overview.tsx`, `dashboard.ts`, `dashboard.test.ts`, `ScheduleTimeline.tsx`, `DeviceIllustration.tsx` ; modifier `App.tsx`, `DeviceCard.tsx`, `DeviceCard.test.tsx`, `Icon.tsx`, `style.css`.

**Interfaces:** consomme `Settings`, `LiveState`, `LiveDevice`, les callbacks existants `onAction(id, action)` et une navigation locale ; produit `Overview` sans requête ni commande automatique.

- [ ] Écrire les tests de bilan et de découpage horaire : import 4800, solaire 0, voiture 3700, ballon 0 donnent Maison 1100 W ; injection −1000 et solaire 5000 donnent 3000 W avec voiture 1000 W. Inconnue si mesure absente/inutilisable/non finie, écart >2 s ou bilan négatif. 22:00–06:00 se découpe en 00:00–06:00 et 22:00–24:00.
- [ ] Voir les tests échouer puis implémenter les fonctions pures `housePower`, `sumDevicePower` et `clockSegments`.
- [ ] Recomposer le tableau de bord et ses illustrations selon la référence ; conserver les commandes existantes et leurs restrictions.
- [ ] Vérifier les boutons de démarrage, l’affichage d’un résultat non confirmé et les mesures inconnues ; exécuter Vitest et la construction.

## Task 2: Vérification visuelle et livraison

**Files:** modifier le parcours `frontend/tests/e2e/configuration.spec.ts`, versions et Compose ; ajouter notes de correction et captures dans les livrables.

**Interfaces:** consomme l’application construite et le serveur temporaire isolé existant ; produit captures vérifiées, commit, PR actualisée et image privée 0.1.1.

- [ ] Adapter le parcours aux libellés du concept ; vérifier les quatre indicateurs, les illustrations, les commandes désactivées et le planning réel.
- [ ] Exécuter les parcours sur ordinateur et mobile, inspecter les captures à 1280 et 390 px, puis corriger les écarts observés.
- [ ] Exécuter la suite Python et demander une revue finale ciblée ; corriger les erreurs matérielles relevées avec leurs tests.
- [ ] Publier le commit et une image privée 0.1.1 ; vérifier le workflow, le téléchargement authentifié, le Compose et la préversion. Conserver la branche et le worktree pour la PR.
