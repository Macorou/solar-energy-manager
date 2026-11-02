import pytest
from app.connectors.ariston.client import AristonAdapter
from app.settings import DeviceConfig
from app.domain.commands import CommandIntent


class NativeDevice:
    water_heater_current_temperature = 43
    water_heater_target_temperature = 55
    water_heater_minimum_temperature = 40
    water_heater_maximum_temperature = 65
    water_heater_power_value = False
    water_heater_mode_operation_texts = ['GREEN','COMFORT']
    def __init__(self): self.calls=[]
    async def async_update_state(self): pass
    async def async_update_settings(self): raise RuntimeError('optional diagnostic failure')
    async def async_set_power(self, on): self.calls.append(('power',on))
    async def async_set_water_heater_temperature(self, target): self.calls.append(('target',target))


def config(): return DeviceConfig(id='dhw',name='NUOS',kind='water_heater',target=55,max_power_w=700)


@pytest.mark.asyncio
async def test_native_control_acceptance_does_not_invent_observation():
    device = NativeDevice()
    adapter = AristonAdapter(config(),device=device)
    report = await adapter.probe_capabilities()
    assert 'suspend' in report.supported
    state = await adapter.read_state()
    assert state.temperature == 43 and state.observed_power is None
    result = await adapter.execute(CommandIntent('start','dhw','set_power',700))
    assert result.accepted and not result.observed
    assert device.calls == [('target',55),('power',True)]
    assert (await adapter.read_state()).observed_state == 'off'


@pytest.mark.asyncio
async def test_bad_setpoint_and_unsupported_native_control_are_refused():
    device = NativeDevice()
    adapter = AristonAdapter(config().model_copy(update={'target':80}),device=device)
    assert not (await adapter.execute(CommandIntent('x','dhw','set_power',700))).accepted
    assert device.calls == []
    device.async_set_power = None
    assert 'suspend' not in (await adapter.probe_capabilities()).supported
    assert not (await adapter.execute(CommandIntent('s','dhw','suspend',0))).accepted


@pytest.mark.asyncio
async def test_main_read_failure_keeps_temperature_unknown_and_device_offline():
    device = NativeDevice()
    async def fail(): raise RuntimeError('secret-provider-response')
    device.async_update_state = fail
    state = await AristonAdapter(config(),device=device).read_state()
    assert not state.connected and state.temperature is None
    assert state.fault == 'provider_unavailable'
