from app.domain.devices import DeviceSpec
from test_solar_allocation import fixture_state


def test_short_cloud_is_tolerated_but_persistent_deficit_stops():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock()
    engine=EnergyEngine(clock)
    specs=[DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)]
    policies={'ev':DevicePolicy('ev',armed=True,start_delay_s=0,stop_delay_s=30,import_tolerance_w=100)}
    first=engine.evaluate(fixture_state(clock,{'ev':2000},1800),specs,policies,{})
    assert not any(c.action=='suspend' for c in first.commands)
    clock.advance(20)
    assert not any(c.action=='suspend' for c in engine.evaluate(fixture_state(clock,{'ev':1380},1180),specs,policies,{}).commands)
    clock.advance(11)
    assert engine.evaluate(fixture_state(clock,{'ev':1380},1180),specs,policies,{}).commands[0].action=='suspend'


def test_return_of_sun_resets_stop_delay_and_start_delay_requires_continuity():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock()
    engine=EnergyEngine(clock)
    spec=DeviceSpec('tank','water_heater',min_power_w=600,max_power_w=600)
    policy=DevicePolicy('tank',armed=True,start_delay_s=10,stop_delay_s=30)
    assert not engine.evaluate(fixture_state(clock,{'tank':0},-700),[spec],{'tank':policy},{}).commands
    clock.advance(8)
    engine.evaluate(fixture_state(clock,{'tank':0},-100),[spec],{'tank':policy},{})
    clock.advance(3)
    assert not engine.evaluate(fixture_state(clock,{'tank':0},-700),[spec],{'tank':policy},{}).commands
    clock.advance(11)
    assert engine.evaluate(fixture_state(clock,{'tank':0},-700),[spec],{'tank':policy},{}).commands[0].limit_w==600


def test_import_tolerances_are_not_added_across_running_devices():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock()
    specs=[DeviceSpec('a','charger',min_power_w=600,max_power_w=600),DeviceSpec('b','charger',min_power_w=600,max_power_w=600,priority=2)]
    policies={s.id:DevicePolicy(s.id,armed=True,start_delay_s=0,stop_delay_s=0,import_tolerance_w=200) for s in specs}
    result=EnergyEngine(clock).evaluate(fixture_state(clock,{'a':600,'b':600},300),specs,policies,{})
    assert any(c.action=='suspend' for c in result.commands)


def test_running_tank_is_not_preempted_and_hard_limit_overrides_delays():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    from dataclasses import replace
    clock=SimulatedClock()
    specs=[DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700,priority=1),DeviceSpec('tank','water_heater',min_power_w=600,max_power_w=600,priority=2)]
    policies={s.id:DevicePolicy(s.id,armed=True,start_delay_s=0,stop_delay_s=300,min_run_s=600) for s in specs}
    engine=EnergyEngine(clock)
    result=engine.evaluate(fixture_state(clock,{'ev':0,'tank':600},-1000),specs,policies,{})
    assert not any(c.device_id=='tank' and c.action=='suspend' for c in result.commands)
    assert not any(c.device_id=='ev' and c.limit_w for c in result.commands)
    limited=replace(fixture_state(clock,{'tank':600,'ev':0},1000),site_limit_w=300)
    assert any(c.device_id=='tank' and c.action=='suspend' for c in engine.evaluate(limited,specs,policies,{}).commands)
