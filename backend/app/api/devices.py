from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import BaseModel,Field,SecretStr
from datetime import timedelta
import asyncio
from app.api.auth import require_auth
from app.settings import SettingsDocument
from app.domain.measurements import utcnow

router=APIRouter(prefix='/api/v1',dependencies=[Depends(require_auth)])


def lookup(request,device_id):
    config=SettingsDocument.model_validate(request.app.state.store.load_settings())
    device=next((d for d in config.devices if d.id==device_id),None)
    if not device: raise HTTPException(404,'Appareil introuvable')
    return config,device


class ManualRequest(BaseModel):
    duration_minutes:int=Field(30,ge=1,le=720,description='Durée du mode manuel du ballon. Ignorée pour la voiture : le mode manuel reste actif jusqu’à une intervention utilisateur.')


@router.post('/devices/{device_id}/meter-read')
async def meter_read(device_id:str,request:Request):
    _,device=lookup(request,device_id)
    if device.kind!='charger':raise HTTPException(409,'Lecture réservée aux bornes OCPP')
    from app.connectors.ocpp.registry import ChargerAdapter
    try:
        accepted=await asyncio.wait_for(ChargerAdapter(request.app.state.ocpp,device).request_meter(),10)
    except Exception:accepted=False
    if not accepted:raise HTTPException(409,'La borne ne permet pas cette demande de mesure ou est hors connexion')
    return {'ok':True,'status':'meter_requested'}


@router.post('/devices/{device_id}/manual')
def manual(device_id:str,body:ManualRequest,request:Request):
    config,device=lookup(request,device_id)
    if not device.armed: raise HTTPException(409,'Activer et vérifier cet appareil avant une commande')
    values=request.app.state.store.get('manual_controls',{})
    previous=values.get(device_id,{}).get('previous_mode',device.mode)
    values[device_id]={'until':None if device.kind=='charger' else (utcnow()+timedelta(minutes=body.duration_minutes)).isoformat(),
                       'previous_mode':previous if previous!='manual' else 'off'}
    request.app.state.store.set('manual_controls',values)
    device.mode='manual'
    request.app.state.store.save_settings(config.model_dump(mode='json'))
    request.app.state.store.append_event({'kind':'manual','device_id':device_id,
        'details':{'duration_minutes':None if device.kind=='charger' else body.duration_minutes,
                   'persistent':device.kind=='charger','origin':'web'}})
    return {'ok':True,'until':values[device_id]['until']}


@router.post('/devices/{device_id}/pause')
def pause(device_id:str,request:Request):
    config,device=lookup(request,device_id)
    modes=request.app.state.store.get('paused_modes',{})
    manuals=request.app.state.store.get('manual_controls',{})
    previous=manuals.get(device_id,{}).get('previous_mode') if device.mode=='manual' else device.mode
    if previous in ('solar','planned','off_peak_solar'): modes[device_id]=previous
    request.app.state.store.set('paused_modes',modes)
    manuals.pop(device_id,None)
    request.app.state.store.set('manual_controls',manuals)
    device.mode='off'
    request.app.state.store.save_settings(config.model_dump(mode='json'))
    request.app.state.coordinator.engine.forget(device_id)
    return {'ok':True,'status':'stop_requested'}


@router.post('/devices/{device_id}/resume')
def resume(device_id:str,request:Request):
    config,device=lookup(request,device_id)
    if not device.armed: raise HTTPException(409,'Appareil non activé')
    record=request.app.state.coordinator.dispatcher.records.get(device_id)
    if record and record['status']=='unknown': raise HTTPException(409,'Vérifier et acquitter le résultat inconnu')
    automatic_modes=('solar','planned','off_peak_solar')
    manuals=request.app.state.store.get('manual_controls',{})
    previous_manual=manuals.get(device_id,{}).get('previous_mode') if device.mode=='manual' else None
    previous_pause=request.app.state.store.get('paused_modes',{}).get(device_id)
    device.mode=next((mode for mode in (device.mode,previous_manual,previous_pause)
                      if mode in automatic_modes),'solar')
    manuals.pop(device_id,None)
    request.app.state.store.set('manual_controls',manuals)
    request.app.state.store.save_settings(config.model_dump(mode='json'))
    request.app.state.coordinator.engine.forget(device_id)
    return {'ok':True}


@router.post('/devices/{device_id}/disarm')
def disarm(device_id:str,request:Request):
    config,device=lookup(request,device_id)
    runtime=request.app.state.coordinator
    state=runtime.snapshot.device_states.get(device_id)
    power=state.observed_power if state else None
    if device.mode!='off' or not power or not power.usable(utcnow(),config.sample_max_age_s) or power.value>20:
        raise HTTPException(409,'Mettre en pause et attendre une mesure électrique confirmant l’arrêt')
    device.armed=False
    device.capabilities_verified=False; device.offline_behavior_verified=False
    request.app.state.store.save_settings(config.model_dump(mode='json'))
    runtime.dispatcher.records.pop(device_id,None); runtime.dispatcher.save()
    runtime.reservations.pop(device_id,None); runtime.errors.pop(device_id,None)
    runtime.engine.charger_limit_faults.discard(device_id)
    runtime.engine.charger_fault_retry.pop(device_id,None)
    runtime.engine.timers.since.pop(device_id+':cap_unapplied',None)
    runtime.engine.charger_commanded.pop(device_id,None)
    runtime.store.set('charger_limit_faults',sorted(runtime.engine.charger_limit_faults))
    runtime.engine.forget(device_id)
    return {'ok':True}


class OcppCredentials(BaseModel): password:SecretStr|None=None


@router.get('/connections/ocpp')
def ocpp_connections(request:Request):
    registry=request.app.state.ocpp
    identities=sorted({device.charge_point_id for device in registry.devices() if device.charge_point_id})
    return {'stations':[{'station_id':identity,
        'credentials_saved':request.app.state.secrets.present('ocpp_'+identity),
        'connected':identity in registry.stations,'last_error':registry.connection_errors.get(identity),
        'firmware':registry.metadata.get(identity,{}).get('firmware')} for identity in identities]}


@router.put('/connections/ocpp/{station_id}')
def credentials(station_id:str,body:OcppCredentials,request:Request):
    devices=request.app.state.ocpp.devices(station_id)
    if not devices: raise HTTPException(404,'Borne non enregistrée')
    value=body.password.get_secret_value() if body.password else ''
    if not value and request.app.state.secrets.present('ocpp_'+station_id):return {'ok':True,'retained':True}
    if any(d.armed for d in devices): raise HTTPException(409,'Désactiver la borne avant de changer son accès')
    if len(value)<12: raise HTTPException(422,'Au moins 12 caractères requis')
    request.app.state.secrets.set('ocpp_'+station_id,value)
    return {'ok':True}


@router.get('/state')
def state(request:Request): return request.app.state.coordinator.public_state()


@router.get('/events')
def events(request:Request): return request.app.state.store.events()


@router.get('/state/stream')
async def stream(request:Request):
    from starlette.responses import StreamingResponse
    from fastapi.encoders import jsonable_encoder
    import asyncio,json
    async def generate():
        for _ in range(360):
            if await request.is_disconnected(): break
            yield 'data: '+json.dumps(jsonable_encoder(request.app.state.coordinator.public_state()))+'\n\n'
            await asyncio.sleep(2)
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'Cache-Control':'no-store'})
