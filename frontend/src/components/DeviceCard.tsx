import type {LiveDevice,Telemetry} from '../api/types'
import {watts,date} from '../api/client'
import {Icon} from './Icon'
export function DeviceCard({device,telemetry,onAction}:{device:LiveDevice;telemetry?:Telemetry;
  onAction:(id:string,action:string)=>void}) {
  const {config,state,command}=device
  const car=config.kind==='charger'
  const value=car?telemetry?.soc:state.temperature
  const fresh=car?telemetry?.fresh:state.connected
  return <article className={'device-card '+(car?'ev':'tank')}>
    <div className="card-heading"><div><span className="eyebrow">{car?'MOBILITÉ ÉLECTRIQUE':'EAU CHAUDE SANITAIRE'}</span><h2>{config.name}</h2></div>
      <span className={'badge '+(config.armed?'green':'neutral')}>{config.armed?'Pilotage activé':'Observation'}</span></div>
    <div className="device-visual"><div className="device-icon"><Icon name={car?'car':'drop'} size={92}/><span>{car?'OCPP 1.6J':'Commande native'}</span></div>
      <div className="device-metric"><div className="big-number">{value==null?'—':Math.round(value)}<small>{car?'%':'°C'}</small></div>
        <div className="meter"><i style={{width:Math.min(100,value||0)+'%'}}/></div>
        <p>Objectif {car?(device.authorization?.target_soc||config.default_soc_target)+' %':(config.target??'—')+' °C'}</p>
        <span className={'freshness '+(fresh?'':'old')}>{fresh?'Mesure disponible':'Mesure indisponible ou ancienne'}</span>
        {car&&<span className="hint">{date(telemetry?.measured_at)}</span>}</div></div>
    <div className="device-readings"><div><Icon name="bolt"/><div><strong>{watts(state.observed_power?.value)}</strong><span>Puissance mesurée</span></div></div>
      <div><strong>{config.priority}</strong><span>Priorité de démarrage</span></div></div>
    <div className="reason"><span className="status-dot"/>{device.reason}</div>
    {command&&<div className="command-status">Demande {watts(command.power_w)} · {({sending:'envoi en cours',accepted:'acceptée, en attente de mesure',observed:'effet observé',unknown:'résultat inconnu'} as Record<string,string>)[command.status]||command.status}</div>}
    <div className="actions equal"><button disabled={!config.armed} onClick={()=>onAction(config.id,'resume')}>Automatique</button>
      <button disabled={!config.armed} onClick={()=>onAction(config.id,'manual')}>Manuel · 30 min</button>
      <button disabled={!config.armed} onClick={()=>onAction(config.id,'pause')}>Pause</button></div>
  </article>
}
