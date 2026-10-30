from contextlib import asynccontextmanager
from pathlib import Path
import os
import secrets
from fastapi import FastAPI, Depends, Request, HTTPException
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
from app.api.devices import router as devices_router
from app.api.simulation import router as simulation_router
from app.api.sessions import router as sessions_router
from app.runtime.coordinator import Coordinator


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

    app = FastAPI(title='Solar Energy Manager', version='0.1.20', lifespan=lifespan)
    app.state.store = store
    app.state.secrets = secret_store
    app.state.runtime_settings = settings
    app.state.login_attempts = {}
    app.state.ocpp=OcppRegistry(store,lambda:store.load_settings().get('devices',[]),secret_store.get)
    app.state.peugeot=PeugeotAdapter(secret_store,PeugeotConfig.model_validate(store.load_settings()['peugeot']))
    app.state.ariston_adapters={}
    app.state.coordinator=Coordinator(store,app)
    app.state.ocpp.on_transaction=app.state.coordinator.engine.forget
    register_server(app,app.state.ocpp)
    app.include_router(auth_router)
    app.include_router(connections_router)
    app.include_router(schedules_router)
    app.include_router(tariffs_router)
    app.include_router(chargers_router)
    app.include_router(vehicles_router)
    app.include_router(water_heaters_router)
    app.include_router(devices_router)
    app.include_router(simulation_router)
    app.include_router(sessions_router)

    @app.get('/api/v1/health/live')
    def health():
        return {'status': 'ok', 'version': '0.1.20'}

    @app.get('/api/v1/system/status', dependencies=[Depends(require_auth)])
    def status():
        return {'version': '0.1.20', 'simulation': False,
                'runtime': 'running' if app.state.coordinator.running else 'not_started'}

    @app.get('/api/v1/settings', dependencies=[Depends(require_auth)])
    def read_settings():
        return store.load_settings()

    @app.put('/api/v1/settings', dependencies=[Depends(require_auth)])
    def write_settings(body: SettingsDocument):
        previous=SettingsDocument.model_validate(store.load_settings())
        old={d.id:d for d in previous.devices}
        new={d.id:d for d in body.devices}
        protected=('armed','capabilities_verified','offline_behavior_verified')
        identity=('kind','charge_point_id','connector_id','vehicle_id','gateway_id','min_power_w',
                  'max_power_w','phases','grid_phases','voltage','min_current_a','max_current_a','allow_insecure_identity','ocpp_profile')
        for device in body.devices:
            prior=old.get(device.id)
            if any(getattr(device,p) != (getattr(prior,p) if prior else False) for p in protected):
                raise HTTPException(409,'Utiliser la procédure dédiée d’activation ou de désactivation')
            if prior and prior.armed and any(getattr(device,p)!=getattr(prior,p) for p in identity):
                raise HTTPException(409,'Désactiver avant de modifier les caractéristiques de l’appareil')
            if (prior and prior.armed and device.kind=='water_heater'
                and (device.target,device.solar_target)!=(prior.target,prior.solar_target)):
                source=app.state.ariston_adapters.get(device.id)
                if not source or not all(source.temperature_allowed(t) for t in
                    (device.target,device.solar_target if device.solar_target is not None else device.target)):
                    raise HTTPException(409,'Vérifier la connexion et les limites de température natives avant de modifier les consignes réseau et solaire')
        if any(d.armed and d.id not in new for d in previous.devices):
            raise HTTPException(409,'Désactiver avant suppression')
        store.save_settings(body.model_dump(mode='json'))
        return {'ok': True}

    static_dir=Path(os.environ.get('SEM_STATIC_DIR',str(Path(__file__).resolve().parents[2] / 'frontend' / 'dist')))
    if not static_dir.exists():
        static_dir=Path(__file__).resolve().parents[3]/'frontend'/'dist'
    if static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount('/',StaticFiles(directory=static_dir,html=True),name='web')
    return app
