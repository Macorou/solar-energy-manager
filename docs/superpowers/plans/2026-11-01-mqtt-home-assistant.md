# MQTT → Home Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish SEM's decisions, battery estimate and three EUR/kWh energy prices (site, car, water heater) to Home Assistant through MQTT discovery, read-only. The car price follows a "car served last" rule, which the charging-session cost also adopts.

**Architecture:**
- A pure pricing module computes each device's grid share. The coordinator's public state exposes the prices, and the charging tracker uses the car share for session cost.
- A separate `MqttService` asyncio task, independent from the 2 s control loop, maps the coordinator's public state to Home Assistant entities and publishes them through a client abstraction. `aiomqtt` sits behind a factory so tests use a fake client.
- New settings section `mqtt`, password in `SecretStore`, REST endpoints, and a card plus form in Réglages → Intégrations → Services locaux.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, asyncio, aiomqtt, pytest/pytest-asyncio (`asyncio_mode = auto`), React 19, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-01-mqtt-home-assistant-design.md`. Read it first. Its "Précisions" section is binding.

## Global Constraints

- Repository root: `C:\Users\jorda\Documents\Codex\2026-10-26\en\outputs\solar-energy-manager\.worktrees\v1`.
- Git:
  - prefix every git command with `git -c safe.directory='*'`;
  - **never** `git add -A`, `git add .`, `git clean`, `git reset --hard` or `git stash -u`;
  - **no commit and no push** during execution: leave changes uncommitted; the controller asks the user at the end;
  - **never open, read, stage or modify `docs/next-patch.md`**.
- Backend tests:
  - Python is `C:/Users/jorda/AppData/Local/Temp/claude/H--DEV-Claude-Solar-Energy-Manager/f6fe42a1-0d40-4c5f-a6b4-b90954ca40c2/scratchpad/venv312/Scripts/python.exe`;
  - command: `SEM_DATA_DIR=<fresh empty scratch dir> <python> -m pytest -q -p no:cacheprovider --basetemp=<fresh scratch dir> <tests>`;
  - scratch dirs live under `C:/Users/jorda/AppData/Local/Temp/claude/H--DEV-Claude-Solar-Energy-Manager/ed784aab-8025-4b7e-ac44-a8f39938deda/scratchpad`.
- Frontend: `npm --prefix frontend test`, then `npm --prefix frontend run build` (it runs `tsc --noEmit`).
- No test touches real equipment, the production volume, a real Home Assistant or a real MQTT broker.
- Text and copy:
  - all user-facing text is French;
  - code comments in English, matching the sparse existing style;
  - existing files use LF line endings; keep them.
- Never publish or log: MQTT password, tokens, VIN, e-mail addresses.
- MQTT must never block, slow or raise into `Coordinator.run`/`tick`. A broker failure only changes the MQTT status and writes a journal line on state change.
- Throttle: power and price entities are published at most every **10 s** each. Other entities are published as soon as they change.
- Price precision: **3 decimals**, unit `EUR/kWh`. A missing input gives an **unavailable** entity, never `0`.
- Defaults: topic `sem`, discovery prefix `homeassistant`, client id `sem-` + random suffix (stable for the process lifetime). An empty topic or an empty broker means publication is disabled.
- Pin new Python dependencies exactly (`==`) in `backend/pyproject.toml`, choosing a release at least two weeks old.

## Review Focus

1. **Broker down or hanging at start-up or mid-run:** control continues, ticks complete, and the status shows "Hors connexion". Pinned in Task 4.
2. **Tariff sensor missing at night while the car imports:** the car price is unavailable, not 0. With the car on full solar and no tariff, the solar price is used. Pinned in Task 1.
3. **Home Assistant restarts** (`homeassistant/status` → `online`): discovery is re-sent, so entities come back without restarting SEM. Pinned in Task 4.
4. **A device renamed or removed in SEM while MQTT runs:** names update and removed devices' entities are cleared. This holds across SEM restarts because the announced set is persisted. Pinned in Task 3.
5. **Password with special characters:** it never appears in the journal, the API responses or the settings document. Pinned in Task 5.

---

### Task 1: Energy prices (grid shares, car served last)

**Files:**
- Create: `backend/app/runtime/energy_prices.py`
- Modify: `backend/app/runtime/coordinator.py`, in `public_state()`: add the `energy_prices` key
- Test: `tests/backend/test_energy_prices.py`

**Interfaces:**
- Consumes: `SiteSnapshot` (`grid`, `price`, `device_states`, `at`), `SettingsDocument` (`devices`, `solar_price_per_kwh`, `sample_max_age_s`), and `mix_context` from `app.runtime.charging` (site price, unchanged).
- Produces:
  - `grid_shares(snapshot: SiteSnapshot, config: SettingsDocument) -> dict[str, float | None]`: device id → grid fraction in [0, 1], or None, for every charger and water heater in `config.devices`.
  - `price_from_share(share: float | None, tariff: float | None, solar_price: float) -> float | None`.
  - `device_prices(snapshot, config) -> dict[str, float | None]`: device id → EUR/kWh, rounded to 3 decimals.
  - `public_state()['energy_prices'] == {'site': float | None, 'devices': {device_id: float | None}}`. The site value is `self.charging.effective_price` rounded to 3 decimals; the devices map is `device_prices(replace(self.snapshot, at=now), config)`.

Rules for `grid_shares` (binding; from the spec, "Calcul des prix" and "Précisions" 2–3):
- `import = max(0, grid.value)` if `snapshot.grid` is usable at `snapshot.at` with `config.sample_max_age_s`. Otherwise every share is None.
- Order of import attribution: chargers first, then water heaters. Within each kind, sort by `priority` descending, so the least prioritary device (largest number) takes import first.
- Power of a device:
  - if `observed_power` is usable: `max(0, value)`;
  - else if the device is not active by state: 0;
  - else None. A charger is active by state when `connected` and `observed_state == 'Charging'`; a water heater when `observed_state == 'on'`.
- Walk the order with `remaining = import`:
  - power None → this share and every later share are None;
  - power ≤ 20 W (idle) → share = 1.0 if `remaining > 0`, else 0.0, and `remaining` is unchanged;
  - otherwise `grid = min(power, remaining)`, `share = grid / power`, `remaining -= grid`.
- `price_from_share`:
  - None share → None;
  - share 0 → `solar_price`, even if the tariff is None;
  - tariff None with share > 0 → None;
  - else `share * tariff + (1 - share) * solar_price`.

- [ ] **Step 1: Write the failing tests** in `tests/backend/test_energy_prices.py`. Build snapshots with `Sample(value, 'W', 'test', now, now, checked_at=now)`, as in `tests/backend/test_car_solar_target.py`, and `SettingsDocument(devices=[...], solar_price_per_kwh=0)` with a charger `ev` (priority 1) and a water heater `tank` (priority 2).
  - `test_reference_example`: import 2000, car `Charging` 3000 W, heater `on` 2500 W, tariff 0.165:
    - `grid_shares == {'ev': pytest.approx(2/3), 'tank': 0.0}`;
    - `device_prices == {'ev': 0.110, 'tank': 0.0}`.
  - `test_idle_car_pays_tariff_when_site_imports_and_solar_when_exporting`: car `Preparing` with 0 W:
    - grid 500 → `ev` 0.165;
    - grid −800 → `ev` 0.0.
  - `test_idle_heater_pays_tariff_only_when_import_exceeds_the_car`: heater `off` 0 W, car charging 3000 W:
    - grid 2000 → `tank` 0.0;
    - grid 3500 → `tank` 0.165.
  - `test_missing_grid_makes_every_price_unavailable`: `grid=None` → all None.
  - `test_missing_tariff`:
    - `price=None`, car charging 3000 W, grid −500 → `ev` 0.0 (full solar);
    - grid 1000 → `ev` None.
  - `test_unknown_running_car_power_makes_later_prices_unknown`: car `Charging` with a stale power sample (`measured_at = now - 120 s`) → `ev` None and `tank` None.
  - `test_unplugged_car_with_stale_power_counts_as_zero`: car `Available`, stale sample, heater on 2500 W, grid 1000 → `tank` `pytest.approx(0.066)`.
  - `test_least_prioritary_charger_takes_import_first`: chargers `a` (priority 1) and `b` (priority 2), each 2000 W, grid 2000 → `b` share 1.0, `a` share 0.0.
  - `test_public_state_exposes_energy_prices` (async, uses `Coordinator(SQLiteStore(tmp_path/'db'))`, like `tests/backend/test_charging_accounting.py`): after `await runtime.tick(frame)`, `runtime.public_state()['energy_prices']` has keys `site` and `devices`, and `devices['ev']` equals `device_prices(...)` for that frame.
- [ ] **Step 2: Run** `tests/backend/test_energy_prices.py`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `grid_shares`, `price_from_share` and `device_prices` in `backend/app/runtime/energy_prices.py`, and add `energy_prices` to `Coordinator.public_state()`.
- [ ] **Step 4: Run** the new tests, then the full backend suite. Expected: all PASS.

---

### Task 2: Session cost follows the car share

**Files:**
- Modify: `backend/app/runtime/charging.py`, in `ChargingTracker.update`, where the context `entry=[now,fraction,price,config.solar_price_per_kwh]` is built (currently near line 147)
- Test: `tests/backend/test_charging_accounting.py`

**Interfaces:**
- Consumes: `grid_shares` (Task 1).
- Produces: there is no new interface. Each charger's context `fraction` becomes `grid_shares(snapshot, config)[device.id]`, computed once per `update` call. `mix_context` still sets `self.effective_price` (site) and supplies `price`.

- [ ] **Step 1: Write the failing test** `test_session_cost_uses_the_car_share_not_the_site_mix`:
  - Use the `frame` helper pattern with an added water heater `tank` (`kind='water_heater'`) drawing 2000 W `on` from solar. Grid +2000 (import), solar 2000, car charging 2000 W, tariff 0.2.
  - Feed two frames 30 s apart, with the car meter going from 10 000 to 12 000 Wh.
  - Assert `summary('ev')['cost_eur'] == pytest.approx(0.4)` (all grid) and `summary('ev')['solar_percent'] == pytest.approx(0)`. The site mix would have given 0.2 and 50 %.
- [ ] **Step 2: Run** it. Expected: FAIL (cost 0.2).
- [ ] **Step 3: Implement.** Replace the site `fraction` with the car share in the charger context entry. Keep the existing "append when changed or every 10 s" condition, applied to the new value.
- [ ] **Step 4: Run** the full backend suite. Expected: PASS.
  - If an existing accounting test changes value, check it with the car-last rule.
  - Update only expectations the new rule explains, and list each one in the task report with old → new values and why.
  - If unsure whether a change is explained, stop and report instead of editing.

---

### Task 3: Home Assistant entity model and publisher

**Files:**
- Create: `backend/app/connectors/mqtt/__init__.py` (empty), `backend/app/connectors/mqtt/entities.py`, `backend/app/connectors/mqtt/publisher.py`
- Test: `tests/connectors/test_mqtt_entities.py`, `tests/connectors/test_mqtt_publisher.py`

**Interfaces:**
- Consumes: the dict returned by `Coordinator.public_state()`, including Task 1's `energy_prices`, and `SettingsDocument`.
- Produces:
  - In `entities.py`, a frozen dataclass `Entity(group: str, key: str, component: str, name: str, device_name: str, value: str | None, unit: str | None = None, device_class: str | None = None, state_class: str | None = None, precision: int | None = None, attributes: dict | None = None, throttled: bool = False)`.
    - `group` is `'site'` or a SEM device id.
    - `component` is `'sensor'` or `'binary_sensor'`.
    - `value` None means unavailable. Binary values are `'ON'`/`'OFF'`.
  - In `entities.py`, `build_entities(state: dict, config: SettingsDocument, now: datetime) -> list[Entity]`.
  - In `publisher.py`, `class Publisher(client, prefix: str, discovery_prefix: str, store)`, where `client` has `async publish(topic: str, payload: str, retain: bool) -> None`. Methods:
    - `async announce(entities: list[Entity]) -> None`: discovery for each entity, then removal (empty retained config) for every `(component, group, key)` previously announced but absent now. The announced set is persisted in `store` under the key `mqtt_announced`, as a list of `[component, group, key]`.
    - `async publish(entities: list[Entity], mono: float) -> None`: availability and state, honouring the throttle.
    - `async clear() -> None`: empty retained configs for everything in `mqtt_announced`, then reset it to `[]`.
- Topics (binding for all tasks):
  - availability (global): `<prefix>/status`, `online`/`offline`, retained;
  - state: `<prefix>/<group>/<key>/state`, retained;
  - per-entity availability: `<prefix>/<group>/<key>/available`, `online`/`offline`, retained;
  - attributes: `<prefix>/<group>/<key>/attributes`, JSON, retained, only when `attributes` is not None;
  - discovery: `<discovery_prefix>/<component>/sem_<group>/<key>/config`, retained JSON with:
    - `name`, `unique_id: sem_<group>_<key>`, `object_id: sem_<group>_<key>`, `state_topic`;
    - `availability: [{topic: <prefix>/status}, {topic: .../available}]`, `availability_mode: 'all'`;
    - optional `unit_of_measurement`, `device_class`, `state_class`, `suggested_display_precision`, `json_attributes_topic`;
    - `device: {identifiers: ['sem_<group>'], name: device_name, manufacturer: 'Solar Energy Manager', model: 'SEM'}`.

Entity catalogue (binding names, keys and units; `name` is the French label):
- **Site** (`group='site'`, `device_name='SEM – Installation'`):
  - `price` « Prix de l'énergie du site », EUR/kWh, measurement, precision 3, throttled;
  - `surplus` « Surplus solaire disponible », W, power, measurement, throttled;
  - `off_peak` binary « Heures creuses »;
  - `control_active` binary « Pilotage actif »: `state['running']` and `state['at']` less than 30 s before `now`;
  - `problem` « Problème en cours »: the first value of `state['errors']`, translated (see below), `''` if none.
- **Each charger** (`device_name='SEM – ' + config name`):
  - `price` « Prix de l'énergie de la voiture » (as for site);
  - `battery` « Batterie », %, battery, attributes `{'source': 'estimée'|'relevée'}`. Use `charging.soc` if `charging.active` and it is not None, with source `estimée` if `soc_estimated`; else the vehicle telemetry soc with source `relevée`;
  - `range` « Autonomie », km, distance;
  - `power` « Puissance de charge », W, power, throttled. Use `state.observed_power.value` when `usable`;
  - `state` « État »;
  - `reason` « Raison »;
  - `mode` « Mode »;
  - `plugged` binary « Voiture branchée », device_class plug (`state.vehicle_connected is True`);
  - `target` « Objectif », %: `default_soc_target` if mode is manual, else `authorization.target_soc`, else `default_soc_target`;
  - `solar_target` « Objectif sur surplus solaire », %: `config.solar_target` if mode is not manual and it is greater than the target, else unavailable;
  - `session_energy` « Énergie de la session », kWh, energy, state_class `total`;
  - `session_cost` « Coût de la session », EUR, monetary, state_class `total`;
  - `session_solar` « Part solaire de la session », %;
  - `plan_warning` « Avertissement du programme », `''` if none.
- **Each water heater**:
  - `price` « Prix de l'énergie du ballon »;
  - `temperature` « Température », °C, temperature;
  - `target` « Consigne en cours », °C, temperature (`effective_target`), attributes `{'source': 'solaire'|'réseau'}` from `target_source`;
  - `power` « Puissance de chauffe », W, throttled;
  - `state`, `reason` and `mode`, as for the car.
- `state` text, mirroring the `DeviceCard` badge:
  - `state.fault` or command status `unknown` → `À vérifier`;
  - connected with usable power > 20 and observed state in `Charging`/`on` → `En charge` (charger) or `En chauffe` (heater);
  - command status `sending`/`accepted` → `En attente de confirmation`;
  - not armed → `Observation`;
  - not connected → `Hors connexion`;
  - else `En attente`.
- `mode` text:
  - not armed → `Observation`;
  - `manual` → `Manuel`;
  - `off` → `Pause`;
  - else `Automatique`.
- Error translation for `problem`:
  - `{'not_configured':'Peugeot non configuré','reconnect_required':'Reconnexion Peugeot nécessaire','rate_limited':'Limite de requêtes Peugeot atteinte','vehicle_not_found':'Véhicule introuvable chez Peugeot','vin_required':'VIN du véhicule à renseigner','provider_unavailable':'Service indisponible'}`;
  - any other value is published as is: these are French messages produced by SEM.
- Numbers are formatted as strings: prices with 3 decimals, powers as integers, °C/%/km with at most 1 decimal, kWh with 2, EUR with 2. No VIN, e-mail, username or `charge_point_id` ever goes into a name, an id or an attribute.

Throttle rule: an entity's state is published when its value differs from the last published value. For `throttled` entities, it is also required that at least 10 s (`mono`) have passed since that entity's last publish; otherwise the newest value waits for a later `publish` call. Availability is published on change, immediately.

- [ ] **Step 1: Write the failing tests** in `tests/connectors/test_mqtt_entities.py`, using a hand-built `state` dict shaped like `public_state()` with one charger `ev` and one heater `tank`.
  - `test_catalogue_keys_units_and_device_names`: the set of `(group, key)` and the units match the catalogue; `device_name` values are `'SEM – Installation'` and `'SEM – ' + name`.
  - `test_prices_are_three_decimals_and_none_is_unavailable`: `energy_prices.devices.ev = 0.11` gives `'0.110'`; None gives `value is None`.
  - `test_mode_and_state_labels`: armed `planned` → `Automatique`; unarmed → `Observation`; command `unknown` → state `À vérifier`.
  - `test_battery_source`: an active session with an estimated soc gives source `estimée`; no session gives the telemetry soc and source `relevée`.
  - `test_problem_translates_provider_codes`: `{'vehicle_car': 'reconnect_required'}` → `Reconnexion Peugeot nécessaire`.
  - `test_no_vin_or_identity_leaks`: put a VIN-like value in `config.vehicles[0].vin`, an e-mail in `peugeot.username` and `charge_point_id='CP-SECRET'`. The JSON of all entities, including the discovery payloads built by the publisher, contains none of them.
- [ ] **Step 2: Write the failing tests** in `tests/connectors/test_mqtt_publisher.py`, with a `FakeClient` recording `(topic, payload, retain)` and a real `SQLiteStore(tmp_path/'db')`.
  - `test_discovery_payload_shape`: for the site price, the topic is `homeassistant/sensor/sem_site/price/config`; the payload has `unique_id == 'sem_site_price'`, `unit_of_measurement == 'EUR/kWh'`, `suggested_display_precision == 3`, two availability topics and `retain=True`.
  - `test_unavailable_value_publishes_offline_availability_not_zero`.
  - `test_throttled_entity_waits_ten_seconds`:
    - power 1000 at mono 0 is published;
    - 1200 at mono 5 is not published;
    - at mono 10, 1200 is published;
    - a non-throttled text change at mono 5 is published at once.
  - `test_removed_device_is_cleared_even_after_restart`: announce with `ev`, create a new `Publisher` on the same store, announce without `ev` → empty retained payloads for every `ev` config topic.
  - `test_renamed_device_updates_discovery_name`.
- [ ] **Step 3: Run** both test files. Expected: FAIL (modules missing).
- [ ] **Step 4: Implement** `entities.py` and `publisher.py` to the interfaces above.
- [ ] **Step 5: Run** both test files, then the full backend suite. Expected: PASS.

---

### Task 4: Settings section and the MQTT service

**Files:**
- Modify: `backend/app/settings.py`: add `MqttConfig`, plus `SettingsDocument.mqtt: MqttConfig = Field(default_factory=MqttConfig)`
- Modify: `backend/pyproject.toml`: add `aiomqtt==<pinned>` to `dependencies`
- Create: `backend/app/connectors/mqtt/service.py`
- Modify: `backend/app/main.py`: build `app.state.mqtt` and start/stop it in `lifespan` when `settings.start_runtime`, after the coordinator starts and before it stops
- Test: `tests/connectors/test_mqtt_service.py`

**Interfaces:**
- Consumes: `build_entities` and `Publisher` (Task 3); `SecretStore.get('mqtt_password')`.
- Produces:
  - `class MqttConfig(Model)`, with the existing `Model` base (`extra='forbid'`):
    - `broker: str = ''`: empty, or `host:port` with port 1–65535 and no whitespace or `/`;
    - `topic: str = 'sem'`: empty, or a topic without `#`, `+`, whitespace, or a leading/trailing `/`;
    - `client_id: str = ''`;
    - `username: str = ''`;
    - `allow_self_signed: bool = False`;
    - `tls: bool = False`;
    - `discovery_prefix: str = 'homeassistant'`: same rule as `topic`, and not empty.

    Invalid values raise `ValueError` with a French message. `MqttConfig.enabled` is a property, true when both `broker` and `topic` are non-empty.
  - `class MqttService(store, secrets, state_provider: Callable[[], dict], client_factory=None)` with:
    - `async start()` and `async stop()`;
    - `status() -> dict`, returning `{'state': 'disabled'|'connecting'|'connected'|'disconnected', 'last_publish_at': str | None, 'error': str | None}`. `last_publish_at` is an ISO string;
    - `async test(config: MqttConfig, password: str | None) -> None`: raises `ValueError` with a French message;
    - `async remove(config: MqttConfig, password: str | None) -> bool`: connects, calls `Publisher.clear()`, publishes `offline`; returns False if the broker is unreachable.
  - `client_factory(config: MqttConfig, password: str | None, client_id: str, will_topic: str)` returns an async context manager yielding a client with:
    - `async publish(topic, payload, retain)`;
    - `async subscribe(topic)`;
    - an async iterator `messages()` yielding `(topic: str, payload: str)`.

    The default factory wraps `aiomqtt.Client` with the hostname and port from `broker`, `username`/`password` when set, `identifier=client_id`, `will` = `will_topic` / `offline` / retain, keepalive 30, and TLS when `tls` is set. Certificate verification is disabled only when `allow_self_signed` is set.
