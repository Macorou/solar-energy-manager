import {useState} from 'react'
import {energy,money,percent,duration,fullDate} from './model'
import type {SessionPage,ChargingSession,Sort} from './types'
export function SessionTable({data,sort,direction,onSort,onPage,onOpen}:{data:SessionPage;sort:Sort;direction:'asc'|'desc';onSort:(s:Sort)=>void;onPage:(p:number)=>void;onOpen:(s:ChargingSession)=>void}){
  const [mobileColumn,setMobileColumn]=useState<'solar'|'cost'|'duration'>('solar')
  const columns:{id:Sort;name:string;className?:string}[]=[{id:'date',name:'Début'},{id:'charger',name:'Point de charge',className:'sessions-desktop'},{id:'vehicle',name:'Véhicule',className:'sessions-desktop'},{id:'energy',name:'Énergie chargée'},{id:'duration',name:'Durée de charge',className:'sessions-extra'},{id:'solar',name:'Solaire',className:'sessions-extra'},{id:'cost',name:'Coût',className:'sessions-extra'}]
  const total=data.totals
  const mobileValue=(s:ChargingSession)=>mobileColumn==='solar'?percent(s.solar_percent):mobileColumn==='cost'?money(s.cost_eur):duration(s.charge_duration_s)
  const pages=Math.max(1,Math.ceil(data.total/data.page_size))
  return <section className="panel sessions-table-panel"><div className="sessions-table-title"><h2>Aperçu</h2><span>{numberCount(data.total)} session{data.total!==1?'s':''}</span><label className="sessions-mobile-column">Afficher<select aria-label="Colonne mobile" value={mobileColumn} onChange={e=>setMobileColumn(e.target.value as typeof mobileColumn)}><option value="solar">Part solaire</option><option value="duration">Durée</option>{data.available.cost&&<option value="cost">Coût</option>}</select></label></div>
    <table className="sessions-table"><thead><tr>{columns.map(c=><th key={c.id} className={c.className} aria-sort={sort===c.id?(direction==='asc'?'ascending':'descending'):'none'}><button type="button" onClick={()=>onSort(c.id)}>{c.name}{sort===c.id&&<span aria-hidden="true">{direction==='asc'?' ↑':' ↓'}</span>}</button></th>)}<th className="sessions-mobile-value"><button type="button" onClick={()=>onSort(mobileColumn)}>{mobileColumn==='solar'?'Solaire':mobileColumn==='cost'?'Coût':'Durée'}{sort===mobileColumn&&(direction==='asc'?' ↑':' ↓')}</button></th></tr></thead>
      <tbody>{data.items.map(session=><tr key={session.id}>
        <td><button className="session-open" type="button" onClick={()=>onOpen(session)} aria-label={`Détails de la session du ${fullDate(session.started_at,data.timezone)}`}><span>{fullDate(session.started_at,data.timezone)}</span><small className="sessions-mobile-names">{session.vehicle_name}<br/>{session.device_name}</small>{session.active&&<small className="sessions-active">En cours</small>}</button></td>
        <td className="sessions-desktop">{session.device_name}</td><td className="sessions-desktop">{session.vehicle_name}</td>
        <td><strong>{energy(session.energy_kwh)}</strong>{session.energy_partial&&<small className="sessions-data-note">{session.energy_kwh==null?'Mesure absente':'Partielle'}</small>}</td>
        <td className="sessions-extra">{duration(session.charge_duration_s)}{session.duration_partial&&session.charge_duration_s!=null&&<small className="sessions-data-note">Partielle</small>}</td>
        <td className="sessions-extra">{percent(session.solar_percent)}</td><td className="sessions-extra">{money(session.cost_eur)}{session.cost_partial&&session.cost_eur!=null&&<small className="sessions-data-note">Partiel</small>}</td>
        <td className="sessions-mobile-value">{mobileValue(session)}{mobileColumn==='cost'&&session.cost_partial&&session.cost_eur!=null&&<small className="sessions-data-note">Partiel</small>}{mobileColumn==='duration'&&session.duration_partial&&session.charge_duration_s!=null&&<small className="sessions-data-note">Partielle</small>}</td>
      </tr>)}</tbody>
      <tfoot><tr><th colSpan={1}>Total sélection</th><td className="sessions-desktop"/><td className="sessions-desktop"/><td>{energy(total.energy_kwh)}{total.energy_partial&&<small className="sessions-data-note">Partielle</small>}</td><td className="sessions-extra">{duration(total.charge_duration_s)}</td><td className="sessions-extra">{percent(total.solar_percent)}</td><td className="sessions-extra">{money(total.cost_eur)}</td><td className="sessions-mobile-value">{mobileColumn==='solar'?percent(total.solar_percent):mobileColumn==='cost'?money(total.cost_eur):duration(total.charge_duration_s)}</td></tr></tfoot>
    </table>
    {!data.total&&<p className="sessions-empty">Aucune session pour cette sélection.</p>}
    {pages>1&&<div className="sessions-pagination"><button type="button" disabled={data.page<=1} onClick={()=>onPage(data.page-1)} aria-label="Page précédente">←</button><span>Page {data.page} sur {pages}</span><button type="button" disabled={data.page>=pages} onClick={()=>onPage(data.page+1)} aria-label="Page suivante">→</button></div>}
  </section>
}
const numberCount=(n:number)=>n.toLocaleString('fr-FR')
