import {colorFor,equipmentColors,energy,money,number,percent,knownCost} from './model'
import type {Breakdown,Metric,SessionPage,Period} from './types'
import {SolarHistoryChart} from './SolarHistoryChart'

export function SessionBreakdown({data,metric,period,year,month,group}:{data:SessionPage;metric:Metric;period:Period;year:number;month:number;group:'solar'|'charger'|'vehicle'}){
  const entries=(group==='charger'?data.by_charger:data.by_vehicle).filter(e=>metric!=='cost'||(e.totals.known_cost_count??e.totals.priced_count)>0)
  const colors=equipmentColors(data,group)
  const value=(entry:Breakdown)=>metric==='energy'?entry.totals.energy_kwh:knownCost(entry.totals)||0
  const distribution=group==='solar'?[
    {id:'grid',name:'Réseau électrique',value:data.totals.grid_kwh,color:'#939ba8'},
    {id:'solar',name:'Solaire',value:data.totals.solar_kwh,color:'#42c995'},
    ...(data.totals.unknown_kwh>1e-8?[{id:'unknown',name:'Origine inconnue',value:data.totals.unknown_kwh,color:'#b59bc9'}]:[]),
  ]:entries.map(e=>({id:e.id,name:e.name,value:value(e),color:colors[e.id]||colorFor(e.id)}))
  const total=distribution.reduce((sum,e)=>sum+Math.abs(e.value),0),format=metric==='energy'?energy:money
  let offset=0
  return <div className="sessions-extras">
    <section className="panel sessions-breakdown"><h2>{metric==='cost'?'Prix moyen au kWh':group==='solar'&&period!=='month'?'Part solaire dans le temps':'Part solaire par '+(group==='charger'?'point de charge':'véhicule')}</h2>
      {group==='solar'&&period!=='month'&&metric==='energy'?<SolarHistoryChart data={data}/>:<div className="sessions-share-list">{entries.map(entry=><div key={entry.id}><span title={entry.name}>{entry.name}</span><div className="sessions-share-track"><i style={{width:(metric==='energy'?entry.totals.solar_percent??0:total?Math.abs(value(entry))/total*100:0)+'%',background:metric==='energy'?'#42c995':colors[entry.id]||colorFor(entry.id)}}/></div><b>{metric==='energy'?percent(entry.totals.solar_percent):entry.totals.average_price_per_kwh==null?'—':`${number(entry.totals.average_price_per_kwh,3)} €/kWh`}</b></div>)}</div>}
    </section>
    <section className="panel sessions-breakdown"><h2>{group==='solar'?'Répartition solaire / réseau':`${metric==='energy'?'Énergie':'Coût'} par ${group==='charger'?'point de charge':'véhicule'}`}</h2>
      <div className="sessions-donut-layout"><svg viewBox="0 0 140 140" className="sessions-donut" role="img" aria-label="Répartition de la sélection"><circle cx="70" cy="70" r="52" fill="none" stroke="var(--track)" strokeWidth="18"/>{distribution.map(entry=>{const fraction=total?Math.abs(entry.value)/total:0,start=offset;offset+=fraction;return <circle key={entry.id} cx="70" cy="70" r="52" fill="none" stroke={entry.color} strokeWidth="18" pathLength="100" strokeDasharray={`${fraction*100} ${100-fraction*100}`} strokeDashoffset={-start*100} transform="rotate(-90 70 70)"/>})}</svg><div className="sessions-legends">{distribution.map(e=><div key={e.id}><span><i style={{background:e.color}}/>{e.name}</span><strong>{format(e.value)}{metric==='cost'&&entries.find(entry=>entry.id===e.id)?.totals.cost_partial&&<small className="sessions-data-note">Partiel</small>}</strong></div>)}</div></div>
      {metric==='cost'&&distribution.some(e=>e.value<0)&&<p className="sessions-data-note">Le disque représente la valeur absolue des coûts ; les montants restent signés.</p>}
    </section>
  </div>
}
