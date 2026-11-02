# Commandes de la voiture depuis Home Assistant — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Depuis Home Assistant, par MQTT, pouvoir changer le mode de la voiture (Auto/Manuel/Pause) et l'objectif de chaque programme de charge. Le mode Manuel de la voiture repasse en Auto au débranchement.

**Architecture:**
- Les opérations de mode des routes web (`manual`, `pause`, `resume`) sont extraites dans un module partagé, `app/runtime/device_modes.py`. Les routes et les commandes MQTT l'utilisent toutes les deux.
- Un module `app/connectors/mqtt/commands.py` décrit les entités commandables (`select`, `number`) et traite les messages `…/set` sous `coordinator.lock`.
- Le service MQTT s'abonne aux sujets de commande, ignore les messages retenus et republie aussitôt après une commande.
- Le coordinateur détecte le débranchement à chaque `tick`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, asyncio, aiomqtt 2.5.1, SQLite, React 19 + Vitest.

**Spec:** `docs/superpowers/specs/2026-11-01-mqtt-commandes-voiture-design.md`

## Global Constraints

- **Modèles** : les sous-agents qui codent utilisent le modèle `sonnet` (Sonnet 5.5).
- **Git** :
  - aucun commit ni push : le contrôleur commite après accord de l'utilisateur ;
  - jamais `git add -A`, `git add .`, `git clean`, `git reset --hard` ni `git stash -u` ;
  - ne jamais ouvrir, modifier ni indexer `docs/next-patch.md`.
- **Tests** : uniquement avec un `SEM_DATA_DIR` neuf et jetable, et `--basetemp` dans le scratchpad. Jamais contre le volume de production.
  - Python : `/c/Users/jorda/AppData/Local/Temp/claude/H--DEV-Claude-Solar-Energy-Manager/f6fe42a1-0d40-4c5f-a6b4-b90954ca40c2/scratchpad/venv312/Scripts/python.exe`. S'il a disparu, le recréer avec Python 3.12 et `pip install -r backend/requirements.lock pytest pytest-asyncio httpx`.
  - Commande : `SEM_DATA_DIR=$(mktemp -d) "$PY" -m pytest -q -p no:cacheprovider --basetemp <scratch>/pt <fichiers>`.
- **Git sous Windows** : `git -c safe.directory='*'`.
- **Fins de ligne** : conserver celles de chaque fichier. Plusieurs sont en CRLF, dont `backend/app/sessions/service.py` et `frontend/src/settings/ConnectionForm.tsx`. Ne jamais réécrire un fichier entier avec une autre fin de ligne.
- **Textes visibles** : en français, et exactement ceux du spec :
  - `Mode de la voiture`, `Auto`, `Manuel`, `Pause`, `Objectif – <nom>` (tiret demi-cadratin « – ») ;
  - `Autoriser les commandes depuis Home Assistant` ;
  - l'avertissement `Toute personne ou tout appareil ayant accès à votre courtier MQTT pourra changer le mode de charge de la voiture.` ;
  - `Voiture débranchée : fin du mode Manuel, retour en Auto (Planifié)`.
- **Mode Auto** : toujours `planned`.
- **Correspondance des modes** :

  | Mode SEM | Affiché |
  |---|---|
  | `planned` | Auto |
  | `manual` | Manuel |
  | `off` | Pause |
  | autre | `None`, que HA affiche comme « inconnu » |

- **Routes web** : les routes `/devices/{id}/manual|pause|resume` gardent exactement leurs codes, messages et effets actuels.
- **Pas de secrets** : MQTT ne doit jamais casser la boucle de 2 s, et ne journalise ni ne publie aucun secret.

## Review Focus

1. **Accès concurrent** : une commande arrive pendant que `tick()` tient le verrou et réenregistre les réglages. La commande doit attendre le verrou, et sa modification ne doit pas être écrasée. Test : Task 4, `test_command_waits_for_the_coordinator_lock`.
2. **Valeurs d'objectif invalides** (`abc`, `nan`, `0`, `101`, vide) : elles sont ignorées, avec un avertissement dans le journal, sans rien modifier. Test : Task 4, `test_invalid_target_payloads_change_nothing`.
3. **Option de mode inconnue ou mauvaise casse** (`Turbo`, `auto`) : seules les options exactes, espaces retirés, sont acceptées. Test : Task 4, `test_unknown_mode_option_is_refused`.
4. **Commande vers un ballon, un appareil inconnu ou un programme supprimé** : elle est ignorée et journalisée, et le lecteur MQTT continue de tourner. Test : Task 4, `test_commands_for_unknown_targets_are_ignored`.
5. **Commandes désactivées** : aucun abonnement aux sujets `/set`, et un message reçu quand même ne modifie rien. Test : Task 4, `test_commands_disabled_neither_subscribe_nor_apply`.

