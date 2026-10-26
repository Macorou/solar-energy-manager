from dataclasses import asdict
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import BaseModel
from app.api.auth import require_auth
from app.settings import DeviceConfig,SettingsDocument
from app.connectors.ocpp.registry import ChargerAdapter
from app.domain.measurements import utcnow

router=APIRouter(prefix='/api/v1/chargers',dependencies=[Depends(require_auth)])


class ArmRequest(BaseModel):
    confirm_control:bool=False
    offline_behavior_verified:bool=False
    capabilities_verified:bool=False


def find_device(request,device_id,kind='charger'):
    config=SettingsDocument.model_validate(request.app.state.store.load_settings())
    device=next((d for d in config.devices if d.id==device_id and d.kind==kind),None)
    if not device:
        raise HTTPException(404,'Appareil introuvable')
    return config,device


def save_config(request,config):
    request.app.state.store.save_settings(SettingsDocument.model_validate(config.model_dump(mode='json')).model_dump(mode='json'))


@router.get('')
def listing(request:Request):
    return [d for d in request.app.state.store.load_settings()['devices'] if d['kind']=='charger']


@router.post('',status_code=201)
def add(body:DeviceConfig,request:Request):
    config=SettingsDocument.model_validate(request.app.state.store.load_settings())
    if body.kind!='charger' or any(d.id==body.id for d in config.devices):
        raise HTTPException(409,'Type ou identifiant non valide')
    body=body.model_copy(update={'armed':False,'capabilities_verified':False,'offline_behavior_verified':False})
    config.devices.append(body)
    save_config(request,config)
    return body


@router.put('/{device_id}')
def update(device_id:str,body:DeviceConfig,request:Request):
    config,old=find_device(request,device_id)
    if body.id!=device_id or body.kind!='charger':
        raise HTTPException(422,'Identité non valide')
    config.devices=[body.model_copy(update={'armed':False,'capabilities_verified':False,
        'offline_behavior_verified':False}) if d.id==device_id else d for d in config.devices]
    save_config(request,config)
    return {'ok':True,'requires_rearming':True}


@router.delete('/{device_id}')
def delete(device_id:str,request:Request):
    config,device=find_device(request,device_id)
    if device.armed:
        raise HTTPException(409,'Mettre en pause et désactiver avant de supprimer')
    config.devices=[d for d in config.devices if d.id!=device_id]
    save_config(request,config)
    return {'ok':True}


@router.post('/{device_id}/test')
async def test(device_id:str,request:Request):
    config,device=find_device(request,device_id)
    return asdict(await ChargerAdapter(request.app.state.ocpp,device).probe_capabilities())


@router.post('/{device_id}/arm')
def arm(device_id:str,body:ArmRequest,request:Request):
    config,device=find_device(request,device_id)
    report=request.app.state.ocpp.probes.get(device_id)
    if not request.app.state.ocpp.state(device_id).connected or not report or 'limit_current' not in report.supported:
        raise HTTPException(409,'Connecter la borne et vérifier ses capacités OCPP')
    if not config.site_limit_w or not device.vehicle_id or device.min_power_w<=0 or device.max_power_w<device.min_power_w:
        raise HTTPException(409,'Renseigner limites, véhicule et puissances avant activation')
    if not all((body.confirm_control,body.offline_behavior_verified,body.capabilities_verified)):
        raise HTTPException(422,'Confirmer les essais de contrôle et le comportement hors ligne')
    armed=device.model_copy(update={'armed':True,'capabilities_verified':True,'offline_behavior_verified':True})
    config.devices=[armed if d.id==device_id else d for d in config.devices]
    save_config(request,config)
    request.app.state.store.append_event({'kind':'armed','device_id':device_id,'details':{'verified_at':utcnow().isoformat()}})
    return {'ok':True}
