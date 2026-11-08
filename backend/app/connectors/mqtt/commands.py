import math
from app.api.schedules import save_programs
from app.connectors.mqtt.entities import Entity, _short
from app.runtime.device_modes import DeviceNotFound, ModeRefused, apply_manual, apply_pause, apply_resume
from app.settings import SettingsDocument

CAR_MODES = {'planned': 'Auto', 'manual': 'Manuel', 'off': 'Pause'}  # SEM mode -> Home Assistant label
MODE_KEY = 'car_mode'


def program_key(program_id: str) -> str:
    return f'program_{program_id}_target'


def command_entities(config: SettingsDocument) -> list[Entity]:
    entities = []
    for device in config.devices:
        if device.kind != 'charger': continue
        name = 'SEM – ' + device.name
        # Modes without a label (solar, off_peak_solar) are published as 'None': Home Assistant reads it as unknown.
        entities.append(Entity(device.id, MODE_KEY, 'select', 'Mode de la voiture', name,
                               CAR_MODES.get(device.mode, 'None'), command=True, options=tuple(CAR_MODES.values())))
        if not device.vehicle_id: continue
        entities += [Entity(device.id, program_key(program.id), 'number', f'Objectif – {program.name}', name,
                            _short(program.target_soc), unit='%', command=True, minimum=1, maximum=100, step=1)
                     for program in config.schedules if program.vehicle_id == device.vehicle_id]
    return entities


CUT = 40  # characters of an incoming payload (or topic part) that may reach the journal
MODES = {label: mode for mode, label in CAR_MODES.items()}


def _cut(text: str) -> str: return text[:CUT]


class CommandHandler:
    """Applies Home Assistant commands received on `<topic>/<device>/<key>/set`."""

    def __init__(self, state_provider): self.state_provider = state_provider

    async def handle(self, prefix: str, topic: str, payload: str) -> tuple[str, str] | None:
        """Returns the (group, key) to publish again, or None when the topic is not one of ours."""
        parts, head = topic.split('/'), prefix.split('/')
        if len(parts) != len(head) + 3 or parts[:len(head)] != head or parts[-1] != 'set': return None
        device_id, key = parts[-3], parts[-2]
        state = self.state_provider()
        async with state.coordinator.lock:
            journal = state.store.journal
            config = SettingsDocument.model_validate(state.store.load_settings())
            if not config.mqtt.commands_enabled: return None
            payload = payload.strip()
            if not any((e.group, e.key) == (device_id, key) for e in command_entities(config)):
                journal.write('WARN', 'mqtt', f'Commande Home Assistant ignorée : cible inconnue {_cut(device_id)}/{_cut(key)}')
                return None
            if key == MODE_KEY: self._mode(state, config, device_id, payload)
            else: self._target(state, config, key, payload)
            return device_id, key

    @staticmethod
    def _mode(state, config, device_id, option):
        journal = state.store.journal
        if option not in MODES:
            journal.write('WARN', 'mqtt', f'Commande Home Assistant ignorée : mode inconnu « {_cut(option)} »')
            return
        if CAR_MODES.get(next(d.mode for d in config.devices if d.id == device_id)) == option:
            # Repeating the active mode must not command the charger again (e.g. Auto would drop its engine state).
            journal.write('INFO', 'mqtt', f'Mode {option} déjà actif (demande Home Assistant)')
            return
        try:
            if option == CAR_MODES['planned']: apply_resume(state, device_id, mode='planned')
            elif option == CAR_MODES['manual']: apply_manual(state, device_id, duration_minutes=240, origin='home_assistant')
            else: apply_pause(state, device_id)
        except (ModeRefused, DeviceNotFound) as error:
            journal.write('WARN', 'mqtt', f'Commande Home Assistant refusée : {option} – {error}')
            return
        if option == CAR_MODES['manual'] and state.coordinator.red_peak_active:
            # Accepted: it is the user's decision; the warning is shown on the Home Assistant side.
            journal.write('INFO', 'mqtt', 'Manuel demandé depuis Home Assistant pendant les heures pleines rouges')
        else: journal.write('INFO', 'mqtt', f'Mode {option} demandé depuis Home Assistant')

    @staticmethod
    def _target(state, config, key, payload):
        journal = state.store.journal
        program = next(p for p in config.schedules if program_key(p.id) == key)  # the entity exists, so the program does
        try:
            if not payload.isascii() or '_' in payload: raise ValueError
            value = float(payload)
            if not math.isfinite(value) or not 1 <= value <= 100: raise ValueError
        except ValueError:
            journal.write('WARN', 'mqtt', f'Commande Home Assistant ignorée : objectif invalide « {_cut(payload)} »')
            return
        program.target_soc = value
        try: save_programs(state.store, config.schedules)
        except ValueError as error:
            journal.write('WARN', 'mqtt', f'Commande Home Assistant ignorée : {error}')
            return
        journal.write('INFO', 'mqtt', f'Objectif du programme « {program.name} » réglé à {value:g} % depuis Home Assistant')
