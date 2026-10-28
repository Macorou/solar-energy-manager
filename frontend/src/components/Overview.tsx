import type {LiveDevice,LiveState,Settings} from '../api/types'
import {DeviceCard,UnconfiguredDeviceCard} from './DeviceCard'
import {Icon} from './Icon'
import {ScheduleTimeline} from './ScheduleTimeline'
import {housePower,sumDevicePower} from './dashboard'

export function Overview({settings,state,connections,onAction,onNavigate}:{settings:Settings;state:LiveState|null;
  connections:Record<string,boolean>;onAction:(id:string,action:string)=>void;onNavigate:(page:string)=>void}) {
  const grid=state?.grid?.usable&&Number.isFinite(state.grid.value)?state.grid.value:null
  const stats=[{icon:'grid',label:'Réseau',value:grid,scale:settings.site_limit_w||12000,detail:grid==null?'En attente de mesure':grid<0?'Injection vers le réseau':'Énergie prélevée sur le réseau'},
    {icon:'car',label:'Voiture',value:sumDevicePower(state,'charger'),scale:settings.devices.filter(d=>d.kind==='charger').reduce((sum,d)=>sum+d.max_power_w,0)||7400,detail:'Puissance de recharge mesurée'},
    {icon:'drop',label:'Eau chaude',value:sumDevicePower(state,'water_heater'),scale:settings.devices.filter(d=>d.kind==='water_heater').reduce((sum,d)=>sum+d.max_power_w,0)||3000,detail:'Puissance de chauffe mesurée'},
    {icon:'home',label:'Maison',value:housePower(state),scale:settings.site_limit_w||12000,detail:state?.house_configured?
      'Consommation totale, voiture et ballon inclus : capteur Home Assistant configuré.':
      'Consommation totale, voiture et ballon inclus : réseau signé + production solaire. Lectures cohérentes requises.'}]
  const live=(config:Settings['devices'][number]):LiveDevice=>state?.devices.find(device=>device.config.id===config.id)??{
    config,state:{observed_power:null,observed_state:'unknown',connected:false,temperature:null,target_temperature:null,fault:null},
    reason:'En attente de mesures',reservation_w:0,command:null,authorization:null}
  return <>
    <div className="stat-grid">{stats.map(stat=><section className={'stat-card '+stat.icon} key={stat.icon} aria-label={stat.label} title={stat.detail}>
      <span className="stat-icon"><Icon name={stat.icon} size={43}/></span><div className="stat-metric"><span>{stat.label}</span><strong>{stat.value==null?'—':(stat.value/1000).toLocaleString('fr-FR',{minimumFractionDigits:1,maximumFractionDigits:1})+' kW'}</strong>
        <div className="stat-meter" aria-hidden="true"><i style={{width:stat.value==null?'0%':Math.min(100,Math.abs(stat.value)/stat.scale*100)+'%'}}/></div></div>
    </section>)}</div>
    <div className="device-grid">{(['charger','water_heater'] as const).flatMap(kind=>{
      const devices=settings.devices.filter(device=>device.kind===kind)
      return devices.length?devices.map(config=><DeviceCard key={config.id} device={live(config)} telemetry={state?.vehicles[config.vehicle_id]} timezone={settings.timezone} onAction={onAction}/>):
        [<UnconfiguredDeviceCard key={kind} kind={kind} onConfigure={()=>onNavigate(kind==='charger'?'chargers':'water')}/>]
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
