from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, SecretStr
from app.api.auth import require_auth
from app.settings import MqttConfig, SettingsDocument

router = APIRouter(prefix='/api/v1', dependencies=[Depends(require_auth)])
PASSWORD = 'mqtt_password'


class MqttInput(BaseModel):
    config: MqttConfig
    password: SecretStr | None = None


def current(request: Request, settings: dict) -> MqttConfig:
    return MqttConfig.model_validate(settings.get('mqtt') or {})


@router.put('/connections/mqtt')
async def configure_mqtt(body: MqttInput, request: Request):
    state = request.app.state
    settings = state.store.load_settings()
    previous = current(request, settings)
    settings['mqtt'] = body.config.model_dump(mode='json')
    try: checked = SettingsDocument.model_validate(settings)
    except ValueError: raise HTTPException(422, 'Configuration MQTT non valide') from None
    removed = None
    if previous.enabled and not body.config.enabled:
        # Clear the discovery entities with the old settings before they are overwritten.
        removed = await state.mqtt.remove(previous, state.secrets.get(PASSWORD))
    state.store.save_settings(checked.model_dump(mode='json'))
    if body.password:
        state.secrets.set(PASSWORD, body.password.get_secret_value())
    return {'ok': True, 'entities_removed': removed}


@router.post('/connections/mqtt/test')
async def test_mqtt(body: MqttInput, request: Request):
    state = request.app.state
    password = body.password.get_secret_value() if body.password else state.secrets.get(PASSWORD)
    try:
        await state.mqtt.test(body.config, password or None)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    return {'ok': True}


@router.delete('/connections/mqtt')
async def delete_mqtt(request: Request):
    state = request.app.state
    settings = state.store.load_settings()
    removed = await state.mqtt.remove(current(request, settings), state.secrets.get(PASSWORD))
    settings['mqtt'] = MqttConfig().model_dump(mode='json')
    state.store.save_settings(SettingsDocument.model_validate(settings).model_dump(mode='json'))
    state.secrets.delete(PASSWORD)
    return {'ok': True, 'entities_removed': removed}


@router.get('/connections/mqtt/status')
def mqtt_status(request: Request):
    return request.app.state.mqtt.status()
