import {useState} from 'react'
import type {Cloud,Program} from '../api/types'
import {createId} from '../api/id'

export const cloudDefaults:Cloud={start_surplus_w:0,start_delay_s:60,import_tolerance_w:0,stop_delay_s:180,min_run_s:300,restart_delay_s:120}
const fields:[keyof Cloud,string][]=[['start_surplus_w','Seuil de démarrage (W)'],['start_delay_s','Surplus stable avant démarrage (s)'],
  ['import_tolerance_w','Tolérance réseau (W)'],['stop_delay_s','Déficit avant suspension (s)'],
  ['min_run_s','Durée minimale de fonctionnement (s)'],['restart_delay_s','Délai avant redémarrage (s)']]
export function CloudSettingsForm({value,onChange}:{value:Cloud;onChange:(value:Cloud)=>void}) {
  return <fieldset><legend>Passages de nuages</legend><p className="hint">Les seuils et temporisations s’appliquent uniquement à cet appareil.</p>
    <div className="form-grid">{fields.map(([key,label])=><label key={key}>{label}<input type="number" min="0" required
      value={value[key]} onChange={e=>onChange({...value,[key]:Number(e.target.value)})}/></label>)}</div></fieldset>
}
const days=['Lun','Mar','Mer','Jeu','Ven','Sam','Dim']
export function ChargeProgramEditor({vehicles,initial,onSave,onCancel}:{vehicles:{id:string;name:string}[];initial?:Program;
  onSave:(value:Program)=>void;onCancel?:()=>void}) {
  const [value,set]=useState<Program>(initial||{id:createId(),name:'',vehicle_id:vehicles[0]?.id||'',weekdays:[0,1,2,3,4],
    earliest_start:'22:00',deadline:'05:45',target_soc:80,solar_early:true,solar_horizon_hours:24,enabled:true})
  return <form onSubmit={e=>{e.preventDefault();onSave(value)}} className="editor">
    <div className="form-grid"><label>Nom du programme<input required value={value.name} onChange={e=>set({...value,name:e.target.value})}/></label>
      <label>Véhicule<select required value={value.vehicle_id} onChange={e=>set({...value,vehicle_id:e.target.value})}>
        {vehicles.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label></div>
    <fieldset><legend>Jours de l’échéance</legend><div className="days">{days.map((day,i)=><label key={day} className={value.weekdays.includes(i)?'selected':''}>
      <input type="checkbox" checked={value.weekdays.includes(i)} onChange={e=>set({...value,weekdays:e.target.checked?
        [...value.weekdays,i].sort():value.weekdays.filter(d=>d!==i)})}/>{day}</label>)}</div></fieldset>
    <div className="form-grid"><label>Début réseau autorisé<input type="time" required value={value.earliest_start} onChange={e=>set({...value,earliest_start:e.target.value})}/></label>
      <label>Prêt à<input type="time" required value={value.deadline} onChange={e=>set({...value,deadline:e.target.value})}/></label>
      <label>Objectif batterie (%)<input type="number" required min="1" max="100" value={value.target_soc} onChange={e=>set({...value,target_soc:Number(e.target.value)})}/></label>
      <label>Anticipation solaire (heures)<input type="number" min="0" max="168" required value={value.solar_horizon_hours} onChange={e=>set({...value,solar_horizon_hours:Number(e.target.value)})}/></label></div>
    <p className="hint">{value.earliest_start>=value.deadline?'Le début réseau est la veille de l’échéance.':'Le début réseau et l’échéance sont le même jour.'}</p>
    <label className="check"><input type="checkbox" checked={value.solar_early} onChange={e=>set({...value,solar_early:e.target.checked})}/>Autoriser le solaire avant le début réseau</label>
    <div className="actions"><button className="primary" disabled={!vehicles.length||!value.weekdays.length}>Enregistrer le programme</button>
      {onCancel&&<button type="button" onClick={onCancel}>Annuler</button>}</div></form>
}
