from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, SecretStr
from app.api.auth import require_auth
from app.settings import VehicleConfig, SettingsDocument, PeugeotConfig
from app.connectors.peugeot.client import ProviderError

router = APIRouter(prefix='/api/v1', dependencies=[Depends(require_auth)])


@router.get('/vehicles')
def vehicles(request: Request): return request.app.state.store.load_settings()['vehicles']


@router.put('/vehicles')
def save_vehicles(body: list[VehicleConfig],request:Request):
    settings = request.app.state.store.load_settings()
    settings['vehicles'] = [v.model_dump(mode='json') for v in body]
    try: checked = SettingsDocument.model_validate(settings)
    except ValueError: raise HTTPException(422,'Références véhicule invalides') from None
    request.app.state.store.save_settings(checked.model_dump(mode='json'))
    return {'ok':True}


class PeugeotInput(BaseModel):
    config: PeugeotConfig
    refresh_token: SecretStr | None = None
    client_secret: SecretStr | None = None


@router.put('/connections/peugeot')
def configure(body: PeugeotInput, request: Request):
    settings = request.app.state.store.load_settings()
    settings['peugeot'] = body.config.model_dump(mode='json')
    request.app.state.store.save_settings(settings)
    for field,key in [('refresh_token','peugeot_refresh'),('client_secret','peugeot_client_secret')]:
        value = getattr(body,field)
        if value: request.app.state.secrets.set(key,value.get_secret_value())
    request.app.state.peugeot.config = body.config
    request.app.state.peugeot.expires = request.app.state.peugeot.expires.min.replace(
        tzinfo=request.app.state.peugeot.expires.tzinfo)
    return {'ok':True}


@router.post('/connections/peugeot/auth')
def begin(request: Request): return request.app.state.peugeot.begin_auth()


class Callback(BaseModel): response: SecretStr


@router.post('/connections/peugeot/complete')
async def complete(body:Callback,request:Request):
    try: return await request.app.state.peugeot.complete_auth(body.response.get_secret_value())
    except ProviderError as error: raise HTTPException(400,str(error)) from None


@router.post('/connections/peugeot/test')
async def test(request:Request):
    try:
        await request.app.state.peugeot.refresh_access()
        return {'ok':True}
    except ProviderError as error: raise HTTPException(400,str(error)) from None
