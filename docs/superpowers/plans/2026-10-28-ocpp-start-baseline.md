# Index OCPP au démarrage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Éviter qu'un changement de base d'index au début d'une transaction rende un SOC Peugeot valide indisponible.
**Architecture:** Identifier le début de transaction OCPP indépendamment des index périodiques. Rebaser une nouvelle transaction sans inventer d'énergie entre deux bases. Récupérer une ancienne session bloquée sans énergie comptée uniquement lorsque l'arrêt est confirmé par une mesure utilisable de 0 W. Conserver les vrais défauts d'énergie pendant la charge et leur donner un motif précis.
**Tech Stack:** Python/FastAPI/SQLite, OCPP 1.6, React/TypeScript.
**Spec:** Demande du 28/10/2026 : charge attendue par le planning, refus « batterie indisponible » avec 60 % Peugeot visible. Dernière valeur Peugeot conservée automatiquement, objectif 80 % et sécurités électriques maintenus.

## Preuves en lecture seule
- Serveur 0.1.11 ; Peugeot 60 %, référence reconnue ; capacité50 kWh, rendement0.9.
- Planning autorise réseau de22:00 à05:45, cible80 % ; autorisation allow_grid=true.
- Journal : démarrage accepté22:16:10 à3910 W, arrêt22:16:13 pour « Batterie indisponible ».
- State Wallbox Finishing, connectée, HA confirme0 W ; index5000922 Wh terminal ; charging.energy_kwh=0, energy_partial=true, soc_usable=false.
- Cause logicielle reproduite : changement d'index avant première énergie comptée → soc_gap_at → retrait d'un SOC valide.
- Configuration actuelle de l'utilisateur : max6000 W, max20 A, phaseL1 ; ne pas restaurer l'ancien plafond3700 W. Aucun changement réel autorisé pendant ce diagnostic.

## Global Constraints
- Ne pas commander la borne, modifier HA/les réglages réels ou déployer. Publication privée de correctifs dans la continuité du travail autorisé.
- Ne jamais cumuler un saut d'index comme énergie chargée ; conserver les Wh déjà mesurés.
- Une nouvelle transaction repart d'une base explicite ; mêmes dates/identifiants ne doivent pas doubler les gains.
- Ancien défaut sans Wh mesuré : récupération seulement à l'arrêt confirmé ; coût/énergie restent partiels.
- Perte/incohérence d'énergie pendant une charge suivie : blocage conservé, motif compteur précis.

## Review Focus
- Index initial nul puis début de transaction à5000922 Wh : SOC60 utilisable sans millions de Wh fictifs.
- Transaction suivante et redémarrage : conserver les Wh de branchement, ne pas réinitialiser le SOC.
- Ancienne session0.1.11 partielle0kWh bloquée : reprise à0 W confirmé sans exiger un nouveau Peugeot.
- Reset/valeur impossible pendant une vraie charge : aucune augmentation ni contournement silencieux.
- Compteur absent/périmé et limitation par phase restent effectifs ; aucune action matérielle du test.

### Task 1 : index et motifs
**Files:** backend/app/domain/devices.py, vehicles.py, connectors/ocpp/station.py, runtime/charging.py/coordinator.py, engine/engine.py ; tests/backend/test_charging_accounting.py/test_phase_limits.py ; frontend/src/api/types.ts/components/DeviceCard.tsx et tests.
**Interfaces:** DeviceState porte l'identité et la base du début de transaction. ChargingTracker consomme les index et produit SOC/énergie/motif. VehicleTelemetry transmet le motif si le SOC est inutilisable.
- [x] Tests RED : début/fin de transaction et première remontée tardive, récupération de la session réelle anonymisée, conservation des garde-fous.
- [x] Implémentation minimale et GREEN complet Python/UI/schema/build/browser ; revue indépendante du correctif puis corrections importantes RED→GREEN.
- [x] Commit de la logique vérifiée.

### Task 2 : livraison0.1.12
- [x] Versions et guide ciblé, schéma et build ; tag immuable.
- [x] Publication privée, CI et digest/pull vérifiés ; préversion avec guide identique au livrable local.
- [x] Documentation finale ; garder branche/worktree/PR en brouillon, sans déploiement ni fusion.

Livraison : v0.1.12 au commit97e2688e857fe163bc1aae92d0e770adf7d80428.
Workflow40774394475 réussi : Python248/UI42/navigateur6/Docker1, schéma/build/Compose.
Image privée digest sha256:a910e54a090f9cf365ebaa6700733e01c39e1abf41aadca79859952a5ab3619b,
téléchargement authentifié vérifié. Guide4490octets,
SHA256dc12d3bb787391b82b61fac924dbbb8e5e79e3644c04225cfb9c1c6057d43107,
identique au livrable local et à l'asset GitHub. Aucune action réelle ni fusion main.
