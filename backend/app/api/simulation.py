from dataclasses import asdict
from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field
from app.api.auth import require_auth
from app.simulation.clock import SimulatedClock
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.domain.devices import DeviceSpec,DeviceState
from app.domain.site import SiteSnapshot
from app.domain.measurements import Sample

router=APIRouter(prefix='/api/v1/simulation',dependencies=[Depends(require_auth)])


class Scenario(BaseModel):
    surplus_w:float=Field(3000,ge=0,le=30000)
    car_priority:int=Field(1,ge=1,le=100)
    tank_priority:int=Field(2,ge=1,le=100)


@router.post('')
def simulate(body:Scenario):
    # Pure calculation: no store, no coordinator and no connector references.
    clock=SimulatedClock()
    sample=lambda value:Sample(value,'W','simulation',clock.now(),clock.now())
    specs=[DeviceSpec('demo-car','charger',min_power_w=1380,max_power_w=3700,priority=body.car_priority),
           DeviceSpec('demo-tank','water_heater',min_power_w=600,max_power_w=600,priority=body.tank_priority)]
    snapshot=SiteSnapshot(clock.now(),sample(-body.surplus_w),device_states={
        s.id:DeviceState(s.id,sample(0),connected=True) for s in specs},site_limit_w=9000,export_margin_w=100)
    batch=EnergyEngine(clock).evaluate(snapshot,specs,
        {s.id:DevicePolicy(s.id,armed=True,start_delay_s=0) for s in specs},{})
    return {'simulation':True,'commands':[asdict(c) for c in batch.commands],'reasons':batch.reasons}
