import {useState} from 'react'
import type {Program,Settings} from '../api/types'
import {ChargeProgramEditor} from '../components/Editors'
import {api,date} from '../api/client'
import type {Run} from './Devices'
export function Planning({settings,save,run}:{settings:Settings;save:(value:Settings)=>Promise<void>;run:Run}) {
  const [editing,setEditing]=useState<Program|true|null>(null)
  const [windows,setWindows]=useState(settings.off_peak)
  const [preview,setPreview]=useState<{id:string;deadline_at:string;target_soc:number;network_start_at:string}[]>([])
  const days=['Lun','Mar','Mer','Jeu','Ven','Sam','Dim']
  return <><div className="section-title"><p className="subtitle">Définissez l’heure de départ et laissez le solaire prendre de l’avance.</p><button className="primary" disabled={!settings.vehicles.length} onClick={()=>setEditing(true)}>Créer un programme</button></div>
    {!settings.vehicles.length&&<p className="notice">Ajoutez d’abord un véhicule dans Bornes et véhicules.</p>}
    <div className="program-grid">{settings.schedules.map(p=><article className="panel program" key={p.id}><div className="section-title"><h2>{p.name}</h2><span className={'badge '+(p.enabled?'green':'neutral')}>{p.enabled?'Actif':'Désactivé'}</span></div>
      <div className="program-target"><strong>{p.target_soc}<small>%</small></strong><span>prêt à <b>{p.deadline}</b></span></div>
      <div className="days static">{days.map((day,i)=><span className={p.weekdays.includes(i)?'selected':''} key={day}>{day}</span>)}</div>
      <p>Réseau à partir de {p.earliest_start>=p.deadline?'la veille à ':''}<b>{p.earliest_start}</b></p><p className="hint">{p.solar_early?`Solaire autorisé jusqu’à ${p.solar_horizon_hours} h avant l’échéance`:'Solaire dans le créneau uniquement'}</p>
      <div className="actions"><button onClick={()=>setEditing(p)}>Modifier</button><button onClick={()=>run(()=>api(`/schedules/${p.id}`,'PUT',{...p,enabled:!p.enabled}),'Programme mis à jour')}>{p.enabled?'Désactiver':'Activer'}</button>
        <button className="danger" onClick={()=>run(()=>api(`/schedules/${p.id}`,'DELETE'),'Programme supprimé')}>Supprimer</button></div></article>)}</div>
    {!settings.schedules.length&&<div className="empty panel"><h2>Votre premier départ serein</h2><p>Exemple : 80 % à 05:45 du lundi au vendredi. Les jours sont ceux de l’échéance.</p></div>}
    {editing&&<section className="panel"><h2>{editing===true?'Nouveau programme':'Modifier le programme'}</h2><ChargeProgramEditor key={editing===true?'new':editing.id} initial={editing===true?undefined:editing} vehicles={settings.vehicles}
      onSave={value=>run(async()=>{await api('/schedules'+(editing===true?'':'/'+value.id),editing===true?'POST':'PUT',value);setEditing(null)},'Programme enregistré')} onCancel={()=>setEditing(null)}/></section>}
    <section className="panel"><div className="section-title"><h2>Prochaines échéances</h2><button onClick={()=>run(async()=>setPreview(await api('/schedules/preview')))}>Actualiser l’aperçu</button></div>
      {preview.map(p=><div className="list-row" key={p.id}><strong>{date(p.deadline_at)} · {p.target_soc} %</strong><span className="hint">Réseau dès {date(p.network_start_at)}</span></div>)}
      {!preview.length&&<p className="hint">L’aperçu est calculé par le serveur dans le fuseau {settings.timezone}.</p>}</section>
    <section className="panel"><div className="section-title"><h2>Heures creuses</h2><span className="badge neutral">Horaires locaux · {settings.timezone}</span></div><p className="hint">Ces plages autorisent le ballon en mode HC/HP + solaire. Elles sont indépendantes des programmes voiture.</p>
      {windows.map((w,i)=><fieldset key={i}><legend>Plage {i+1}</legend><div className="form-grid"><label>Début HC<input type="time" value={w.start} onChange={e=>setWindows(windows.map((v,n)=>n===i?{...v,start:e.target.value}:v))}/></label>
        <label>Fin HC<input type="time" value={w.end} onChange={e=>setWindows(windows.map((v,n)=>n===i?{...v,end:e.target.value}:v))}/></label></div>
        <div className="days">{days.map((day,n)=><label key={day} className={w.weekdays.includes(n)?'selected':''}><input type="checkbox" checked={w.weekdays.includes(n)} onChange={e=>setWindows(windows.map((v,k)=>k===i?{...v,weekdays:e.target.checked?[...v.weekdays,n]:v.weekdays.filter(d=>d!==n)}:v))}/>{day}</label>)}</div>
        <p className="hint">{w.start>=w.end?'Fin le lendemain du jour coché.':'Début et fin le même jour.'}</p><button onClick={()=>setWindows(windows.filter((_,n)=>i!==n))}>Retirer cette plage</button></fieldset>)}
      <div className="actions"><button onClick={()=>setWindows([...windows,{start:'22:00',end:'06:00',weekdays:[0,1,2,3,4,5,6]}])}>Ajouter une plage HC</button>
        <button className="primary" onClick={()=>run(()=>save({...settings,off_peak:windows}),'Heures creuses enregistrées')}>Enregistrer les heures creuses</button></div></section>
  </>
}
