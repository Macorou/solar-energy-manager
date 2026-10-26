# Solar Energy Manager — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire la première version utilisable du gestionnaire indépendant, avec solaire, plannings, HC/HP locales, connecteurs, interface web et image privée GHCR déployable depuis Portainer.

**Architecture:** Un service Docker contient l’interface compilée, une API FastAPI et un seul moteur de commandes. Les connecteurs échangent des données normalisées avec ce moteur ; SQLite conserve les réglages et les événements. Les publications privées GitHub/GHCR fournissent une image versionnée au Compose.

**Tech Stack:** Python, FastAPI, React, TypeScript, SQLite, bibliothèque OCPP Python, client Ariston à vérifier, pytest, Vitest, Playwright, Docker, GitHub Actions et GHCR. Les versions compatibles sont vérifiées et figées au premier ajout, sans reprendre aveuglément une version de documentation.

**Spec:** [2026-10-26-solar-energy-manager-design.md](../specs/2026-10-26-solar-energy-manager-design.md).

## Global Constraints

- Application indépendante ; bibliothèques existantes et modules EVCC réutilisables si utiles.
- Dépôt `Macorou/solar-energy-manager` privé ; image cible `ghcr.io/macorou/solar-energy-manager` privée.
- Docker ; fournir un fichier Compose directement utilisable dans une Stack Portainer.
- Première borne : Wallbox Pulsar Plus, OCPP 1.6J ; plusieurs bornes enregistrables.
- Première voiture : Peugeot e-208 de 2020 ; données de batterie issues des services Peugeot.
- Premier ballon : Ariston NUOS Plus Wi-Fi ; aucune coupure d’alimentation par prise connectée.
- Home Assistant fournit les mesures ; les plages HC/HP sont saisies dans les paramètres.
- Les puissances et temporisations des passages de nuages sont configurables par appareil.
- Exemple de programme : 80 % du lundi au vendredi à 5 h 45 ; réseau interdit avant le début défini, solaire anticipé autorisable.
- Horizon solaire proposé à 24 heures ; complément réseau terminé à l’échéance ; règles détaillées dans la conception validée.
- Un seul moteur propriétaire des commandes, sans action physique avant connexion validée et activation explicite de l’appareil.
- Une mesure indisponible n’est jamais remplacée par zéro ; demandé, accepté et observé restent distincts.
- Aucune donnée fictive n’est présentée comme une donnée réelle ; tests simulés et essais matériels sont distingués.
- Les remontées HA et EDF Tempo sont des étapes après la base, pas des fonctions prétendument livrées dans la V1.

## Review Focus

1. Réponses OCPP en retard ou session interrompue : ne pas doubler une demande ni confirmer une puissance non mesurée — tâches 5 et 8.
2. Réseau mesuré avec signe inversé, unités kW ou appareil à démarrage retardé : ne pas distribuer deux fois le surplus — tâches 2 et 3.
3. Horaires traversant minuit et changements d’heure : une occurrence par échéance, avec interdictions réseau conservées — tâche 4.
4. Jeton Peugeot expiré en cours de charge ou diagnostic Ariston indisponible : limiter l’impact à la fonction concernée, sans état inventé — tâches 6 et 7.
5. Redémarrage du conteneur avec session active ou clé de chiffrement manquante : reprise contrôlée, données préservées, aucune commande rejouée aveuglément — tâches 1, 8 et 10.

---

## Jalons et limites de validation

**A — moteur démontrable sans appareil :** tâches 1 à 4. API et règles testables avec des scénarios explicitement simulés.

**B — connexions et interface :** tâches 5 à 9. Une connexion non configurée ou non accessible reste indisponible, et ne bloque pas les tests des autres modules. La validation du compte réel Peugeot et de la commande native NUOS reste nécessaire avant de déclarer l’installation opérationnelle.

**C — distribution privée et mise en service :** tâches 10 et 11. Image construite, vérifiée et publiée, puis essais identifiés sur Portainer et le matériel. L’accès au serveur de Jordan et les éventuelles étapes interactives de connexion seront traités à ce moment ; ils ne sont pas supposés disponibles.

Le plan est auto-relu contre les sections 1 à 24 de la conception. Les seules extensions laissées à un plan ultérieur sont l’intégration HA de retour et Tempo, conformément à l’ordre demandé.

## Carte des fichiers

