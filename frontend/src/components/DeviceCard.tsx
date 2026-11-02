import type {LiveDevice,Telemetry} from '../api/types'
import {watts} from '../api/client'
import {Icon} from './Icon'
import {DeviceIllustration} from './DeviceIllustration'
import {ChargeSession,vehicleStatus} from './ChargeSession'
import {reportedPower,useLastPowerReadings} from './powerDisplay'

export function DeviceCard({device,telemetry,onAction,timezone='Europe/Paris'}:{device:LiveDevice;telemetry?:Telemetry;
  onAction:(id:string,action:string)=>void;timezone?:string}) {
  const {config,state,command}=device
  const car=config.kind==='charger'
  const session=device.charging
  const useEstimate=car&&session?.soc!=null&&(session.active||!!session.ended_at&&
    (!telemetry?.measured_at||new Date(telemetry.measured_at)<=new Date(session.ended_at)))
  const fresh=car?(useEstimate?session?.soc_usable:telemetry?.fresh):state.connected
  const raw=car?(useEstimate?session?.soc:telemetry?.soc):state.temperature
  const known=raw!=null&&Number.isFinite(raw)&&(!car||(raw>=0&&raw<=100))
  const value=known&&(car||fresh)?raw:null
  const measured=telemetry?.measured_at?new Date(telemetry.measured_at):null
  const batteryDate=measured&&Number.isFinite(measured.getTime())?
    measured.toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'short',timeZone:timezone}):null
  const scope=JSON.stringify([config.id,config.kind,config.charge_point_id,config.connector_id,config.gateway_id])
  const displayed=useLastPowerReadings(scope,{power:reportedPower(state.observed_power)},{power:state.observed_power})
  const power=displayed.values.power
  const currentPower=state.observed_power?.usable?reportedPower(state.observed_power):null
  const observedRunning=state.connected&&currentPower!=null&&currentPower>20&&['Charging','on'].includes(state.observed_state)
  const pending=command&&['sending','accepted'].includes(command.status)
  const badge=state.fault||command?.status==='unknown'?['red','À vérifier','info']:
    observedRunning?['blue',car?'En charge':'En chauffe','bolt']:
    pending?['amber','En attente de confirmation','clock']:
    !config.armed?['neutral','Observation','eye']:
    !state.connected?['neutral','Hors connexion','link']:['amber','En attente','clock']
  const target=car?(config.mode==='manual'?config.default_soc_target:device.authorization?.target_soc??config.default_soc_target):(device.effective_target??config.target)
  const solarTarget=car&&config.mode!=='manual'&&config.solar_target!=null&&target!=null&&config.solar_target>target?config.solar_target:null
  const deadline=car&&config.mode!=='manual'&&device.authorization?.expires_at?new Date(device.authorization.expires_at)
    .toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:timezone}):null
  const automatic=config.mode!=='off'&&config.mode!=='manual'
  return <article className={'device-card '+(car?'ev':'tank')} aria-label={config.name}>
    <div className="card-heading"><h2>{car?'Voiture électrique':'Ballon d’eau chaude'}</h2>
      <span className={'badge '+badge[0]}><Icon name={badge[2]} size={16}/>{badge[1]}</span></div>
    <p className="device-name">{config.name}</p>
    {car&&<p className="vehicle-connection">Voiture : {vehicleStatus(device)}</p>}
    <div className="device-card-body">
      <div className="device-art"><DeviceIllustration kind={config.kind}/></div>
      <div className="device-controls">
        <div className="device-level">
        <div className="big-number">{value==null?'—':Math.round(value)}<small>{car?'%':'°C'}</small></div>
        <div className="meter"><i style={{width:Math.max(0,Math.min(100,value??0))+'%'}}/></div>
        <p className="device-target">Objectif {target??'—'} {car?'%':'°C'}{deadline&&<> à {deadline}</>}{solarTarget!=null&&<> · surplus jusqu’à {solarTarget} %</>}{!car&&device.target_source&&<> · {device.target_source==='solar'?'solaire':'réseau'}</>}</p>
        {useEstimate&&session?.soc_estimated&&<span className="freshness">{session.soc_usable?'Batterie estimée':session.soc_reason||'Estimation à vérifier'}</span>}
        {!fresh&&<span className="freshness old">{car?(value!=null?'Donnée ancienne':'Batterie indisponible'):'Mesure indisponible ou ancienne'}</span>}
        {car&&device.plan_warning&&<span className="freshness old" role="status">{device.plan_warning}</span>}
        </div>
        <div className="mode-switch" aria-label="Mode de pilotage">
          <button className={automatic?'selected automatic':''} aria-pressed={automatic} disabled={!config.armed} onClick={()=>onAction(config.id,'resume')}><Icon name="leaf" size={14}/>Automatique</button>
          <button className={config.mode==='manual'?'selected':''} aria-pressed={config.mode==='manual'} disabled={!config.armed} onClick={()=>onAction(config.id,'manual')} title={car?'Manuel jusqu’au débranchement de la voiture':'Démarrage temporaire pendant 30 minutes'}><Icon name="hand" size={14}/>Manuel</button>
          <button className={config.mode==='off'?'selected':''} aria-pressed={config.mode==='off'} disabled={!config.armed} onClick={()=>onAction(config.id,'pause')}><Icon name="pause" size={14}/>Pause</button>
        </div>
        <div className="device-reading"><Icon name={car?'bolt':'calendar'} size={26}/><div>
          <strong>{watts(power)}</strong><span>{displayed.estimated.power?'Puissance estimée · état OCPP':car?'Puissance de charge actuelle':'Puissance de chauffe actuelle'}</span>
        </div></div>
        <button className={'start-now '+(car?'charge':'heat')} disabled={!config.armed} title={car?'Recharge manuelle jusqu’au débranchement de la voiture':'Commande manuelle temporaire de 30 minutes'} onClick={()=>onAction(config.id,'manual')}><Icon name="play" size={16}/>{car?'Charger maintenant':'Chauffer maintenant'}</button>
      </div>
    </div>
    {car&&session&&<ChargeSession value={session}/>}
    <div className="device-feedback"><span className="reason"><span className="status-dot"/>{device.reason}</span><span className="device-priority">Priorité {config.priority}</span></div>
    {car&&value!=null&&<span className="measure-date">{batteryDate?<>Batterie relevée le <time dateTime={telemetry!.measured_at!}>{batteryDate}</time></>:'Date de mesure indisponible'}</span>}
  </article>
}

