from contextlib import asynccontextmanager
from pathlib import Path
import os
import secrets
from fastapi import FastAPI, Depends, Request
from app.settings import RuntimeSettings, SettingsDocument
from app.storage.database import SQLiteStore
from app.storage.secrets import SecretStore
from app.api.auth import router as auth_router, require_auth
from app.api.connections import router as connections_router
from app.api.schedules import router as schedules_router
from app.api.tariffs import router as tariffs_router
from app.connectors.ocpp.registry import OcppRegistry
from app.connectors.ocpp.server import register_server
from app.api.chargers import router as chargers_router
from app.api.vehicles import router as vehicles_router
from app.connectors.peugeot.client import PeugeotAdapter
from app.settings import PeugeotConfig
from app.api.water_heaters import router as water_heaters_router


def create_app(settings: RuntimeSettings | None = None) -> FastAPI:
    settings = settings or RuntimeSettings(
        data_dir=Path(os.environ.get('SEM_DATA_DIR', '/data')),
        secure_cookie=os.environ.get('SEM_SECURE_COOKIE') == 'true',
        public_url=os.environ.get('SEM_PUBLIC_URL', ''), start_runtime=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    existed = (settings.data_dir / 'app.db').exists()
    if existed and not (settings.data_dir / 'secrets' / 'master.key').exists():
        raise RuntimeError('Missing encryption key for existing database')
    store = SQLiteStore(settings.data_dir / 'app.db')
    secret_store = SecretStore(store, settings.data_dir / 'secrets' / 'master.key', existed)
    bootstrap = settings.data_dir / 'bootstrap-token'
    if not bootstrap.exists():
        fd = os.open(bootstrap, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            output.write(secrets.token_urlsafe(32))
    if not store.load_settings():
        store.save_settings(SettingsDocument().model_dump(mode='json'))

    @asynccontextmanager
    async def lifespan(app):
        coordinator = getattr(app.state, 'coordinator', None)
        if coordinator and settings.start_runtime:
            await coordinator.start()
        yield
        if coordinator and settings.start_runtime:
            await coordinator.stop()

    app = FastAPI(title='Solar Energy Manager', version='0.1.0', lifespan=lifespan)
    app.state.store = store
    app.state.secrets = secret_store
    app.state.runtime_settings = settings
    app.state.login_attempts = {}
    app.state.ocpp=OcppRegistry(store,lambda:store.load_settings().get('devices',[]),secret_store.get)
    app.state.peugeot=PeugeotAdapter(secret_store,PeugeotConfig.model_validate(store.load_settings()['peugeot']))
    app.state.ariston_adapters={}
    register_server(app,app.state.ocpp)
    app.include_router(auth_router)
    app.include_router(connections_router)
    app.include_router(schedules_router)
    app.include_router(tariffs_router)
    app.include_router(chargers_router)
    app.include_router(vehicles_router)
    app.include_router(water_heaters_router)

    @app.get('/api/v1/health/live')
    def health():
        return {'status': 'ok', 'version': '0.1.0'}

    @app.get('/api/v1/system/status', dependencies=[Depends(require_auth)])
    def status():
        return {'version': '0.1.0', 'simulation': False, 'runtime': 'not_started'}

    @app.get('/api/v1/settings', dependencies=[Depends(require_auth)])
    def read_settings():
        return store.load_settings()

    @app.put('/api/v1/settings', dependencies=[Depends(require_auth)])
    def write_settings(body: SettingsDocument):
        store.save_settings(body.model_dump(mode='json'))
        return {'ok': True}

    return app