| Zone | Responsabilité |
|---|---|
| `backend/app/domain/` | Types partagés, unités, capacités et contrats de commande. |
| `backend/app/storage/` | Base, migrations, réglages, accès protégés et événements. |
| `backend/app/api/` | API versionnée, authentification et flux de mises à jour. |
| `backend/app/connectors/` | Home Assistant, OCPP, Peugeot et Ariston. |
| `backend/app/engine/` | Budget, temporisations, priorités et réservations. |
| `backend/app/scheduling/` | Programmes, occurrences et autorisations. |
| `backend/app/runtime/` | Acquisition, calcul, envoi, confirmation et reprise. |
| `backend/app/simulation/` | Appareils et horloge de démonstration isolés du mode réel. |
| `frontend/src/` | Écrans et client typé de l’API. |
| `tests/` | Tests de comportement et de protocoles ; aucun secret de compte réel. |
| `.github/workflows/` | Vérifications et publication de l’image privée. |
| `docs/deployment/` | Installation, registre privé, sauvegarde et compte rendu des essais. |

### Task 1: Service persistant, contrats et accès administrateur

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/settings.py`.
- Create: `backend/app/domain/measurements.py`, `devices.py`, `commands.py`, `schedules.py`, `vehicles.py`.
- Create: `backend/app/storage/database.py`, `settings_store.py`, `secrets.py`, `events.py`.
- Create: `backend/app/api/auth.py`, `system.py`.
- Test: `tests/backend/test_bootstrap.py`, `test_storage.py`, `test_secrets.py`.

**Interfaces:**
- Produces: `Sample(value: float | None, unit: str, source: str, measured_at: datetime | None, received_at: datetime, quality: Quality)`.
- Produces: `DeviceSpec(id, kind, capabilities, min_power_w, max_power_w, priority)`, `DeviceState(id, observed_power, observed_state, connected, fault)` et `Reservation(device_id, power_w, command_id, expires_at)`.
- Produces: `CommandIntent(id, device_id, action, limit_w, expires_at, reason)` ; `CommandResult(id, accepted, observed, error, checked_at)`.
- Produces: `CapabilityReport(supported, unsupported, verified_at, hardware_verified)` ; `VehicleTelemetry(soc, range_km, charging_state, measured_at, received_at, quality)`.
- Produces: `ChargeProgram(id, vehicle_id, weekdays, earliest_start, deadline, target_soc, solar_early, solar_horizon_hours, enabled)` ; `ChargeOccurrence(id, program_id, vehicle_id, network_start_at, solar_start_at, deadline_at, target_soc, state)`.
- Produces: `ChargeAuthorization(vehicle_id, allow_grid, allow_solar, target_soc, expires_at, reason)`.
- Produces: `create_app(settings: RuntimeSettings) -> FastAPI` et `SQLiteStore(path)` avec `load_settings()`, `save_settings(settings)`, `append_event(event)`, `backup(destination)`.
- API: `GET /api/v1/health/live`, `GET /api/v1/system/status`, `POST /api/v1/setup`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`.

- [ ] **Step 1: Écrire les tests de premier démarrage et de persistance.** Assertions : deux appels de setup ne créent pas deux administrateurs ; une API de configuration sans connexion est refusée ; fermeture/réouverture de SQLite conserve les réglages ; les accès fournisseur ne figurent ni en clair dans la base ni dans la réponse API ; une base existante sans sa clé échoue explicitement, sans générer une nouvelle clé incompatible.
- [ ] **Step 2: Vérifier l’échec initial.** Run: `uv run --project backend pytest tests/backend/test_bootstrap.py tests/backend/test_storage.py tests/backend/test_secrets.py -q`. Expected: échec sur le service ou les modules absents, pas sur un compte externe.
- [ ] **Step 3: Implémenter les contrats, SQLite et les routes.** Bootstrap à usage unique avec secret dans `/data/bootstrap-token`, clé persistée dans `/data/secrets/master.key` avec droits restreints ; mots de passe hachés ; accès fournisseurs chiffrés. Sessions HttpOnly/SameSite, contrôles d’origine pour mutations et réglage HTTPS adapté au reverse proxy. Aucun mot de passe réel dans les sources. Un jeton d’intégration futur est stocké sous forme de hash et limité à ses fonctions.
- [ ] **Step 4: Relancer les tests de la tâche.** Expected: tous passent ; une base de test ne contient aucune donnée de Jordan.
- [ ] **Step 5: Commit.** `git add backend tests/backend && git commit -m "feat: add persistent application service and access control"`.

### Task 2: Mesures Home Assistant et budget normalisé