---

### Task 1: Opérations de mode partagées

**Files:**
- Create: `backend/app/runtime/device_modes.py`
- Modify: `backend/app/api/devices.py` (routes `manual`, `pause`, `resume`, et la description de `ManualRequest.duration_minutes`)
- Test: `tests/runtime/test_device_modes.py` (nouveau), plus `tests/runtime/test_resume_modes.py` et `tests/runtime/test_persistent_manual.py`, qui doivent passer sans modification

**Interfaces:**
- Produces (dans `app.runtime.device_modes`) :
  - `class DeviceNotFound(LookupError)`, message `'Appareil introuvable'` ;
  - `class ModeRefused(ValueError)`, avec le message HTTP actuel ;
  - `def apply_manual(state, device_id: str, duration_minutes: int = 30, origin: str = 'web') -> str | None` : renvoie `until` (ISO) ou `None` ;
  - `def apply_pause(state, device_id: str) -> None` ;
  - `def apply_resume(state, device_id: str, mode: str | None = None) -> None`. Avec `mode=None`, le comportement de `resume` est inchangé. Avec `mode='planned'`, la règle de choix est remplacée par ce mode ; les contrôles d'activation et de résultat inconnu restent.
- Dans ces trois fonctions, `state` est un objet qui expose `.store` et `.coordinator` (en pratique `request.app.state`).

- [ ] **Step 1: Write the failing tests** in `tests/runtime/test_device_modes.py`, using `service` from `test_resume_modes`:

```python
def test_resume_to_planned_leaves_manual_and_clears_controls(tmp_path):
    app, client = service(tmp_path, 'charger', 'solar')
    apply_manual(app.state, 'device', origin='home_assistant')
    apply_resume(app.state, 'device', mode='planned')
    assert app.state.store.load_settings()['devices'][0]['mode'] == 'planned'
    assert 'device' not in app.state.store.get('manual_controls', {})

def test_manual_records_its_origin(tmp_path):
    app, _ = service(tmp_path, 'charger', 'planned')
    apply_manual(app.state, 'device', origin='home_assistant')
    event = app.state.store.events()[0]
    assert event['kind'] == 'manual' and event['details']['origin'] == 'home_assistant'

def test_refusals_keep_the_web_messages(tmp_path):
    app, _ = service(tmp_path, 'charger', 'planned')
    config = app.state.store.load_settings(); config['devices'][0]['armed'] = False
    app.state.store.save_settings(config)
    with pytest.raises(ModeRefused, match='Activer et vérifier cet appareil avant une commande'):
        apply_manual(app.state, 'device')
    with pytest.raises(ModeRefused, match='Appareil non activé'):
        apply_resume(app.state, 'device', mode='planned')
    apply_pause(app.state, 'device')  # always allowed
    with pytest.raises(DeviceNotFound):
        apply_pause(app.state, 'missing')
```

- [ ] **Step 2: Run them.** `pytest tests/runtime/test_device_modes.py -v`. Expected: FAIL, `ModuleNotFoundError: app.runtime.device_modes`.
- [ ] **Step 3: Implement the module.** Move the bodies of the three routes into the three functions, without changing their logic. The routes become wrappers that turn `DeviceNotFound` into 404 and `ModeRefused` into 409, with the same message. Set the `duration_minutes` description to `Durée du mode manuel du ballon. Ignorée pour la voiture : le mode manuel reste actif jusqu’au débranchement de la voiture.`
- [ ] **Step 4: Run the tests.** `pytest tests/runtime/test_device_modes.py tests/runtime/test_resume_modes.py tests/runtime/test_persistent_manual.py tests/runtime/test_manual_heating_cycle.py -v`. Expected: all PASS.

### Task 2: Retour en Auto au débranchement

**Files:**
- Modify: `backend/app/runtime/coordinator.py`. Add the attribute `self.last_plugged: dict[str, bool] = {}` in `__init__`, the method `end_manual_on_unplug`, and its call in `tick()` just after `self.charging.update(snapshot, config)`.
- Test: `tests/runtime/test_manual_unplug.py` (nouveau)

**Interfaces:**
- Produces: `Coordinator.end_manual_on_unplug(self, snapshot: SiteSnapshot, config: SettingsDocument) -> bool`. It returns `True` if it changed at least one mode. It modifies `config` in place, so that `policies()` sees the new mode in the same tick.

