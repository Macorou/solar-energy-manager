from dataclasses import asdict
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import BaseModel,SecretStr
from app.api.auth import require_auth
from app.api.chargers import find_device,save_config,ArmRequest
from app.settings import DeviceConfig,SettingsDocument,AristonConfig
from app.connectors.ariston.client import AristonAdapter

router=APIRouter(prefix='/api/v1',dependencies=[Depends(require_auth)])


def adapter(request, device):
    adapters = request.app.state.ariston_adapters
    if device.id not in adapters or adapters[device.id].config != device:
        config=SettingsDocument.model_validate(request.app.state.store.load_settings())
        adapters[device.id]=AristonAdapter(device,config.ariston.username,
            request.app.state.secrets.get('ariston_password') or '')
    return adapters[device.id]


class AristonInput(BaseModel):
    config:AristonConfig
    password:SecretStr | None=None


@router.put('/connections/ariston')
def configure(body:AristonInput,request:Request):
    config=SettingsDocument.model_validate(request.app.state.store.load_settings())
    config.ariston=body.config
    save_config(request,config)
    if body.password: request.app.state.secrets.set('ariston_password',body.password.get_secret_value())
    request.app.state.ariston_adapters.clear()
    return {'ok':True}


@router.get('/water-heaters')
def listing(request:Request):
    return [d for d in request.app.state.store.load_settings()['devices'] if d['kind']=='water_heater']


@router.post('/water-heaters',status_code=201)
def add(body:DeviceConfig,request:Request):
    config=SettingsDocument.model_validate(request.app.state.store.load_settings())
    if body.kind!='water_heater' or any(d.id==body.id for d in config.devices):
        raise HTTPException(409,'Type ou identifiant non valide')
    config.devices.append(body.model_copy(update={'armed':False,'capabilities_verified':False,
                                                  'offline_behavior_verified':False}))
    save_config(request,config)
    return {'ok':True}


@router.put('/water-heaters/{device_id}')
def update(device_id:str,body:DeviceConfig,request:Request):
    config,device=find_device(request,device_id,'water_heater')
    if device.armed: raise HTTPException(409,'Désactiver avant de modifier la configuration matérielle')
    if body.id!=device_id or body.kind!='water_heater': raise HTTPException(422,'Identité invalide')
    config.devices=[body.model_copy(update={'armed':False,'capabilities_verified':False,
        'offline_behavior_verified':False}) if d.id==device_id else d for d in config.devices]
    save_config(request,config)
    return {'ok':True,'requires_rearming':True}


@router.delete('/water-heaters/{device_id}')
def delete(device_id:str,request:Request):
    config,device=find_device(request,device_id,'water_heater')
    if device.armed: raise HTTPException(409,'Désactiver avant suppression')
    config.devices=[d for d in config.devices if d.id!=device_id]
    save_config(request,config)
    return {'ok':True}


@router.post('/water-heaters/{device_id}/test')
async def test(device_id:str,request:Request):
    _,device=find_device(request,device_id,'water_heater')
    source=adapter(request,device)
    try:
        state=await source.connect()
        return {'state':asdict(state),'capabilities':asdict(await source.probe_capabilities())}
    except Exception: raise HTTPException(400,'Connexion Ariston indisponible ou appareil non pris en charge') from None


@router.post('/water-heaters/{device_id}/arm')
def arm(device_id:str,body:ArmRequest,request:Request):
    config,device=find_device(request,device_id,'water_heater')
    source=adapter(request,device)
    if not source.state.connected or not source.report or not {'start','suspend','set_temperature'} <= set(source.report.supported):
        raise HTTPException(409,'Vérifier la connexion et les commandes natives')
    if (not config.site_limit_w or device.min_power_w<=0 or device.max_power_w<=0 or
        device.target is None or device.id not in config.home_assistant.device_power_entities):
        raise HTTPException(409,'Renseigner puissance, consigne, limite du site et mesure électrique du ballon')
    if not all((body.confirm_control,body.capabilities_verified,body.offline_behavior_verified)):
        raise HTTPException(422,'Confirmer les essais natifs et le comportement hors ligne')
    config.devices=[d.model_copy(update={'armed':True,'capabilities_verified':True,
        'offline_behavior_verified':True}) if d.id==device_id else d for d in config.devices]
    save_config(request,config)
    return {'ok':True}
