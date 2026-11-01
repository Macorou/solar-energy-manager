import {useEffect,useId,useRef,useState} from 'react'
import {createPortal} from 'react-dom'
import {api} from '../api/client'
import {Icon} from '../components/Icon'
import {energy,money,number,percent,duration,fullDate} from './model'
import type {ChargingSession,Option} from './types'

export function SessionDetail({id,timezone,vehicles,onClose,onChanged}:{id:string;timezone:string;vehicles:Option[];onClose:()=>void;onChanged:()=>void}){
  const ref=useRef<HTMLDialogElement>(null),heading=useId()
  const [session,setSession]=useState<ChargingSession|null>(null),[error,setError]=useState(''),[pending,setPending]=useState(false)
  const [vehicle,setVehicle]=useState(''),[confirm,setConfirm]=useState<'edit'|'delete'|null>(null)
  useEffect(()=>{const dialog=ref.current!,previous=document.activeElement as HTMLElement|null
    dialog.showModal();let active=true
    api<ChargingSession>(`/charging-sessions/${encodeURIComponent(id)}`).then(row=>{if(active){setSession(row);setVehicle(row.vehicle_id)}}).catch(e=>{if(active)setError(e.message)})
    return()=>{active=false;dialog.close();previous?.focus()}
  },[id])
  async function mutate(){setPending(true);setError('')
    try{if(confirm==='delete'){await api(`/charging-sessions/${encodeURIComponent(id)}`,'DELETE',{confirm:true});onChanged();onClose()}
      else{const row=await api<ChargingSession>(`/charging-sessions/${encodeURIComponent(id)}`,'PATCH',{vehicle_id:vehicle,confirm:true});setSession(row);setConfirm(null);onChanged()}}
    catch(e){setError((e as Error).message)}finally{setPending(false)}
  }
  const rows=session?[
    ['Début',fullDate(session.started_at,timezone)],['Fin',session.active?'En cours':fullDate(session.ended_at,timezone)],
    ['Durée de branchement',session.ended_at?duration((new Date(session.ended_at).getTime()-new Date(session.started_at).getTime())/1000):null],
    ['Durée de charge',session.charge_duration_s==null?null:duration(session.charge_duration_s)+(session.duration_partial?' · partielle':'')],
    ['Point de charge',session.device_name],['Véhicule',session.vehicle_name],
    ['Énergie chargée',session.energy_kwh==null?'Mesure absente':energy(session.energy_kwh)+(session.energy_partial?' · partielle':'')],
    ['Solaire',session.solar_kwh==null?null:energy(session.solar_kwh)],['Réseau électrique',session.grid_kwh==null?null:energy(session.grid_kwh)],
    ['Origine inconnue',session.unknown_kwh!=null&&session.unknown_kwh>1e-8?energy(session.unknown_kwh):null],
    ['Part solaire',session.solar_percent==null?null:percent(session.solar_percent)+(session.solar_partial?' · partielle':'')],
    ['Coût',session.cost_eur==null?null:money(session.cost_eur)+(session.cost_partial?' · partiel':'')],
    ['Prix moyen au kWh',session.average_price_per_kwh==null?null:`${number(session.average_price_per_kwh,4)} €/kWh`],
    ['Batterie au début',session.soc_start==null?'Non enregistrée':percent(session.soc_start)],
    [session.active?'Batterie actuelle':'Batterie à la fin',session.soc_end==null?null:percent(session.soc_end)+(session.soc_end_estimated?' · estimée':'')],
  ]:[]
  return createPortal(<dialog ref={ref} className="settings-dialog session-detail" aria-labelledby={heading} onCancel={e=>{e.preventDefault();if(!pending)onClose()}}>
    <header className="settings-dialog-head"><div><span className="eyebrow">SESSIONS DE CHARGE</span><h2 id={heading}>Détail de la session</h2></div><button type="button" className="icon-button" aria-label="Fermer les détails" onClick={onClose} disabled={pending}><Icon name="close"/></button></header>
    <div className="settings-dialog-body">{error&&<p className="alert error" role="alert">{error}</p>}{!session&&!error&&<p role="status">Chargement de la session…</p>}
      {session&&<><dl className="session-detail-values">{rows.filter(([,v])=>v!=null).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        {(session.energy_partial||session.solar_partial)&&<p className="hint">{session.energy_partial?'Les mesures disponibles couvrent une partie de cette session. ':''}{session.solar_partial?session.solar_percent==null?'La part solaire ne peut pas être déterminée.':'La part solaire porte sur l’énergie d’origine connue.':''}</p>}
        {session.editable&&<div className="session-edit"><label>Affecter à un véhicule<select value={vehicle} disabled={pending} onChange={e=>{setVehicle(e.target.value);setConfirm(null)}}><option value="">Véhicule inconnu</option>{session.vehicle_id&&!vehicles.some(v=>v.id===session.vehicle_id)&&<option value={session.vehicle_id} disabled>{session.vehicle_name} (retiré)</option>}{vehicles.filter(v=>v.id).map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label><div className="session-detail-actions"><button type="button" disabled={pending||vehicle===session.vehicle_id} onClick={()=>setConfirm('edit')}>Modifier l’affectation</button><button type="button" className="danger" disabled={pending} onClick={()=>setConfirm('delete')}><Icon name="trash" size={17}/>Supprimer la session</button></div></div>}
        {confirm&&<div className="session-confirm" role="group" aria-label="Confirmer la modification"><p>{confirm==='delete'?'Supprimer définitivement cette session de l’historique local ? Cette action est irréversible.':'Confirmer l’affectation de cette session au véhicule sélectionné ?'}</p><div className="session-detail-actions"><button type="button" disabled={pending} onClick={()=>setConfirm(null)}>Annuler</button><button type="button" className={confirm==='delete'?'danger':'primary'} disabled={pending} onClick={mutate}>{pending?'Enregistrement…':confirm==='delete'?'Confirmer la suppression':'Confirmer l’affectation'}</button></div></div>}
      </>}
    </div><footer className="settings-dialog-foot"><span>Historique local · {timezone}</span><button type="button" onClick={onClose} disabled={pending}>Fermer</button></footer>
  </dialog>,document.body)
}