**Algorithm** (spec, « Précisions techniques »). For each device of kind `charger`:
- `state = snapshot.device_states.get(id)`.
- **Borne absente ou hors connexion** (`not state or not state.connected`) : `last_plugged.pop(id)`, then go to the next device.
- **`vehicle_connected is True`** : `last_plugged[id] = True`.
- **`vehicle_connected is None`** : nothing changes, and the last known state is kept.
- **`vehicle_connected is False`** : `was = last_plugged.get(id, False)`, then `last_plugged[id] = False`. If `was` and `device.mode == 'manual'`:
  - set `device.mode = 'planned'` ;
  - remove `manual_controls[id]` ;
  - save the settings ;
  - call `self.engine.forget(id)` ;
  - write `journal.write('INFO', 'device:'+id, 'Voiture débranchée : fin du mode Manuel, retour en Auto (Planifié)')`.

- [ ] **Step 1: Write the failing tests.**
  - Build snapshots with `SiteSnapshot(now, device_states={'device': DeviceState('device', None, status, connected, vehicle_connected=v)})`, using `service(tmp_path, 'charger', 'manual')` and `app.state.coordinator`.
  - Parametrize the sequences of `(connected, vehicle_connected)` with the expected final mode:

```python
@pytest.mark.parametrize('sequence,mode', [
    ([(True, True), (True, False)], 'planned'),
    ([(True, True), (True, None), (True, False)], 'planned'),
    ([(True, True), (False, None), (True, False)], 'manual'),
    ([(True, False)], 'manual'),                       # first observation after a restart
    ([(True, False), (True, True)], 'manual'),         # plugging in never changes the mode
])
def test_manual_returns_to_auto_only_on_an_observed_unplug(tmp_path, sequence, mode):
    ...  # call coordinator.end_manual_on_unplug(snapshot, config) for each step, reloading config each time
    assert app.state.store.load_settings()['devices'][0]['mode'] == mode

def test_unplug_leaves_other_modes_alone(tmp_path):  # 'planned' and 'off' are untouched by True -> False
def test_unplug_writes_the_journal_line_and_clears_manual_controls(tmp_path):
```

- [ ] **Step 2: Run them.** `pytest tests/runtime/test_manual_unplug.py -v`. Expected: FAIL, `AttributeError: … end_manual_on_unplug`.
- [ ] **Step 3: Implement it** per the algorithm above, then call it in `tick()`.
- [ ] **Step 4: Run them.** `pytest tests/runtime -q`. Expected: all PASS.

### Task 3: Réglage, entités commandables et annonce

**Files:**
- Modify: `backend/app/settings.py`, adding `commands_enabled: bool = False` to `MqttConfig`.
- Modify: `backend/app/connectors/mqtt/entities.py`.
  - Add these fields to `Entity`, with the defaults shown:
    - `command: bool = False`
    - `options: tuple[str, ...] | None = None`
    - `minimum: float | None = None`
    - `maximum: float | None = None`
    - `step: float | None = None`
  - At the end of `build_entities`, add `if config.mqtt.commands_enabled: entities += command_entities(config)`.
- Create: `backend/app/connectors/mqtt/commands.py`, with `CAR_MODES` and `command_entities`. `CommandHandler` comes in Task 4.
- Modify: `backend/app/connectors/mqtt/publisher.py`. In `discovery()`, when `entity.command`, add:
  - `command_topic = <prefix>/<group>/<key>/set` ;
  - `options` for a `select` ;
  - `min`, `max` and `step` for a `number`.
- Test: `tests/connectors/test_mqtt_entities.py`, `tests/connectors/test_mqtt_publisher.py`, `tests/backend/test_mqtt_api.py`

**Interfaces:**
- Produces (dans `app.connectors.mqtt.commands`) :
  - `CAR_MODES = {'planned': 'Auto', 'manual': 'Manuel', 'off': 'Pause'}` ;
  - `MODE_KEY = 'car_mode'` ;
  - `def program_key(program_id: str) -> str`, which returns `f'program_{program_id}_target'` ;
  - `def command_entities(config: SettingsDocument) -> list[Entity]`.
- **Pour chaque `config.devices` de type `charger`** :
  - un `Entity(group=id, key='car_mode', component='select', name='Mode de la voiture', device_name='SEM – '+name, value=CAR_MODES.get(mode, 'None'), command=True, options=('Auto','Manuel','Pause'))` ;
  - si `vehicle_id` est renseigné, pour chaque programme de `config.schedules` ayant ce `vehicle_id`, actif ou non : `Entity(group=id, key=program_key(p.id), component='number', name=f'Objectif – {p.name}', device_name=…, value=_short(p.target_soc), unit='%', command=True, minimum=1, maximum=100, step=1)`.