- Loop behaviour:
  - every 2 s, reload settings;
  - disabled → status `disabled`, disconnect if connected;
  - a change of config or password → reconnect;
  - on connect: publish `<topic>/status` `online` retained, `announce`, subscribe to `<discovery_prefix>/status`;
  - each cycle: `publish(build_entities(state_provider(), config, utcnow()), time.monotonic())`, then `announce` again when the set of `(component, group, key)` or any name changed;
  - on `<discovery_prefix>/status` = `online`: `announce` again;
  - every client call is wrapped in `asyncio.wait_for(..., 5)`;
  - any exception → status `disconnected`, `error` ∈ {`Courtier injoignable`, `Authentification refusée`, `Échange MQTT interrompu`}, a journal `WARN` area `mqtt` only when status or error changes, then retry with backoff 5 → 60 s;
  - a successful publish sets `last_publish_at`;
  - `state_provider` exceptions are caught the same way;
  - `stop()` publishes `offline` best-effort, without blocking more than 5 s.

- [ ] **Step 1: Pick and pin** the newest `aiomqtt` 2.x release that is at least two weeks old, and install it in the venv. Run `<python> -c "import aiomqtt; print(aiomqtt.__version__)"`. Expected: the pinned version.
- [ ] **Step 2: Write the failing tests** in `tests/connectors/test_mqtt_service.py`, with a fake factory and a stub `state_provider`.
  - `test_mqtt_config_validation`:
    - `broker='192.168.1.30:1883'` is valid;
    - `'host'`, `'host:0'`, `'host:70000'`, `'a b:1883'` and topic `'sem/#'` are invalid;
    - `MqttConfig().enabled is False`.
  - `test_disabled_when_broker_empty`: status `disabled`, factory never called.
  - `test_connect_announces_and_publishes_online`.
  - `test_reannounces_when_home_assistant_comes_back_online`: the fake yields `('homeassistant/status', 'online')` → config topics are published again.
  - `test_broker_down_sets_disconnected_and_control_loop_still_ticks`:
    - the factory raises `OSError`;
    - status becomes `disconnected` with error `Courtier injoignable`;
    - while the service runs, `await asyncio.wait_for(coordinator.tick(frame), 5)` completes for a real `Coordinator` on a temp store.
  - `test_hanging_publish_does_not_block_ticks`: the fake `publish` awaits forever; ticks still complete within 5 s, and the status leaves `connected` after the 5 s timeout.
  - `test_reconnects_on_config_change`.
  - `test_default_factory_options` (monkeypatch `aiomqtt.Client` to capture kwargs): the will topic is `sem/status` with `offline`; TLS is off by default; insecure TLS only with `allow_self_signed`.
