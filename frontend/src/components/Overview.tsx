import type {LiveDevice,LiveState,Settings} from '../api/types'
import {DeviceCard,UnconfiguredDeviceCard} from './DeviceCard'
import {Icon} from './Icon'
import {ScheduleTimeline} from './ScheduleTimeline'
import {EnergyFlow} from './EnergyFlow'


export function Overview({settings,state,connections,onAction,onNavigate}:{settings:Settings;state:LiveState|null;
  connections:Record<string,boolean>;onAction:(id:string,action:string)=>void;onNavigate:(page:string)=>void}) {
  const live=(config:Settings['devices'][number]):LiveDevice=>state?.devices.find(device=>device.config.id===config.id)??{
    config,state:{observed_power:null,observed_state:'unknown',connected:false,temperature:null,target_temperature:null,fault:null},
    reason:'En attente de mesures',reservation_w:0,command:null,authorization:null}
  return <>
    <EnergyFlow settings={settings} state={state}/>
    <div className="device-grid">{(['charger','water_heater'] as const).flatMap(kind=>{
      const devices=settings.devices.filter(device=>device.kind===kind)
      return devices.length?devices.map(config=><DeviceCard key={config.id} device={live(config)} telemetry={state?.vehicles[config.vehicle_id]} timezone={settings.timezone} onAction={onAction}/>):
        [<UnconfiguredDeviceCard key={kind} kind={kind} onConfigure={()=>onNavigate('settings')}/>]
    })}</div>
    {state&&Object.keys(state.errors).length>0&&<section className="panel readings-errors"><h2>Points à vérifier</h2>{Object.entries(state.errors).map(([id,text])=><p key={id}>{settings.devices.find(device=>device.id===id)?.name||id} : {text}</p>)}</section>}
    <div className="overview-bottom"><ScheduleTimeline settings={settings} onOpen={()=>onNavigate('planning')}/>
      <section className="panel connection-card"><div className="section-title"><h2><Icon name="ha" size={28}/>Home Assistant</h2><span className="badge neutral"><Icon name="clock" size={14}/>{connections.home_assistant?'Accès enregistrés':'À connecter'}</span></div>
        <div className="ha-link" aria-hidden="true"><Icon name="home" size={53}/><span className="ha-dots"/><span className="ha-logo"><Icon name="ha" size={45}/></span></div>
        <strong>Production · consommation · mesures</strong><p>Remontée vers Home Assistant prévue ensuite.</p>
        <button className="text-button" onClick={()=>onNavigate('settings')}>Configurer la connexion <Icon name="arrow" size={15}/></button>
      </section></div>
  </>
}
