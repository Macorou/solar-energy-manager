import asyncio
from datetime import datetime, timezone
import logging
import math
from ariston import Ariston
from app.domain.devices import DeviceState, CapabilityReport
from app.domain.commands import CommandResult

logging.getLogger('ariston').setLevel(logging.CRITICAL)


class AristonAdapter:
    def __init__(self, config, username='', password='', device=None, journal=None):
        self.config, self.username, self.password = config, username, password
        self.device, self.library = device, None
        self.initialized = False
        self.report = None
        self.state = DeviceState(config.id)
        self.lock = asyncio.Lock()
        self.last_command = None
        self.journal = journal
        if journal:
            journal.redactor.register(password)
            journal.redactor.register(username)

    def log(self,level,message):
        if self.journal:self.journal.write(level,'ariston:'+self.config.id,message)

    async def connect(self):
        async with self.lock:
            if not self.device:
                if not self.username or not self.password: raise RuntimeError('not_configured')
                self.library = Ariston()
                if not await self.library.async_connect(self.username,self.password):
                    raise RuntimeError('connection_failed')
                self.device = await self.library.async_hello(self.config.gateway_id)
                if not self.device: raise RuntimeError('device_unsupported')
            if not self.initialized:
                # Cancellation must leave initialization retryable, even after discovery.
                try: await self.device.async_update_settings()
                except Exception: pass
                self.initialized=True
        return await self.read_state()

    async def read_state(self):
        if not self.device: return DeviceState(self.config.id, fault='not_configured')
        async with self.lock:
            try:
                await self.device.async_update_state()
                temperature = self.device.water_heater_current_temperature
                target = self.device.water_heater_target_temperature
                on = getattr(self.device,'water_heater_power_value',None)
                self.state = DeviceState(self.config.id,connected=True,
                    observed_state='on' if on is True else 'off' if on is False else 'unknown',
                    temperature=temperature,target_temperature=target,
                    target_reached=bool(temperature is not None and self.config.target is not None
                                        and temperature >= self.config.target),
                    measured_at=datetime.now(timezone.utc))
                self.log('DEBUG',f'Lecture réussie : température={temperature} °C ; consigne={target} °C ; état={self.state.observed_state}')
            except Exception as error:
                self.state = DeviceState(self.config.id,fault='provider_unavailable')
                self.log('ERROR',f'Lecture cloud indisponible ({type(error).__name__})')
        return self.state

    async def probe_capabilities(self):
        supported = ['read_temperature'] if self.device else []
        if self.device and callable(getattr(self.device,'async_set_power',None)):
            supported += ['start','suspend']
        if self.device and callable(getattr(self.device,'async_set_water_heater_temperature',None)):
            supported += ['set_temperature']
        report = CapabilityReport(tuple(supported),tuple(c for c in
            ('start','suspend','set_temperature','modulate_power') if c not in supported),
            datetime.now(timezone.utc),False)
        if self.device: self.report=report
        return report

    async def execute(self, intent):
        if not self.initialized:
            try: await self.connect()
            except Exception:
                return CommandResult(intent.id,False,error='native_connection_unavailable')
        async with self.lock:
            report = self.report or await self.probe_capabilities()
            action = {'suspend':'suspend','set_power':'start','set_temperature':'set_temperature'}.get(intent.action)
            if action not in report.supported:
                return CommandResult(intent.id,False,error='unsupported_native_control')
            now = datetime.now(timezone.utc)
            if intent.expires_at and intent.expires_at <= now:
                return CommandResult(intent.id,False,error='expired_command')
            try:
                if action in ('start','set_temperature'):
                    if self.last_command and (now-self.last_command).total_seconds()<60:
                        return CommandResult(intent.id,False,error='native_cooldown')
                    target = intent.target_temperature if intent.target_temperature is not None else self.config.target
                    if not self.temperature_allowed(target):
                        return CommandResult(intent.id,False,error='native_temperature_limits_required')
                    if 'set_temperature' not in report.supported:
                        return CommandResult(intent.id,False,error='unsupported_setpoint')
                    await self.device.async_set_water_heater_temperature(target)
                if action!='set_temperature': await self.device.async_set_power(action == 'start')
                self.last_command = now
                self.log('INFO','Commande native acceptée : '+action)
                # Library mutates its local data optimistically; only the next read is observation.
                return CommandResult(intent.id,True,False,checked_at=now)
            except Exception as error:
                self.log('ERROR',f'Commande native impossible ({type(error).__name__})')
                return CommandResult(intent.id,False,error='native_command_failed',checked_at=now)

    def temperature_allowed(self,target):
        minimum=getattr(self.device,'water_heater_minimum_temperature',None)
        maximum=getattr(self.device,'water_heater_maximum_temperature',None)
        try:
            return bool(target is not None and minimum is not None and maximum is not None
                        and math.isfinite(target) and minimum<=target<=maximum)
        except (TypeError,ValueError): return False

    async def close(self): pass
