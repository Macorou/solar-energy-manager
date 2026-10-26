from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, SecretStr
from app.api.auth import require_auth
from app.settings import HomeAssistantConfig
from app.connectors.home_assistant.client import HomeAssistantSource

router = APIRouter(prefix='/api/v1', dependencies=[Depends(require_auth)])


class HomeAssistantInput(BaseModel):
    config: HomeAssistantConfig
    token: SecretStr | None = None


@router.get('/connections')
def connections(request: Request):
    return {'home_assistant': request.app.state.secrets.present('ha_token'),
            'peugeot': request.app.state.secrets.present('peugeot_refresh'),
            'ariston': request.app.state.secrets.present('ariston_password')}


@router.post('/connections/home-assistant/test')
async def test_ha(body: HomeAssistantInput, request: Request):
    token = body.token.get_secret_value() if body.token else request.app.state.secrets.get('ha_token')
    if not token:
        raise HTTPException(422,'Accès Home Assistant requis')
    source = HomeAssistantSource(body.config,token)
    try:
        await source.connect()
        sample = source.snapshot().grid
        return {'ok':True,'grid_available':bool(sample and sample.value is not None),
                'entity_count':len(source.states)}
    except Exception:
        raise HTTPException(400,'Connexion ou mesures Home Assistant non valides') from None
    finally:
        await source.close()


@router.put('/connections/home-assistant')
def configure_ha(body: HomeAssistantInput, request: Request):
    settings = request.app.state.store.load_settings()
    settings['home_assistant'] = body.config.model_dump(mode='json')
    request.app.state.store.save_settings(settings)
    if body.token:
        request.app.state.secrets.set('ha_token',body.token.get_secret_value())
    return {'ok':True}


@router.get('/measurements')
def measurements(request: Request):
    coordinator = getattr(request.app.state,'coordinator',None)
    return coordinator.public_state() if coordinator else {'grid':None,'solar':None,'devices':[]}
