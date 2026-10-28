from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.connectors.ocpp.registry import ChargerAdapter, OcppRegistry
from app.domain.commands import CommandIntent
from app.domain.measurements import utcnow
from app.settings import DeviceConfig
from app.storage.database import SQLiteStore


class MeterWire:
    def __init__(self, *, readonly=False, reject=None, maximum='10', verify=True):
        self.values={'MeterValuesSampledData':'Energy.Active.Import.Register,Voltage',
                     'MeterValueSampleInterval':'60','MeterValuesSampledDataMaxLength':maximum}
        self.readonly=readonly; self.reject=reject; self.verify=verify; self.calls=[]

    async def call(self, message):
        name=message.__class__.__name__; self.calls.append(message)
        if name=='GetConfiguration':
            return SimpleNamespace(configuration_key=[{'key':key,'value':value,
                'readonly':self.readonly} for key,value in self.values.items() if key in message.key],unknown_key=[])
        if name=='ChangeConfiguration':
            status=self.reject or 'Accepted'
            if status=='Accepted' and self.verify:self.values[message.key]=message.value
            return SimpleNamespace(status=status)
        return SimpleNamespace(status='Accepted')


def adapter(tmp_path,wire):
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box',armed=True)
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    registry.stations['box']=wire
    result=ChargerAdapter(registry,config)
    result.metering_required=True
    return result


def start():return CommandIntent('start','ev','set_power',3910,utcnow()+timedelta(seconds=90))


async def test_phase_control_prepares_and_verifies_metering_before_remote_start(tmp_path):
    wire=MeterWire(); result=await adapter(tmp_path,wire).execute(start())
    assert result.accepted
    assert set(wire.values['MeterValuesSampledData'].split(','))=={
        'Energy.Active.Import.Register','Voltage','Power.Active.Import','Current.Import'}
    assert wire.values['MeterValueSampleInterval']=='10'
    names=[m.__class__.__name__ for m in wire.calls]
    assert names.index('ChangeConfiguration')<names.index('SetChargingProfile')<names.index('RemoteStartTransaction')
    assert names.count('GetConfiguration')==2
    assert {m.key for m in wire.calls if m.__class__.__name__=='ChangeConfiguration'}=={
        'MeterValuesSampledData','MeterValueSampleInterval'}


@pytest.mark.parametrize('options',[
    {'readonly':True},{'reject':'Rejected'},{'reject':'RebootRequired'},
    {'maximum':'2'},{'verify':False}])
async def test_unverified_metering_never_reaches_a_profile_or_start(tmp_path,options):
    wire=MeterWire(**options); result=await adapter(tmp_path,wire).execute(start())
    assert not result.accepted and result.error
    assert not any(m.__class__.__name__ in ('SetChargingProfile','RemoteStartTransaction','Reset','ChangeAvailability') for m in wire.calls)
    if options.get('maximum')=='2' or options.get('readonly'):
        assert not any(m.__class__.__name__=='ChangeConfiguration' for m in wire.calls)


async def test_already_suitable_readonly_metering_needs_no_write(tmp_path):
    wire=MeterWire(readonly=True)
    wire.values.update(MeterValuesSampledData='Voltage,Current.Import,Energy.Active.Import.Register,Power.Active.Import',MeterValueSampleInterval='5')
    result=await adapter(tmp_path,wire).execute(start())
    assert result.accepted
    assert not any(m.__class__.__name__=='ChangeConfiguration' for m in wire.calls)


async def test_no_metering_preparation_when_phase_control_is_disabled(tmp_path):
    wire=MeterWire(); source=adapter(tmp_path,wire);source.metering_required=False
    assert (await source.execute(start())).accepted
    assert [m.__class__.__name__ for m in wire.calls]==['SetChargingProfile','RemoteStartTransaction']


async def test_existing_transaction_renewal_never_reconfigures_telemetry(tmp_path):
    wire=MeterWire(); source=adapter(tmp_path,wire)
    source.registry.active[('box',1)]={'transaction_id':4}
    assert (await source.execute(start())).accepted
    assert [m.__class__.__name__ for m in wire.calls]==['SetChargingProfile']


async def test_runtime_enables_meter_preparation_for_its_phase_limited_adapter(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings,SettingsDocument
    app=create_app(RuntimeSettings(data_dir=tmp_path))
    config=SettingsDocument(phase_control_enabled=True,devices=[DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box')])
    wire=MeterWire();app.state.ocpp.stations['box']=wire
    await app.state.coordinator.acquire(config)
    source=app.state.coordinator.adapters['ev']
    assert (await source.execute(start())).accepted
    assert 'Current.Import' in wire.values['MeterValuesSampledData'].split(',')


async def test_status_refresh_only_requests_a_status_notification(tmp_path):
    wire=MeterWire();source=adapter(tmp_path,wire)
    assert await source.request_status()
    assert len(wire.calls)==1
    message=wire.calls[0]
    assert message.__class__.__name__=='TriggerMessage'
    assert message.requested_message=='StatusNotification' and message.connector_id==1