- [ ] **Step 1: Write the failing tests.**
  - `test_commands_disabled_add_no_entities` : with the default settings, no entity has `command=True`.
  - `test_car_mode_select_maps_sem_modes` : parametrize `planned→'Auto'`, `manual→'Manuel'`, `off→'Pause'`, `solar→'None'`, `off_peak_solar→'None'`. Also check `options == ('Auto','Manuel','Pause')`.
  - `test_one_target_number_per_program_of_the_car` :
    - two programs of the car (one disabled) and one program of another vehicle give exactly 2 `number` entities ;
    - their names are `'Objectif – Semaine'` and so on ;
    - `value == '80'`, `minimum == 1`, `maximum == 100`, `step == 1` ;
    - a charger without `vehicle_id` has none.
  - `test_discovery_of_command_entities` (publisher) :
    - select : `command_topic == 'sem/ev/car_mode/set'` and `options == ['Auto','Manuel','Pause']` ;
    - number : `min == 1`, `max == 100`, `step == 1`, `unit_of_measurement == '%'` ;
    - a `sensor` has no `command_topic`.
  - `test_select_unknown_state_is_published_as_None` : the `select` stays `online` and its state message is the text `None`.
  - In `test_mqtt_api.py` : a document saved without `commands_enabled` is read back with `commands_enabled: False`, and a `PUT` of `commands_enabled: true` is kept.