**Files:**
- Create: `backend/app/connectors/home_assistant/client.py`, `mapping.py`.
- Create: `backend/app/domain/site.py`, `backend/app/engine/budget.py`.
- Create: `backend/app/api/connections.py`.
- Test: `tests/backend/test_ha_measurements.py`, `test_power_budget.py`.

**Interfaces:**
- Consumes: `Sample`, `DeviceState`, `Reservation` et `SQLiteStore`.
- Produces: `SiteSnapshot(at, grid, solar, device_states, vehicle_telemetry, reservations, site_limit_w, export_margin_w)` ; les objets `VehicleTelemetry` proviennent du contrat de la tâche 1 et peuvent rester indisponibles jusqu’à la connexion Peugeot.
- Produces: `HomeAssistantSource.connect()`, `snapshot() -> SiteSnapshot`, `subscribe(callback)`, `close()` ; appels asynchrones.
- Produces: `solar_budget_w(snapshot: SiteSnapshot) -> float | None` ; `None` signifie non calculable et non zéro.
- API: `POST /api/v1/connections/home-assistant/test`, `PUT /api/v1/connections/home-assistant`, `GET /api/v1/measurements`.

- [ ] **Step 1: Écrire les tests du bilan.** Assertions : `managed=3000 W, grid=-500 W, margin=100 W` donne `3400 W` de budget total ; `grid=unknown` donne `None` ; `1.5 kW` devient `1500 W` ; inversion de signe configurée appliquée une seule fois ; une ancienne mesure dont seule la réception est récente reste ancienne ; les entités de retour du projet sont refusées comme sources.
- [ ] **Step 2: Vérifier l’échec.** Run: `uv run --project backend pytest tests/backend/test_ha_measurements.py tests/backend/test_power_budget.py -q`. Expected: budget et adaptateur absents.
- [ ] **Step 3: Implémenter lecture initiale, abonnement et normalisation.** API WebSocket HA, reconnexion avec resynchronisation, accès sauvegardé côté serveur ; la mesure réseau signée est la référence. Le calcul retourne un budget total des appareils, les réservations étant ensuite traitées par l’allocation. Une production seule n’active pas le mode solaire.
- [ ] **Step 4: Vérifier sur serveur HA simulé.** Les changements de puissance mettent à jour le snapshot ; `unknown`, `unavailable` et la perte de connexion dégradent la qualité sans déclencher d’action physique.
- [ ] **Step 5: Commit.** `git add backend/app/connectors/home_assistant backend/app/domain/site.py backend/app/engine/budget.py backend/app/api/connections.py tests/backend && git commit -m "feat: read and normalize Home Assistant power measurements"`.

### Task 3: Moteur solaire, priorités et temporisations

**Files:**
- Create: `backend/app/engine/policies.py`, `allocation.py`, `hysteresis.py`, `engine.py`.
- Create: `backend/app/simulation/clock.py`, `fixtures.py`.
- Test: `tests/backend/test_solar_allocation.py`, `test_cloud_delays.py`.

**Interfaces:**
- Consumes: `SiteSnapshot`, `DeviceSpec`, `Reservation`, `CommandIntent`, `ChargeOccurrence`.
- Produces: `DevicePolicy(device_id, mode, start_surplus_w, start_delay_s, import_tolerance_w, stop_delay_s, min_run_s, restart_delay_s, target)`.
- Produces: `Clock.now() -> datetime`, `Clock.monotonic() -> float` ; simulation avec `advance(seconds)`.
- Produces: `EnergyEngine(clock).evaluate(snapshot, specs, policies, authorizations) -> DecisionBatch(commands, reservations, reasons)` ; le moteur conserve les minuteries entre évaluations.

- [ ] **Step 1: Écrire les tests d’allocation et de nuages.** Assertions : premier appareil trop gourmand ignoré au profit du suivant ; deux appareils possibles si budget suffisant ; démarrage Ariston réservé avant apparition de sa consommation ; complément réseau commun non additionné ; nuage de `20 s` avec délai `30 s` sans arrêt, déficit continu `31 s` avec demande de suspension ; retour au seuil annule le compteur ; ballon déjà lancé conservé selon sa durée minimale ; limites impératives priment sur les délais.
- [ ] **Step 2: Vérifier l’échec.** Run: `uv run --project backend pytest tests/backend/test_solar_allocation.py tests/backend/test_cloud_delays.py -q`. Expected: moteur absent, sans attente murale dans les tests.
- [ ] **Step 3: Implémenter les fonctions d’allocation et les minuteries.** Séparer le budget solaire et la capacité électrique totale. Réserver les commandes non confirmées, moduler la voiture dans ses limites, utiliser l’ordre configuré puis l’échéance et l’identifiant pour départager. Ne pas confondre puissance libérée supposée et observée.
- [ ] **Step 4: Relancer les scénarios avec horloge simulée.** Expected: décisions et raisons déterministes ; aucune dépendance à l’ordre d’arrivée des tâches réseau pour distribuer le même budget.
- [ ] **Step 5: Commit.** `git add backend/app/engine backend/app/simulation tests/backend && git commit -m "feat: allocate solar surplus with configurable cloud delays"`.

