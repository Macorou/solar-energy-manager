# Manual heating cycle 0.1.6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans;
> continue the ongoing inline commissioning fix in the existing worktree.

**Goal:** Faire aboutir la demande de chauffe malgré un ancien arrêt en attente.
**Architecture:** Confirmation d'arrêt Ariston croisée native/HA/réseau,
conservation de la demande en cours, temporisation avant envoi du nouveau départ.
**Tech Stack:** Python/FastAPI, pytest, React/Vitest/Playwright, GHCR privé amd64.
**Spec:** `docs/superpowers/specs/2026-10-27-manual-heating-cycle-design.md`.

## Global Constraints

- Aucune commande réelle ni modification des réglages de production.
- Aucun effacement aveugle d'inconnu ; sources native et électrique croisées.
- Garder confirmations physiques de départ, OCPP, limites et temporisation native.
- Conserver les correctifs 0.1.4/0.1.5, volume et port 8090.

## Review Focus

- Natif on, hors ligne, ancien, futur ou en défaut : ne pas valider un arrêt.
- HA ou réseau indisponible/ancien/incohérent : conserver la réserve.
- Nouvelle demande manuelle pendant un départ en attente : aucun nouvel arrêt.
- Arrêt confirmé après reconnexion : délai natif, puis un seul départ valide.
- Une demande expirée ou une pause explicite n'autorise aucun nouveau départ.

### Task 1 — Commandes et réconciliation

Files: `runtime/dispatcher.py`, `runtime/coordinator.py`, `engine/policies.py`,
`engine/engine.py`, `api/devices.py`, `tests/runtime/test_manual_heating_cycle.py`.

- [x] Écrire le scénario complet et les cas de refus ; constater les échecs.
- [x] Corriger la confirmation croisée, préserver l'autorisation en cours et
  différer le nouveau départ avant la fin de la temporisation native.
- [x] Suite pytest complète : 131 réussis, 1 Docker CI ; Vitest20/build/schémas ;
  revue indépendante, deux défauts importants reproduits/corrigés RED→GREEN,
  nouvelle suite complète verte.

### Task 2 — Distribution

- [x] Version 0.1.6 et guide de mise à jour sans nouvelle boucle désarmer/réarmer.
- [ ] Tag neuf, CI complète, image privée et téléchargement authentifié vérifiés.
- [ ] Fournir les résultats, référence exacte et limites de validation matérielle.