- [ ] **Step 2: Run them.** `pytest tests/connectors/test_mqtt_entities.py tests/connectors/test_mqtt_publisher.py tests/backend/test_mqtt_api.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement it** per the Interfaces block.
- [ ] **Step 4: Run them.** Same command. Expected: all PASS.

### Task 4: Traitement des commandes et câblage du service

**Files:**
- Modify: `backend/app/connectors/mqtt/commands.py`, adding `CommandHandler`.
- Modify: `backend/app/api/schedules.py`. Extract `def save_programs(store, programs: list[ChargeProgram]) -> None`, which raises `ValueError('Programme ou véhicule non valide')`. `persist` calls it and turns the error into HTTP 422.
- Modify: `backend/app/connectors/mqtt/service.py` :
  - `_AiomqttSession.messages()` yields `(topic, payload, bool(message.retain))` ;
  - `MqttService.__init__` takes `commands=None` ;
  - subscribe to `f'{topic}/+/+/set'` when `commands_enabled` ;
  - `_read` routes the messages ;
  - add an event `self._wake` that cuts `_sleep` short in the session loop ;
  - add `Publisher.invalidate`.
- Modify: `backend/app/connectors/mqtt/publisher.py`, adding `def invalidate(self, group: str, key: str) -> None`, which forgets `last[(group, key)]` so the next `publish` sends the state again.
- Modify: `backend/app/main.py`, building the service with `commands=CommandHandler(lambda: app.state)`.
- Test: `tests/connectors/test_mqtt_commands.py` (nouveau) and `tests/connectors/test_mqtt_service.py`. The fake `Broker` must be able to inject `(topic, payload, retained)`. `_read` keeps accepting the old 2-tuples (`received, payload, *flags`).

**Interfaces:**
- Consumes: `apply_manual`, `apply_pause`, `apply_resume`, `ModeRefused` and `DeviceNotFound` (Task 1) ; `CAR_MODES`, `MODE_KEY` and `program_key` (Task 3) ; `save_programs`.
- Produces: `class CommandHandler`, with:
  - `__init__(self, state_provider)`, where `state_provider()` returns an object with `.store` and `.coordinator` ;
  - `async def handle(self, prefix: str, topic: str, payload: str) -> tuple[str, str] | None`. It returns the `(group, key)` to republish, or `None` if the topic is not one of its own.
- **Behaviour of `handle`** :
  - it runs entirely under `async with state.coordinator.lock` ;
  - it reloads the settings ;
  - it ignores everything if `mqtt.commands_enabled` is false ;
  - it strips spaces from the payload.
- **`car_mode`** :
  - `Auto` → `apply_resume(..., mode='planned')` ;
  - `Manuel` → `apply_manual(..., origin='home_assistant')` ;
  - `Pause` → `apply_pause`.
  - Accepted : `journal.write('INFO','mqtt', f'Mode {option} demandé depuis Home Assistant')`.
  - Refused : `journal.write('WARN','mqtt', f'Commande Home Assistant refusée : {option} – {message}')`.
- **Program number** :
  - accepts only a finite float from 1 to 100 ;
  - the program must exist and belong to the vehicle of that charger ;
  - `save_programs`, then `journal.write('INFO','mqtt', f'Objectif du programme « {name} » réglé à {value:g} % depuis Home Assistant')`.
- **Anything else** (heater, unknown device, unknown key, invalid value, missing program) : `journal.write('WARN','mqtt', f'Commande Home Assistant ignorée : {raison}')`. The payload is cut to 40 characters. The function returns the `(group, key)` if the entity exists, so it gets republished.
- **Service** :
  - a retained message on a `/set` topic is ignored, with `WARN 'Commande Home Assistant retenue ignorée'` ;
  - a `handle` exception is caught and journaled once, as `ERROR`, with the exception type only ; the reader keeps running ;
  - after `handle`, `publisher.invalidate(*result)` and `self._wake.set()`.

- [ ] **Step 1: Write the failing tests** in `tests/connectors/test_mqtt_commands.py`, with a real `Coordinator(store)` and `SimpleNamespace(store=…, coordinator=…)`, and settings that contain an armed charger `ev`, the vehicle `car`, the program `semaine`, and `mqtt.commands_enabled=True` :

```python
async def test_auto_manual_pause_change_the_mode(...)       # 'Auto' -> planned, 'Manuel' -> manual, 'Pause' -> off; returns ('ev','car_mode')
async def test_refused_manual_is_journaled_and_republished(...)  # charger disarmed: mode unchanged, WARN line, returns ('ev','car_mode')
async def test_program_target_is_saved(...)                 # payload '100' -> schedules[0]['target_soc'] == 100, INFO line
async def test_invalid_target_payloads_change_nothing(...)  # 'abc','nan','0','101','' -> unchanged, WARN
async def test_unknown_mode_option_is_refused(...)          # 'Turbo','auto' -> unchanged; ' Pause ' -> off
async def test_commands_for_unknown_targets_are_ignored(...)  # heater group, 'ghost' device, program of another vehicle, deleted program
async def test_command_waits_for_the_coordinator_lock(...)  # hold coordinator.lock, start handle(), assert not done after 0.05 s, release, assert applied
```

  And in `test_mqtt_service.py` :

```python
async def test_command_message_is_handled_and_state_republished_at_once(...)
async def test_retained_command_is_ignored(...)
async def test_commands_disabled_neither_subscribe_nor_apply(...)
async def test_handler_error_does_not_stop_the_reader(...)
```

  These service tests use a fake handler that records its calls.
- [ ] **Step 2: Run them.** `pytest tests/connectors/test_mqtt_commands.py tests/connectors/test_mqtt_service.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement it** per the Interfaces block.
- [ ] **Step 4: Run them.** `pytest tests/connectors tests/backend/test_mqtt_api.py tests/backend/test_charge_programs.py -q`. Expected: all PASS.

### Task 5: Interface, schéma OpenAPI et vérification complète

**Files:**
- Modify: `frontend/src/settings/ConnectionForm.tsx` (CRLF). In the `mqtt` section :
  - add the checkbox `Autoriser les commandes depuis Home Assistant` (`commands_enabled`) ;
  - add a `<p className="hint">` with the warning text when it is checked ;
  - add `commands_enabled:false` to the `reset` object of the **Supprimer** button.
- Regenerate: `backend/openapi.json` and `frontend/src/api/schema.ts`, with `python scripts/export_openapi.py && npm --prefix frontend run types`.
- Test: `frontend/src/settings/MqttForm.test.tsx`

- [ ] **Step 1: Write the failing test** `it('lets the user allow Home Assistant commands with a warning')` :
  - the checkbox is unchecked by default and the warning is absent ;
  - after a click, the warning text is visible ;
  - **Enregistrer** sends `commands_enabled: true`.
- [ ] **Step 2: Run it.** `npx vitest run src/settings/MqttForm.test.tsx`, from `frontend/`. Expected: FAIL.
- [ ] **Step 3: Implement it**, then regenerate OpenAPI and the types.
- [ ] **Step 4: Run the full verification.**
  - The whole backend suite, with a fresh `SEM_DATA_DIR`. Expected: everything passes, apart from the existing skip.
  - `npx vitest run` and `npm run build`. Expected: OK.
  - Drift check : regenerating `openapi.json` again produces no difference.
