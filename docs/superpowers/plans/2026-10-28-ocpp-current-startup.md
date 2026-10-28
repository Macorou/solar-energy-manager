# Remontée du courant OCPP et confirmation d’arrêt — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Corriger le départ suivi sept secondes après d’un arrêt pour courant de recharge absent, puis d’un faux blocage de confirmation.
**Architecture:** Avant un nouveau départ avec limitation par phase, préparer et relire uniquement les paramètres de télémétrie OCPP nécessaires. Le premier courant dispose de30s au plus, sans augmentation du profil et avec réduction immédiate sur surcharge réseau. Confirmer un arrêt par un état natif postérieur sans transaction ni départ en attente, croisé avec0W HA vérifié, et conserver le vrai motif de blocage.
**Tech Stack:** Python/FastAPI/SQLite/OCPP1.6, interface React existante.
**Spec:** Retour utilisateur du28/10/2026 : demande3,7kW puis « Arrêt demandé ». Diagnostic réel0.1.12 :3910W accepté22:51:37 puis suspend22:51:44 pour « Courant réel de recharge indisponible » ; currents={} ; planning valide, SOC60 utilisable, HA0W inchangé depuis21:59.

## Global Constraints
- Réutiliser le worktree v1 et la branche existante ; aucune modification de l’installation réelle, de HA ou de Portainer par l’assistant.
- Préparation des mesures seulement à un nouveau départ déjà autorisé, seulement si limitation par phase activée ; aucun redémarrage de borne ni changement de disponibilité/identité/limites matérielles.
- Conserver les anciens measurands, exiger Current.Import, Power.Active.Import, Energy.Active.Import.Register et intervalle1..10s, relire après écriture ; refus/lecture seule/RebootRequired => aucun RemoteStart.
- Données réseau absentes ou surcharge => réduction/arrêt immédiat ; absence de courant après30s => arrêt ; aucune attente nuage pour ces limites.
- Jamais confirmer une charge par un ancien0W ; arrêt confirmé seulement par mesures croisées après l’ordre, hors transaction et départ en attente.
- Publication privée0.1.13 et préversion autorisées dans la continuité des correctifs ; ne pas fusionner main ou déployer.

## Review Focus
- Télémétrie refusée, limite de longueur et réponse RebootRequired : aucun départ ni perte silencieuse d’anciens measurands.
- Pendant les30s initiaux, surcharge ou autre borne réservée : aucune augmentation, calcul conservateur, délai non renouvelé par réduction de profil.
- Courant manquant pendant une charge établie : arrêt conservé, aucun nouveau délai.
- Ancien0W HA avec transaction/pending start, état natif ancien/futur/en charge : aucune confirmation d’arrêt.
- Réconciliation après redémarrage : relecture d’état seule, aucun rejeu de départ ; vrai motif d’arrêt visible.

### Task 1 : correctif OCPP et régulation
**Files:** backend/app/connectors/ocpp/registry.py, metering.py ; backend/app/domain/devices.py ; backend/app/engine/engine.py, phase_limits.py ; backend/app/runtime/coordinator.py, dispatcher.py ; tests/protocol/test_ocpp_metering.py ; tests/runtime/test_ocpp_stop_confirmation.py ; tests/backend/test_phase_limits.py.
**Interfaces:** prepare_metering(station) configure/relit la seule télémétrie et renvoie None ou un code d’erreur ; ChargerAdapter(...,metering_required=False) l’appelle avant un nouveau départ. DeviceState expose transaction_active/start_pending optionnels. phase_power_limit(...,waiting_current=False) peut maintenir/réduire le précédent profil pendant le premier délai, jamais augmenter. Le coordinateur relit StatusNotification une fois par arrêt à réconcilier.
- [x] Écrire et observer les tests RED sur chaque rupture et les cinq risques ci-dessus.
- [x] Implémenter le minimum ; tests GREEN puis suite Python complète.
- [x] Commit et revue indépendante ciblée38b1c9c..797fea9 ; trois corrections importantes RED→GREEN, dont le délai durant Preparing. Suite289Python réussie,1Docker ignoré ;42UI et6navigateur réussis, schéma/TypeScript/build.

### Task 2 : livraison0.1.13
**Files:** versions backend/frontend/compose ; docs/deployment/patch-0.1.13.md et livrable outputs/mise-a-jour-portainer-0.1.13.md.
**Interfaces:** utilise le correctif Task1, image privée amd64 existante.
- [ ] Versions/schema/types/build/UI/navigateur/Compose ; documenter préparation des mesures et limites matérielles non vérifiées.
- [ ] Commit, tag immuable, CI complète, image privée/digest/pull vérifiés, préversion et guide identique.
- [ ] Conserver PR en brouillon, branche et notes locales, aucun déploiement.

Décisions : suivi du plan par PowerShell car le mappage des chemins Bash ne peut
pas écrire dans ce sandbox Windows ; sans changement du produit. Packaging
contrôlé séparément sur le tag final ; faute de contrôle, installation impossible.
Firmware et temps de remontée réels hors essais autorisés : aucune action sur
l’installation ; après mise à jour, un refus de réglage bloque encore le départ
avec son motif précis. Aucune anomalie mineure différée.