- [ ] **Step 3: Run.** Expected: FAIL.
- [ ] **Step 4: Implement** `MqttConfig`, `MqttService`, the default factory and the `main.py` wiring.
- [ ] **Step 5: Run** the new tests, then the full backend suite. Expected: PASS.

---

### Task 5: REST API, secret deletion, OpenAPI

**Files:**
- Modify: `backend/app/storage/secrets.py`: `delete(name: str) -> None`, idempotent
- Create: `backend/app/api/mqtt.py`, included in `main.py`
- Modify: `backend/app/api/connections.py`: `GET /connections` adds `'mqtt': bool(settings mqtt.broker)`
- Regenerate: `backend/openapi.json` (`<python> scripts/export_openapi.py`) and `frontend/src/api/schema.ts` (`npm --prefix frontend run types`)
- Test: `tests/backend/test_mqtt_api.py`, `tests/backend/test_secrets.py`

**Interfaces:**
- Consumes: `MqttConfig` and `app.state.mqtt` (`MqttService`), from Task 4.
- Produces, all under `/api/v1`, with `require_auth`:
  - `PUT /connections/mqtt`, body `{config: MqttConfig, password: SecretStr | None}`: validates through `SettingsDocument`, saves `settings['mqtt']`, sets secret `mqtt_password` when a password is given.
    - When the previous config was enabled and the new one is not (empty topic or broker), it first calls `service.remove(previous config, stored password)`, so the entities disappear from Home Assistant.
    - Returns `{'ok': True, 'entities_removed': bool | None}`, with None when nothing was disabled; 422 with a French detail on invalid config.
  - `POST /connections/mqtt/test`, same body: the password falls back to the stored secret; calls `service.test`. Returns `{'ok': True}`, or 400 with the `ValueError` message.
  - `DELETE /connections/mqtt`: calls `service.remove(current config, stored password)`, resets `settings['mqtt']` to `MqttConfig()` dumped, and deletes the secret. Returns `{'ok': True, 'entities_removed': bool}`.
  - `GET /connections/mqtt/status`: returns `service.status()`.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/backend/test_secrets.py`: `test_delete_removes_secret_and_is_idempotent`.
  - In `tests/backend/test_mqtt_api.py`, using `service()` and `setup()` from `tests/backend/test_bootstrap.py`, and replacing `app.state.mqtt` with a stub recording calls:
    - `test_put_saves_config_and_password_never_returned`: password `'p@ss:w/rd#é'`. `GET /api/v1/settings` has `mqtt.broker` and no password anywhere in its JSON. `secrets.get('mqtt_password')` equals the password. The journal export (`GET /api/v1/logs/export` or the store journal rows) does not contain it.
    - `test_put_rejects_invalid_topic` → 422.
    - `test_put_disabling_removes_entities`: an enabled config, then a PUT with `topic=''` → the stub `remove` is called once with the previous config; the response has `entities_removed`.
    - `test_test_endpoint_uses_stored_password_and_reports_french_error`.
    - `test_delete_clears_config_secret_and_reports_cleanup`: the stub `remove` returns False → `entities_removed` False; settings `mqtt.broker == ''`; secret absent.
    - `test_status_endpoint`.
    - `test_connections_reports_mqtt`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the endpoints and `SecretStore.delete`. Regenerate `openapi.json` and `schema.ts`.
- [ ] **Step 4: Run** the full backend suite and `git -c safe.directory='*' diff --stat -- backend/openapi.json frontend/src/api/schema.ts`. Expected: the tests pass and both files show the `MqttConfig` additions.

---

### Task 6: Settings card and form

**Files:**
- Modify: `frontend/src/api/types.ts`: `export type MqttConfig = Complete<components['schemas']['MqttConfig']>` and `export interface MqttStatus {state:'disabled'|'connecting'|'connected'|'disconnected';last_publish_at:string|null;error:string|null}`
- Modify: `frontend/src/pages/Settings.tsx`:
  - the `Editor` connection name union gains `'mqtt'`;
  - the title map gains `mqtt:'MQTT'`;
  - the « Services locaux » group gets a third card, with count `"3 services"`;
  - the integration picker gains MQTT;
  - the status is polled from `/connections/mqtt/status`, alongside the existing OCPP refresh.
- Modify: `frontend/src/settings/ConnectionForm.tsx`: the `section` union gains `'mqtt'`, plus the form below.
- Modify the test fixtures that build a full `Settings` (`Settings.test.tsx`, `SettingsCards.test.tsx`, `DraftPreservation.test.tsx`): add `mqtt:{broker:'',topic:'sem',client_id:'',username:'',allow_self_signed:false,tls:false,discovery_prefix:'homeassistant'}`.
- Test: `frontend/src/settings/MqttForm.test.tsx` and the existing `frontend/src/pages/SettingsCards.test.tsx`.

**Interfaces:**
- Consumes: the Task 5 endpoints and `api()` from `frontend/src/api/client.ts`.
- Card « MQTT »:
  - subtitle `Home Assistant · découverte automatique`; icon `ha`;
  - badge:
    - `connected` → green `Connecté`;
    - `connecting`/`disconnected` → amber `Hors connexion`;
    - `disabled` → neutral `Désactivé`;
    - unreadable status → neutral `État indisponible`;
  - row `Dernier envoi`: a local time, or `—`;
  - note: `status.error`, else `Lecture seule`.
- Form, with exact labels and hints from the spec and the EVCC model:
  - `Courtier`, hint `Exemple : 192.168.1.30:1883`;
  - `Sujet`, hint `Laisser vide pour désactiver la publication.`;
  - `Identifiant client`, placeholder `sem-[aléatoire]`;
  - `Nom d'utilisateur`;
  - `Mot de passe`: type password, placeholder `Conservé si vide` when `connections.mqtt`, emptied after save;
  - checkbox `Autoriser les certificats auto-signés`;
  - a `<details>` « Paramètres avancés » with checkbox `Connexion chiffrée (TLS)` and `Préfixe de découverte Home Assistant`;
  - buttons:
    - `Tester` → POST test, message `Connexion MQTT réussie`;
    - `Supprimer` → `window.confirm('Supprimer la connexion MQTT ?')`, then DELETE, message `Connexion MQTT supprimée` or, when `entities_removed` is false, `Connexion supprimée : entités à supprimer à la main dans Home Assistant (courtier injoignable)`;
    - `Enregistrer` → PUT, message `Connexion MQTT enregistrée`.

