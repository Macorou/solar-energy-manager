import asyncio
from datetime import datetime, timezone
import logging
from ariston import Ariston
from app.domain.devices import DeviceState, CapabilityReport
from app.domain.commands import CommandResult

logging.getLogger('ariston').setLevel(logging.CRITICAL)


class AristonAdapter:
    def __init__(self, config, username='', password='', device=None):
        self.config, self.username, self.password = config, username, password
        self.device, self.library = device, None
        self.initialized = False
        self.report = None
        self.state = DeviceState(config.id)
        self.lock = asyncio.Lock()
        self.last_command = None

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
            except Exception:
                self.state = DeviceState(self.config.id,fault='provider_unavailable')
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
            action = 'suspend' if intent.action == 'suspend' else 'start'
            if action not in report.supported:
                return CommandResult(intent.id,False,error='unsupported_native_control')
            now = datetime.now(timezone.utc)
            if intent.expires_at and intent.expires_at <= now:
                return CommandResult(intent.id,False,error='expired_command')
            try:
                if action == 'start':
                    if self.last_command and (now-self.last_command).total_seconds()<60:
                        return CommandResult(intent.id,False,error='native_cooldown')
                    target = self.config.target
                    minimum = getattr(self.device,'water_heater_minimum_temperature',None)
                    maximum = getattr(self.device,'water_heater_maximum_temperature',None)
                    if (target is None or minimum is None or maximum is None
                        or not minimum <= target <= maximum):
                        return CommandResult(intent.id,False,error='native_temperature_limits_required')
                    if 'set_temperature' not in report.supported:
                        return CommandResult(intent.id,False,error='unsupported_setpoint')
                    await self.device.async_set_water_heater_temperature(target)
                await self.device.async_set_power(action == 'start')
                self.last_command = now
                # Library mutates its local data optimistically; only the next read is observation.
                return CommandResult(intent.id,True,False,checked_at=now)
            except Exception:
                return CommandResult(intent.id,False,error='native_command_failed',checked_at=now)

    async def close(self): pass
