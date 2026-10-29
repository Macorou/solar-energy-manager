import type {LiveState,Settings} from '../api/types'
import {watts} from '../api/client'
import {Icon} from './Icon'
import {energyBalance,flowReading,type FlowPart} from './energyBalance'
import {housePower} from './dashboard'
export function EnergyFlow({settings,state}:{settings:Settings;state:LiveState|null}){
  const model=energyBalance(settings,state),total=model?.total||1
  function markers(parts:FlowPart[],source=false){return <div className={'energy-markers '+(source?'energy-sources':'energy-uses')}>
    {parts.filter(p=>p.power>0).map(p=><div className="energy-bracket" key={p.key} data-use={source?undefined:p.key} style={{flexGrow:p.power}}
      aria-label={p.label+' : '+watts(p.power)} title={p.label+' : '+watts(p.power)}><span className={p.power/total<.025?'energy-small-marker':''}><Icon name={p.icon} size={20}/></span></div>)}</div>}
  return <section className="panel energy-panel" aria-label="Flux d’énergie"><div className="section-title"><h2>Flux d’énergie</h2><span className="hint">Maison au total <strong>{watts(housePower(state))}</strong></span></div>
    {model&&model.total>0?<div className="energy-diagram" role="img" aria-label={model.segments.map(p=>p.label+' '+watts(p.power)).join(', ')+'. '+model.uses.map(p=>p.label+' '+watts(p.power)).join(', ')}>
      {markers(model.sources,true)}<div className="energy-track">{model.segments.map(p=><div key={p.key} className={'energy-segment energy-'+p.key} style={{flexGrow:p.power}} title={p.label+' : '+watts(p.power)}>
        {p.power/total>.12&&<span>{watts(p.power)}</span>}</div>)}</div>{markers(model.uses)}
    </div>:<p className="energy-unavailable">{model?'Aucun flux électrique mesuré.':'En attente de mesures réseau et solaire cohérentes.'}</p>}
    {model?.notice&&<p className="hint energy-notice">{model.notice}</p>}
    <div className="energy-legend">{[{key:'import',label:'Import réseau',value:flowReading(state?.grid)==null?null:Math.max(0,state!.grid!.value!)},
      {key:'solar',label:'Solaire utilisé',value:model?.segments[0].power??null},{key:'export',label:'Export réseau',value:flowReading(state?.grid)==null?null:Math.max(0,-state!.grid!.value!)}].map(p=><div key={p.key}><i className={'energy-dot energy-'+p.key}/><span>{p.label}</span><strong>{watts(p.value)}</strong></div>)}</div>
  </section>
}