### Task 4: Plannings voiture et plages HC/HP locales

**Files:**
- Create: `backend/app/scheduling/recurrence.py`, `authorization.py`, `tariff_windows.py`.
- Create: `backend/app/api/schedules.py`, `tariffs.py`.
- Test: `tests/backend/test_charge_programs.py`, `test_tariff_windows.py`, `test_schedule_dst.py`.

**Interfaces:**
- Consumes: `ChargeProgram`, `ChargeOccurrence`, `DevicePolicy`, `SQLiteStore`.
- Produces: `occurrences_for(program, start: datetime, end: datetime, timezone: str) -> list[ChargeOccurrence]`.
- Consumes: `ChargeAuthorization` défini dans la tâche 1.
- Produces: `select_authorization(vehicle_id, now, occurrences, default_soc_target) -> ChargeAuthorization`.
- Produces: `is_off_peak(now, windows, timezone) -> bool` ; interface tarifaire locale prévue pour extension Tempo.
- API: CRUD `/api/v1/schedules`, aperçu `/api/v1/schedules/preview`, GET/PUT `/api/v1/tariffs/off-peak`.

- [ ] **Step 1: Écrire les tests des horaires.** Assertions : programme lundi–vendredi à `05:45`, début `22:00 la veille`, cible `80` ; pas de réseau à `21:59`, solaire possible dans l’horizon autorisé ; fin du complément à `05:45` si cible manquée ; cible du vendredi à `100` sans influence dès lundi avec horizon `24 h` ; plages HC multiples et transminuit sans HA ; une occurrence à l’heure répétée, report explicite de l’heure inexistante ; cibles différentes à même échéance arbitrées comme dans la conception.
- [ ] **Step 2: Vérifier l’échec.** Run: `uv run --project backend pytest tests/backend/test_charge_programs.py tests/backend/test_tariff_windows.py tests/backend/test_schedule_dst.py -q`. Expected: fonctions absentes.
- [ ] **Step 3: Implémenter récurrence et autorisations.** Stocker événements UTC et récurrences en Europe/Paris par défaut ; matérialiser les occurrences sans doublon, prévisualiser la veille et les changements d’heure ; empêcher le réseau d’un programme ultérieur de démarrer trop tôt. Une occurrence close conserve son résultat.
- [ ] **Step 4: Vérifier les tests et le branchement au moteur.** Expected: le ballon en HC est éligible sans soleil, en HP seulement selon le solaire ; la voiture planifiée commence son complément à l’ouverture autorisée, sous réserve de puissance.
- [ ] **Step 5: Commit.** `git add backend/app/scheduling backend/app/api/schedules.py backend/app/api/tariffs.py tests/backend && git commit -m "feat: add recurring charging goals and local off-peak windows"`.

### Task 5: Serveur OCPP et première borne

**Files:**
- Create: `backend/app/connectors/ocpp/server.py`, `station.py`, `profiles.py`, `registry.py`.
- Create: `backend/app/api/chargers.py`.
- Create: `docs/deployment/wallbox-commissioning.md`.
- Test: `tests/protocol/test_ocpp_sessions.py`, `test_ocpp_limits.py`, `test_ocpp_disconnect.py`.

**Interfaces:**
- Consumes: identifiants enregistrés, `DeviceSpec`, `CommandIntent`, `CommandResult`, stockage des sessions.
- Produces: `OcppServer.start()`, `close()` ; `ChargerAdapter.read_state() -> DeviceState`, `execute(intent) -> CommandResult`, `probe_capabilities() -> CapabilityReport` ; opérations asynchrones.
- Produces: connexion `/ocpp/{charge_point_id}` avec sous-protocole `ocpp1.6`, autorisation selon la capacité d’authentification validée de la borne.
- API: CRUD `/api/v1/chargers`, POST `/api/v1/chargers/{id}/test` et `/arm`.

