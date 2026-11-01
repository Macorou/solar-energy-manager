import time
from dataclasses import replace
from datetime import timedelta
import pytest
from app.connectors.ocpp.registry import OcppRegistry
from app.connectors.ocpp.station import Station
from app.domain.devices import DeviceState
from app.domain.measurements import utcnow
from app.domain.site import SiteSnapshot
from app.settings import DeviceConfig,SettingsDocument
from app.storage.database import SQLiteStore
from tests.runtime.test_resume_modes import service


def observe(app,state):
    coordinator=app.state.coordinator
    snapshot=SiteSnapshot(utcnow(),device_states={'device':state})
    config=SettingsDocument.model_validate(app.state.store.load_settings())
    return coordinator.end_manual_on_unplug(snapshot,config),config


LINK=utcnow()-timedelta(seconds=60)


def fresh(connected,vehicle,since=LINK):
    """A reading received after the link came up, as a StatusNotification would give."""
    return DeviceState('device',None,'unknown',connected,vehicle_connected=vehicle,
        connected_since=since,status_received_at=since+timedelta(seconds=5))


def step(app,connected,vehicle): return observe(app,fresh(connected,vehicle))


@pytest.mark.parametrize('sequence,mode',[
    ([(True,True),(True,False)],'planned'),
    ([(True,True),(True,None),(True,False)],'planned'),
    ([(True,True),(False,None),(True,False)],'manual'),
    ([(True,False)],'manual'),                       # first observation after a restart
    ([(True,False),(True,True)],'manual'),           # plugging in never changes the mode
])
def test_manual_returns_to_auto_only_on_an_observed_unplug(tmp_path,sequence,mode):
    app,_=service(tmp_path,'charger','manual')
    for connected,vehicle in sequence: step(app,connected,vehicle)
    assert app.state.store.load_settings()['devices'][0]['mode']==mode


@pytest.mark.parametrize('mode',['planned','off'])
def test_unplug_leaves_other_modes_alone(tmp_path,mode):
    app,_=service(tmp_path,'charger',mode)
    step(app,True,True)
    changed,config=step(app,True,False)
    assert changed is False
    assert config.devices[0].mode==mode
    assert app.state.store.load_settings()['devices'][0]['mode']==mode


def test_unplug_writes_the_journal_line_and_clears_manual_controls(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    app.state.store.set('manual_controls',{'device':{'until':None,'previous_mode':'planned'}})
    step(app,True,True)
    changed,config=step(app,True,False)
    assert changed is True
    assert config.devices[0].mode=='planned'
    assert 'device' not in app.state.store.get('manual_controls',{})
    entries=app.state.store.journal.query(search='fin du mode Manuel')['entries']
    assert [(e['level'],e['message']) for e in entries]==[('INFO','Voiture débranchée : fin du mode Manuel, retour en Auto (Planifié)')]
    assert entries[0]['area']=='device:device'


def test_a_reading_older_than_the_link_or_without_a_link_time_never_counts(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    step(app,True,True)
    since=utcnow()
    for state in (replace(fresh(True,False),status_received_at=None),
                  replace(fresh(True,False),connected_since=None),
                  replace(fresh(True,False,since),status_received_at=since-timedelta(seconds=1)),
                  replace(fresh(True,False),rebooted=True)):
        assert observe(app,state)[0] is False
    assert app.state.store.load_settings()['devices'][0]['mode']=='manual'


def test_a_new_link_forgets_the_plugged_memory(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    first=utcnow()-timedelta(seconds=30)
    observe(app,fresh(True,True,first))
    # Same device, new link: an unplug reading is the first fresh one, not a transition.
    assert observe(app,fresh(True,False,first+timedelta(seconds=10)))[0] is False
    assert app.state.store.load_settings()['devices'][0]['mode']=='manual'


class Link:
    """The real registry and station state path, with a controllable link."""
    def __init__(self,tmp_path):
        cfg=DeviceConfig(id='device',name='Appareil',kind='charger',charge_point_id='box')
        self.reg=OcppRegistry(SQLiteStore(tmp_path/'ocpp'),lambda:[cfg],lambda _:None)
        self.station=None
    def up(self):
        time.sleep(0.01)
        self.station=Station('box',None,self.reg);self.reg.connect('box',self.station)
        time.sleep(0.01)
    def down(self): self.reg.stations.pop('box',None)
    def state(self): return self.reg.state('device')


def test_stale_plugged_value_after_reconnect_and_reboot_keeps_manual(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    link=Link(tmp_path);link.up()
    link.station.status(1,'NoError','Preparing')
    observe(app,link.state())
    link.down();link.up()
    stale=link.state()
    assert stale.connected and stale.vehicle_connected is True      # other consumers keep seeing it
    assert observe(app,stale)[0] is False
    link.station.boot('Wallbox','Pulsar Plus')
    assert link.state().rebooted is True
    assert observe(app,link.state())[0] is False
    time.sleep(0.01)
    link.station.status(1,'NoError','Available')                    # the charger restarting
    assert observe(app,link.state())[0] is False
    assert app.state.store.load_settings()['devices'][0]['mode']=='manual'


def test_boot_on_the_same_link_does_not_turn_the_following_available_into_an_unplug(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    link=Link(tmp_path);link.up()
    link.station.status(1,'NoError','Charging')
    observe(app,link.state())
    time.sleep(0.01)
    link.station.boot('Wallbox','Pulsar Plus')
    time.sleep(0.01)
    link.station.status(1,'NoError','Available')
    assert observe(app,link.state())[0] is False
    assert app.state.store.load_settings()['devices'][0]['mode']=='manual'


def test_plug_offline_replug_unplug_returns_to_auto(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    link=Link(tmp_path);link.up()
    link.station.status(1,'NoError','Preparing')
    observe(app,link.state())
    link.down()
    assert observe(app,link.state())[0] is False
    link.up()
    link.station.status(1,'NoError','Preparing')
    assert observe(app,link.state())[0] is False
    time.sleep(0.01)
    link.station.status(1,'NoError','Available')
    changed,config=observe(app,link.state())
    assert changed is True and config.devices[0].mode=='planned'
    assert app.state.store.load_settings()['devices'][0]['mode']=='planned'


async def test_tick_applies_the_unplug_revert_before_the_policies_are_built(tmp_path):
    app,_=service(tmp_path,'charger','manual')
    coordinator=app.state.coordinator
    seen=[]
    evaluate=coordinator.engine.evaluate
    def spy(snapshot,specs,policies,authorizations):
        seen.append(policies['device'].mode);return evaluate(snapshot,specs,policies,authorizations)
    coordinator.engine.evaluate=spy
    since=utcnow()-timedelta(seconds=30)
    await coordinator.tick(SiteSnapshot(utcnow(),device_states={'device':fresh(True,True,since)}))
    assert seen==['manual'] and app.state.store.load_settings()['devices'][0]['mode']=='manual'
    await coordinator.tick(SiteSnapshot(utcnow(),device_states={'device':fresh(True,False,since)}))
    assert seen==['manual','planned']
    assert app.state.store.load_settings()['devices'][0]['mode']=='planned'
