import {useState} from 'react'
import {energy,money,percent,duration,fullDate,knownCost} from './model'
import type {SessionPage,ChargingSession,Sort,Totals} from './types'

type MobileMetric='energy'|'solar'|'cost'|'duration'
const metrics:{id:MobileMetric;name:string}[]=[{id:'energy',name:'Chargé'},{id:'cost',name:'Coût'},{id:'solar',name:'Part solaire'},{id:'duration',name:'Durée'}]

function MetricValue({row,metric,total=false}:{row:ChargingSession|Totals;metric:MobileMetric;total?:boolean}){
  const cost=total?knownCost(row as Totals):row.cost_eur
  const value=metric==='energy'?energy(row.energy_kwh):metric==='cost'?money(cost):metric==='solar'?percent(row.solar_percent):duration(row.charge_duration_s)
  const partial=metric==='energy'?row.energy_partial:metric==='cost'?row.cost_partial:metric==='duration'?row.duration_partial:row.solar_partial
  return <><strong>{value}</strong>{partial&&value!=='—'&&<small className="sessions-data-note">{metric==='cost'?'Partiel':'Partielle'}</small>}{metric==='energy'&&row.energy_kwh==null&&<small className="sessions-data-note">Mesure absente</small>}</>
}

export function SessionTable({data,sort,direction,onSort,onPage,onOpen}:{data:SessionPage;sort:Sort;direction:'asc'|'desc';onSort:(s:Sort)=>void;onPage:(p:number)=>void;onOpen:(s:ChargingSession)=>void}){
  const [first,setFirst]=useState<MobileMetric>('energy'),[second,setSecond]=useState<MobileMetric>('solar')
  const columns:{id:Sort;name:string;className?:string}[]=[{id:'date',name:'Début'},{id:'charger',name:'Point de charge',className:'sessions-desktop'},{id:'vehicle',name:'Véhicule',className:'sessions-desktop'},{id:'energy',name:'Chargé',className:'sessions-extra'},{id:'duration',name:'Durée de charge',className:'sessions-extra'},{id:'solar',name:'Solaire',className:'sessions-extra'},{id:'cost',name:'Coût',className:'sessions-extra'}]
  const pages=Math.max(1,Math.ceil(data.total/data.page_size))
  function changeMetric(position:1|2,value:MobileMetric){
    if(position===1){if(value===second)setSecond(first);setFirst(value)}
    else{if(value===first)setFirst(second);setSecond(value)}
  }
  function selector(position:1|2){const value=position===1?first:second;return <div className="sessions-metric-head"><select aria-label={position===1?'Première colonne mobile':'Colonne mobile'} value={value} onChange={e=>changeMetric(position,e.target.value as MobileMetric)}>{metrics.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select><button type="button" aria-label={`Trier la ${position===1?'première':'seconde'} colonne`} onClick={()=>onSort(value)}>{sort===value?(direction==='asc'?'↑':'↓'):'↕'}</button></div>}
  return <section className="panel sessions-table-panel"><div className="sessions-table-title"><h2>Aperçu</h2><span>{data.total.toLocaleString('fr-FR')} session{data.total!==1?'s':''}</span></div>
    <table className="sessions-table"><thead><tr>{columns.map(c=><th key={c.id} className={c.className} aria-sort={sort===c.id?(direction==='asc'?'ascending':'descending'):'none'}><button type="button" onClick={()=>onSort(c.id)}>{c.name}{sort===c.id&&<span aria-hidden="true">{direction==='asc'?' ↑':' ↓'}</span>}</button></th>)}<th className="sessions-mobile-value">{selector(1)}</th><th className="sessions-mobile-value">{selector(2)}</th></tr></thead>
      <tbody>{data.items.map(session=><tr key={session.id}>
        <td><button className="session-open" type="button" onClick={()=>onOpen(session)} aria-label={`Détails de la session du ${fullDate(session.started_at,data.timezone)}`}><span>{fullDate(session.started_at,data.timezone)}</span><small className="sessions-mobile-names">{session.vehicle_name}<br/>{session.device_name}</small>{session.active&&<small className="sessions-active">En cours</small>}</button></td>
        <td className="sessions-desktop">{session.device_name}</td><td className="sessions-desktop">{session.vehicle_name}</td>
        {(['energy','duration','solar','cost'] as MobileMetric[]).map(metric=><td className="sessions-extra" key={metric}><MetricValue row={session} metric={metric}/></td>)}
        <td className="sessions-mobile-value"><MetricValue row={session} metric={first}/></td><td className="sessions-mobile-value"><MetricValue row={session} metric={second}/></td>
      </tr>)}</tbody>
      <tfoot><tr><th>Total sélection</th><td className="sessions-desktop"/><td className="sessions-desktop"/>{(['energy','duration','solar','cost'] as MobileMetric[]).map(metric=><td className="sessions-extra" key={metric}><MetricValue row={data.totals} metric={metric} total/></td>)}<td className="sessions-mobile-value"><MetricValue row={data.totals} metric={first} total/></td><td className="sessions-mobile-value"><MetricValue row={data.totals} metric={second} total/></td></tr></tfoot>
    </table>
    {!data.total&&<p className="sessions-empty">Aucune session pour cette sélection.</p>}
    {pages>1&&<div className="sessions-pagination"><button type="button" disabled={data.page<=1} onClick={()=>onPage(data.page-1)} aria-label="Page précédente">←</button><span>Page {data.page} sur {pages}</span><button type="button" disabled={data.page>=pages} onClick={()=>onPage(data.page+1)} aria-label="Page suivante">→</button></div>}
  </section>
}