- [ ] **Step 1: Écrire les échanges OCPP simulés.** Assertions : borne inconnue refusée ; deux bornes isolées ; BootNotification/heartbeat/status/transaction/meter reçus ; acceptation d’un profil distincte de sa mesure ; unités et connecteurs normalisés ; une session reconnectée n’en crée pas une deuxième ; aucune hypothèse universelle de suspension à `0 A`.
- [ ] **Step 2: Vérifier l’échec.** Run: `uv run --project backend pytest tests/protocol/test_ocpp_sessions.py tests/protocol/test_ocpp_limits.py tests/protocol/test_ocpp_disconnect.py -q`. Expected: serveur et adaptateur absents.
- [ ] **Step 3: Implémenter avec la bibliothèque OCPP retenue.** Démarrage/arrêt, profils de courant et réconciliation adaptés aux capacités ; accusés de réception, délais et valeurs observées séparés. Chaque méthode demeure limitée à la borne ciblée. Un profil expirant ne constitue pas, à lui seul, une preuve d’arrêt hors ligne : vérifier son comportement et le repli natif avant d’armer le solaire.
- [ ] **Step 4: Exécuter les tests et documenter l’essai Pulsar Plus.** Référence/logiciel, phases, minima, profils, comportement hors ligne et retour après redémarrage à relever. Sans accès matériel, marquer « non testé sur la borne », jamais « compatible validé ».
- [ ] **Step 5: Commit.** `git add backend/app/connectors/ocpp backend/app/api/chargers.py tests/protocol docs/deployment/wallbox-commissioning.md && git commit -m "feat: add multi-station OCPP charging control"`.

### Task 6: Télémétrie Peugeot et fraîcheur batterie

**Files:**
- Create: `backend/app/connectors/peugeot/auth.py`, `client.py`, `telemetry.py`.
- Create: `backend/app/api/vehicles.py`.
- Create: `docs/deployment/peugeot-connection.md`, `docs/third-party/peugeot-provenance.md`.
- Test: `tests/connectors/test_peugeot_auth.py`, `test_peugeot_freshness.py`.

**Interfaces:**
- Consumes: stockage des accès, `Sample`, référence véhicule et VIN configuré sans journalisation.
- Consumes: `VehicleTelemetry` défini dans la tâche 1 et exposé par `SiteSnapshot.vehicle_telemetry`.
- Produces: `PeugeotAdapter.begin_auth() -> AuthChallenge`, `complete_auth(response)`, `refresh_access()`, `read_telemetry(vehicle_id) -> VehicleTelemetry` ; asynchrone.
- API: `/api/v1/connections/peugeot/auth`, `/complete`, `/test` et CRUD `/api/v1/vehicles`.

- [ ] **Step 1: Vérifier l’accès fournisseur retenu.** Étudier le flux Peugeot d’EVCC à une révision identifiée et l’accès officiel Stellantis ; inscrire le chemin retenu, sa licence, son authentification et ses limites dans le document de provenance. Une autorisation interactive réelle se fait dans un écran dédié, sans secret dans le chat. Si l’accès reste impossible, livrer un état d’indisponibilité exact et poursuivre les autres tâches ; la validation matérielle globale restera ouverte.
- [ ] **Step 2: Écrire les tests de jetons et de fraîcheur.** Assertions : renouvellement réussi, refus permanent nécessitant reconnexion, temporisation sur limite d’appels, secret expurgé des erreurs ; ancien horodatage fournisseur non rafraîchi artificiellement ; batterie trop ancienne en charge active produit une demande de suspension ; nouvelle mesure valide ne relance que si l’autorisation est encore applicable.
- [ ] **Step 3: Vérifier l’échec initial des tests.** Run: `uv run --project backend pytest tests/connectors/test_peugeot_auth.py tests/connectors/test_peugeot_freshness.py -q`. Expected: adaptateur absent ou garde de fraîcheur absente.
- [ ] **Step 4: Implémenter l’adaptateur et la garde.** Lire les informations réellement fournies, limiter et mettre en cache les requêtes ; rendre la télémétrie et sa qualité visibles, sans commande de charge Peugeot concurrente de la borne OCPP.
- [ ] **Step 5: Vérifier les tests et enregistrer l’état de l’essai réel.** Pour une e-208 connectée, comparer une mesure et son heure avec la source fournisseur ; sinon, résultat « non configuré » ou « indisponible », pas une valeur de démonstration.
- [ ] **Step 6: Commit.** `git add backend/app/connectors/peugeot backend/app/api/vehicles.py tests/connectors docs/deployment/peugeot-connection.md docs/third-party && git commit -m "feat: add Peugeot vehicle telemetry and freshness handling"`.