export function UnconfiguredDeviceCard({kind,onConfigure}:{kind:'charger'|'water_heater';onConfigure:()=>void}) {
  const car=kind==='charger'
  return <article className={'device-card unconfigured '+(car?'ev':'tank')}>
    <div className="card-heading"><h2>{car?'Voiture électrique':'Ballon d’eau chaude'}</h2><span className="badge neutral">À configurer</span></div>
    <p className="device-name">{car?'Votre borne et votre véhicule':'Votre eau chaude sanitaire'}</p>
    <div className="device-card-body"><div className="device-art"><DeviceIllustration kind={kind}/></div><div className="device-controls">
      <div className="device-level">
      <div className="big-number">—<small>{car?'%':'°C'}</small></div><div className="meter"/>
      <p className="device-target">{car?'Connectez votre voiture et sa borne.':'Connectez votre ballon d’eau chaude.'}</p>
      <p className="hint setup-copy">Les mesures et les commandes apparaîtront après la configuration.</p>
      </div>
      <button className={'start-now '+(car?'charge':'heat')} onClick={onConfigure}><Icon name="plus" size={17}/>Configurer {car?'la voiture':'le ballon'}</button>
    </div></div>
    <div className="device-feedback"><span className="reason"><span className="status-dot"/>Pilotage désactivé pendant la configuration</span></div>
  </article>
}
