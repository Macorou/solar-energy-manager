from datetime import timedelta
from app.settings import SettingsDocument
from app.domain.measurements import utcnow


class DeviceNotFound(LookupError): pass
class ModeRefused(ValueError): pass


def find(state,device_id):
    config=SettingsDocument.model_validate(state.store.load_settings())
    device=next((d for d in config.devices if d.id==device_id),None)
    if not device: raise DeviceNotFound('Appareil introuvable')
    return config,device


def apply_manual(state,device_id:str,duration_minutes:int=30,origin:str='web')->str|None:
    config,device=find(state,device_id)
    if not device.armed: raise ModeRefused('Activer et vérifier cet appareil avant une commande')
    values=state.store.get('manual_controls',{})
    previous=values.get(device_id,{}).get('previous_mode',device.mode)
    values[device_id]={'until':None if device.kind=='charger' else (utcnow()+timedelta(minutes=duration_minutes)).isoformat(),
                       'previous_mode':previous if previous!='manual' else 'off'}
    state.store.set('manual_controls',values)
    device.mode='manual'
    state.store.save_settings(config.model_dump(mode='json'))
    state.store.append_event({'kind':'manual','device_id':device_id,
        'details':{'duration_minutes':None if device.kind=='charger' else duration_minutes,
                   'persistent':device.kind=='charger','origin':origin}})
    return values[device_id]['until']


def apply_pause(state,device_id:str)->None:
    config,device=find(state,device_id)
    modes=state.store.get('paused_modes',{})
    manuals=state.store.get('manual_controls',{})
    previous=manuals.get(device_id,{}).get('previous_mode') if device.mode=='manual' else device.mode
    if previous in ('solar','planned','off_peak_solar'): modes[device_id]=previous
    state.store.set('paused_modes',modes)
    manuals.pop(device_id,None)
    state.store.set('manual_controls',manuals)
    device.mode='off'
    state.store.save_settings(config.model_dump(mode='json'))
    state.coordinator.engine.forget(device_id)


def apply_resume(state,device_id:str,mode:str|None=None)->None:
    config,device=find(state,device_id)
    if not device.armed: raise ModeRefused('Appareil non activé')
    record=state.coordinator.dispatcher.records.get(device_id)
    if record and record['status']=='unknown': raise ModeRefused('Vérifier et acquitter le résultat inconnu')
    automatic_modes=('solar','planned','off_peak_solar')
    manuals=state.store.get('manual_controls',{})
    previous_manual=manuals.get(device_id,{}).get('previous_mode') if device.mode=='manual' else None
    previous_pause=state.store.get('paused_modes',{}).get(device_id)
    device.mode=mode or next((m for m in (device.mode,previous_manual,previous_pause)
                              if m in automatic_modes),'solar')
    manuals.pop(device_id,None)
    state.store.set('manual_controls',manuals)
    state.store.save_settings(config.model_dump(mode='json'))
    state.coordinator.engine.forget(device_id)