### Task 7: Ballon Ariston avec contrôle natif vérifié

**Files:**
- Create: `backend/app/connectors/ariston/client.py`, `capabilities.py`.
- Create: `backend/app/api/water_heaters.py`.
- Create: `docs/deployment/ariston-commissioning.md`.
- Test: `tests/connectors/test_ariston_control.py`, `test_ariston_partial_failure.py`.

**Interfaces:**
- Consumes: `DeviceSpec`, `DeviceState`, `CommandIntent`, `CommandResult`, accès protégés.
- Produces: `AristonAdapter.connect()`, `read_state()`, `probe_capabilities()`, `execute(intent)`, `close()` ; asynchrone, mêmes contrats génériques que la borne.
- API: CRUD `/api/v1/water-heaters`, `/test`, `/arm`.

- [ ] **Step 1: Vérifier la bibliothèque candidate et les fonctions du NUOS.** Identifier lecture température/consigne/mode et demande native autorisable ; fixer la version compatible. Le diagnostic historique HA n’est pas une validation actuelle. Aucune manipulation du bornier ni coupure électrique n’est prévue.
- [ ] **Step 2: Écrire les tests de demande et de panne partielle.** Assertions : la demande acceptée réserve la puissance jusqu’au résultat ; un diagnostic optionnel en panne n’empêche pas une lecture principale réussie ; limite constructeur et délai minimal respectés ; retour de consigne vérifié ; mode non supporté visible et non transformé en succès ; passage HC vers HP réévalué sans coupure d’alimentation.
- [ ] **Step 3: Vérifier l’échec.** Run: `uv run --project backend pytest tests/connectors/test_ariston_control.py tests/connectors/test_ariston_partial_failure.py -q`. Expected: adaptateur absent.
- [ ] **Step 4: Implémenter le connecteur natif et la dégradation isolée.** Toute consommation non empêchable par le mode fabricant reste signalée. Ne pas simuler une modulation instantanée ou une compatibilité SG-Ready.
- [ ] **Step 5: Vérifier les tests et renseigner l’essai réel.** Une commande physique n’est envoyée qu’après connexion et activation explicites. L’absence d’un accès au compte est documentée sans masquer le caractère non validé.
- [ ] **Step 6: Commit.** `git add backend/app/connectors/ariston backend/app/api/water_heaters.py tests/connectors docs/deployment/ariston-commissioning.md && git commit -m "feat: add native Ariston hot-water control"`.

### Task 8: Boucle de contrôle, reprise et commandes locales

**Files:**
- Create: `backend/app/runtime/coordinator.py`, `dispatcher.py`, `recovery.py`.
- Create: `backend/app/api/devices.py`, `events.py`, `simulation.py`.
- Test: `tests/runtime/test_command_lifecycle.py`, `test_recovery.py`, `test_simulation_isolation.py`.

**Interfaces:**
- Consumes: moteur, autorisations, sources et adaptateurs des tâches précédentes.
- Produces: `Coordinator.start()`, `stop()`, `tick() -> DecisionBatch` ; propriétaire unique des évaluations et commandes.
- Produces: `Dispatcher.dispatch(intent, adapter) -> CommandResult`, `recover(store, adapters) -> RecoveryReport` ; pas de relance aveugle d’une commande à effet physique.
- API: `GET /api/v1/state`, `GET /api/v1/events`, `POST /api/v1/devices/{id}/manual`, `/pause`, `/resume` ; démonstration dans une session isolée explicitement identifiée.

- [ ] **Step 1: Écrire les tests de bout en bout simulés.** Assertions : deux ticks simultanés n’envoient pas deux démarrages ; timeout affiche résultat inconnu ; réservation libérée seulement après état concilié ; perte HA empêche un nouveau solaire ; manuel voiture sans changement du ballon ; arrêt du processus puis reprise relit les sessions ; anciennes occurrences non rattrapées en boucle ; aucun adaptateur réel n’est appelé en démonstration.
- [ ] **Step 2: Vérifier l’échec.** Run: `uv run --project backend pytest tests/runtime -q`. Expected: coordination absente.
- [ ] **Step 3: Implémenter coordination et reprise.** Une seule instance active ; validations d’activation par appareil, tentatives limitées, événements avec raison et origine, délai d’attente cloud non bloquant pour OCPP et l’API. Les accès inconnus ou les appareils non armés ne reçoivent aucune commande.
- [ ] **Step 4: Exécuter la suite backend.** Run: `uv run --project backend pytest tests/backend tests/connectors tests/protocol tests/runtime -q`. Expected: tous les tests simulés passent ; essais réels encore étiquetés séparément.
- [ ] **Step 5: Commit.** `git add backend/app/runtime backend/app/api tests/runtime && git commit -m "feat: coordinate decisions, commands and restart recovery"`.

