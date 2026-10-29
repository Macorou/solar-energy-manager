from datetime import datetime, timezone
from app.domain.measurements import Sample
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.site import SiteSnapshot


def fixture_state(clock, powers, grid):
    sample = lambda x: Sample(x,'W','test',clock.now(),clock.now())
    return SiteSnapshot(clock.now(), sample(grid),
        device_states={k:DeviceState(k,sample(v),'charging' if v else 'idle',True) for k,v in powers.items()},
        site_limit_w=9000,export_margin_w=0)


def test_smaller_second_device_can_start_and_both_can_run_when_covered():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    clock = SimulatedClock()
    specs = [DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700,priority=1),
             DeviceSpec('tank','water_heater',min_power_w=600,max_power_w=600,priority=2)]
    policies = {s.id:DevicePolicy(s.id,armed=True,start_delay_s=0) for s in specs}
    engine = EnergyEngine(clock)
    first = engine.evaluate(fixture_state(clock,{'ev':0,'tank':0},-900),specs,policies,{})
    assert [(c.device_id,c.limit_w) for c in first.commands] == [('tank',600)]
    assert first.reservations[0].power_w == 600
    both = EnergyEngine(clock).evaluate(fixture_state(clock,{'ev':0,'tank':0},-5000),specs,policies,{})
    assert {c.device_id:c.limit_w for c in both.commands} == {'ev':1380,'tank':600}


def test_pending_start_keeps_reservation_instead_of_reusing_power():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    clock = SimulatedClock()
    specs = [DeviceSpec('a','water_heater',min_power_w=600,max_power_w=600),
             DeviceSpec('b','water_heater',min_power_w=600,max_power_w=600,priority=2)]
    policies = {s.id:DevicePolicy(s.id,armed=True,start_delay_s=0) for s in specs}
    engine = EnergyEngine(clock)
    first = engine.evaluate(fixture_state(clock,{'a':0,'b':0},-900),specs,policies,{})
    second = engine.evaluate(fixture_state(clock,{'a':0,'b':0},-900),specs,policies,{})
    assert first.commands[0].device_id == 'a'
    assert not any(c.device_id=='b' and c.limit_w for c in second.commands)


def test_missing_grid_stops_solar_and_unarmed_device_never_gets_command():
    from app.engine.engine import EnergyEngine
    from app.engine.policies import DevicePolicy
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock()
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    engine=EnergyEngine(clock)
    assert not engine.evaluate(fixture_state(clock,{'ev':0},-4000),[spec],{'ev':DevicePolicy('ev')},{}).commands
    state=fixture_state(clock,{'ev':2000},0)
    from dataclasses import replace
    result=engine.evaluate(replace(state,grid=None),[spec],{'ev':DevicePolicy('ev',armed=True)}, {})
    assert result.commands[0].action=='suspend'