- [ ] **Step 1: Write the failing tests.**
  - In `MqttForm.test.tsx`, mocking `api`:
    - save sends a PUT with the config and the password, and the password field is empty afterwards;
    - test posts and shows the success message;
    - delete asks for confirmation and shows the manual-cleanup message when `entities_removed` is false.
  - In `SettingsCards.test.tsx`: the « MQTT » card shows `Connecté` for a `connected` status, and the group count reads `3 services`.
- [ ] **Step 2: Run** `npm --prefix frontend test`. Expected: FAIL.
- [ ] **Step 3: Implement** the types, the card, the form and the fixtures.
- [ ] **Step 4: Run** `npm --prefix frontend test` and `npm --prefix frontend run build`. Expected: PASS, build OK.

---

### Task 7: Final verification

- [ ] **Step 1:** Run the full backend suite on a fresh `SEM_DATA_DIR`. Expected: all pass; the data dir is still empty afterwards.
- [ ] **Step 2:** Run `npm --prefix frontend test` and `npm --prefix frontend run build`. Expected: pass.
- [ ] **Step 3:** Run `<python> scripts/export_openapi.py && npm --prefix frontend run types`, then `git -c safe.directory='*' diff --exit-code -- backend/openapi.json frontend/src/api/schema.ts` after staging nothing. Expected: no drift beyond this plan's changes, which is the CI check.
- [ ] **Step 4:** Run `git -c safe.directory='*' status --short`. Expected: only files named in this plan are changed or added, and `docs/next-patch.md` is untouched and untracked. No commit is made; report the file list to the controller.