### Task 9: Interface web et configuration complète

**Files:**
- Create: `frontend/package.json`, `frontend/src/api/client.ts`, `types.ts`.
- Create: `frontend/src/pages/Overview.tsx`, `Devices.tsx`, `WaterHeating.tsx`, `Planning.tsx`, `History.tsx`, `Settings.tsx`.
- Create: `frontend/src/components/PowerFlow.tsx`, `DeviceCard.tsx`, `CloudSettingsForm.tsx`, `ChargeProgramEditor.tsx`, `ConnectionWizard.tsx`.
- Test: `frontend/src/components/ChargeProgramEditor.test.tsx`, `CloudSettingsForm.test.tsx`, `tests/e2e/configuration.spec.ts`, `planning.spec.ts`.

**Interfaces:**
- Consumes: API `/api/v1` ; types générés ou vérifiés depuis le schéma OpenAPI réel, aucune copie divergente des règles métier.
- Produces: les six espaces décrits dans la conception, assistant de connexion et activation par équipement ; états et raisons affichés depuis l’API.

- [ ] **Step 1: Écrire les tests des parcours essentiels.** Assertions : plusieurs plages HC traversant minuit ; programme `80 % à 05:45` du lundi au vendredi ; saisie du début la veille et de l’horizon solaire ; seuils W et délais indépendants par appareil ; données périmées clairement identifiées ; aucune commande sur bouton indisponible ; sortie du mode démo sans reprise de ses valeurs comme réglages réels.
- [ ] **Step 2: Vérifier l’échec.** Run: `npm --prefix frontend test -- --run`. Expected: composants ou client absents ; ne pas masquer les erreurs de contrat par des mocks trop permissifs.
- [ ] **Step 3: Implémenter les écrans autour de l’API.** Reprendre les deux maquettes comme intention visuelle, pas comme données ou horaires réels. Réordonner les priorités, éditer plusieurs programmes et afficher la raison des attentes. Aucun secret fournisseur n’est envoyé au navigateur lors d’une lecture de paramètres.
- [ ] **Step 4: Vérifier tests, compilation et parcours.** Run: `npm --prefix frontend run build`, puis Playwright sur le backend de test avec fournisseurs simulés. Examiner captures à `1920 px` et `390 px` : absence de débordement, formulaires utilisables, horaires lisibles, états accessibles sans dépendre uniquement de la couleur.
- [ ] **Step 5: Commit.** `git add frontend tests/e2e && git commit -m "feat: add responsive energy management interface"`.

### Task 10: Image Docker, Stack Portainer et publication GHCR privée

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`.
- Create: `.github/workflows/ci.yml`, `publish-image.yml`.
- Create: `docs/deployment/portainer.md`, `backup-restore.md`.
- Test: `tests/deployment/test_image_smoke.py`.

**Interfaces:**
- Consumes: backend, frontend compilé et toutes les vérifications précédentes.
- Produces: image `ghcr.io/macorou/solar-energy-manager:<version>`, digest et Compose utilisant une image publiée ; persistance `/data`, ports web/OCPP configurables et une seule instance.
- Publication : tags `v*` validés, `GITHUB_TOKEN` avec `contents: read` et `packages: write`, actions figées sur révisions vérifiées ; pas de publication sur PR.

- [ ] **Step 1: Écrire le smoke test conteneur.** Assertions : service accessible après bootstrap ; fichiers conservés après recréation ; aucun mode privilégié/socket Docker ; arrêt propre ; panne d’un fournisseur distincte de la santé du conteneur ; clé et base restaurées ensemble. Le test ne prétend pas contrôler une voiture réelle.
- [ ] **Step 2: Vérifier l’échec sur image non construite.** Run: `uv run --project backend pytest tests/deployment/test_image_smoke.py -q` avec l’environnement Docker de test. Expected: image ou conteneur absent. Si Docker n’est pas installé localement, exécuter cette vérification dans GitHub Actions et conserver le résultat du job.
- [ ] **Step 3: Implémenter Docker et Compose.** Build multiétape frontend/backend ; image Linux amd64 initiale, arm64 selon serveur confirmé ; utilisateur non privilégié, volume nommé, limites de journaux, politique de redémarrage, healthcheck. Le Compose fonctionne dans Portainer sans `build:` et ne contient aucun secret réel.
- [ ] **Step 4: Implémenter CI et publication.** CI exécute backend, frontend et smoke test ; publication seulement si vérifications réussies, label OCI de provenance vers le dépôt. Vérifier explicitement que le paquet reste privé et est lié au dépôt. Ne publier aucune image étiquetée comme fonctionnelle avant les contrôles de conteneur.
- [ ] **Step 5: Vérifier sur GitHub et préparer le guide Portainer.** Conserver URL de workflow, version et digest réellement publiés. Documenter l’ajout de `ghcr.io` dans Portainer avec accès de lecture (`read:packages`, mécanisme classique actuellement documenté par GitHub), saisie du secret dans Portainer uniquement. Confirmer que l’image se télécharge avec un accès autorisé et ne se télécharge pas anonymement.
- [ ] **Step 6: Commit.** `git add Dockerfile .dockerignore compose.yaml .github/workflows docs/deployment tests/deployment && git commit -m "build: publish private GHCR image for Portainer"`.

### Task 11: Mise en service, essais réels et livraison de la base

**Files:**
- Create: `docs/deployment/acceptance-report.md`.
- Modify: `README.md`, guides des connecteurs et de Portainer.
- Modify: `compose.yaml` pour référencer la version ou le digest vérifié.

**Interfaces:**
- Consumes: image publiée, accès de lecture GHCR, serveur Portainer et appareils réellement accessibles.
- Produces: compte rendu distinguant vérifications logicielles, image et installation ; instructions de mise à jour et de restauration.

- [ ] **Step 1: Relever les paramètres de mise en service.** Serveur/architecture, mesures HA et signe réseau, phases et limites, plages HC réelles, consigne NUOS et accès Peugeot. Ne pas publier ces secrets ni des captures contenant des accès.
- [ ] **Step 2: Déployer la Stack avec la version vérifiée.** Si l’accès à Portainer n’est pas disponible dans la session, livrer le Compose et le guide, puis conserver cette étape explicitement non vérifiée ; ne pas prétendre que le serveur de Jordan exécute l’application.
- [ ] **Step 3: Vérifier les lectures et activer chaque appareil séparément.** Lire OCPP, batterie et température réelles ; vérifier les capacités et le repli hors ligne, puis activer les commandes voulues. Tout test physique doit être ciblé et l’état après commande relevé ; aucune modification de consigne sanitaire ou câblage n’est implicite.
- [ ] **Step 4: Exécuter les scénarios réels disponibles.** Surplus suffisant pour un seul appareil puis pour les deux, passage nuageux, planning, chauffe HC et commande manuelle locale ; vérifier l’absence d’ordres concurrents. Les cas non reproductibles restent couverts par simulation et identifiés comme tels.
- [ ] **Step 5: Mettre à jour la documentation de livraison.** Donner dépôt privé, paquet/image, tag et digest, Compose, état exact des essais, sauvegarde/restauration et limites restantes. L’intégration de retour HA et Tempo restent des évolutions nommées, sans bouton prétendument actif.
- [ ] **Step 6: Commit.** `git add README.md compose.yaml docs/deployment && git commit -m "docs: record deployment and hardware acceptance results"`.

## Après la base

1. Préparer le plan de l’intégration HA de retour : bibliothèque cliente de l’API locale, config flow, appareils/entités stables, états indisponibles et commandes passant par le même moteur.
2. Préparer le plan EDF Tempo : source annoncée, journée de 6 h à 6 h, interdictions et anticipations compatibles avec les créneaux, règles en cas de couleur inconnue.

## Auto-relecture du plan

- Couverture : architecture et persistance (1), sources (2), solaire et nuages (3), horaires (4), connecteurs (5–7), reprise et manuel (8), interface (9), distribution privée (10), essais réels (11).
- Chaque contrat consommé est produit dans une tâche précédente ; les tâches réseau et interface réutilisent les mêmes types et la même API.
- Les cinq situations de Review Focus sont affectées à des tests nommés ; les essais matériels sont séparés des résultats simulés.
- Les actions qui dépendent de comptes ou de matériel ne sont pas remplacées par une réussite fictive. Une indisponibilité laisse les autres tâches réalisables et un état de validation ouvert.
- Aucun code produit, workflow de publication ou Compose prétendument prêt n’a été ajouté au dépôt par la seule rédaction de ce plan.
