import {useState} from 'react'
import type {Settings} from '../api/types'
import {api} from '../api/client'
import {PhaseSettings} from '../components/PhaseSettings'
import type {Run} from '../pages/Devices'
import {mergeDraft} from './mergeDraft'

export type SourceKind='grid'|'solar'|'house'|'price'
const fields={grid:['grid_entity','Entité puissance réseau signée'],solar:['solar_entity','Entité production solaire'],house:['house_entity','Entité consommation totale de la maison (facultatif)'],price:['price_entity','Entité prix actuel du réseau (€/kWh)']} as const
export function SourceEditor({kind,settings,run,onSaved}:{kind:SourceKind;settings:Settings;run:Run;onSaved:()=>void}){
  const [base]=useState(()=>structuredClone(settings.home_assistant)),[value,set]=useState(()=>structuredClone(settings.home_assistant))
  const [key,label]=fields[kind]
  function config(){return mergeDraft(settings.home_assistant,base,value)}
  return <form onSubmit={e=>{e.preventDefault();void run(async()=>{await api('/connections/home-assistant','PUT',{config:config(),token:null});onSaved()},'Source enregistrée')}}>
    <div className="source-integration"><strong>Home Assistant</strong><span>Les accès existants sont conservés.</span></div>
    <label>{label}<input value={value[key]||''} placeholder="sensor.nom_du_capteur" onChange={e=>set({...value,[key]:e.target.value.trim()})}/></label>
    {kind==='house'&&<p className="hint">Consommation totale du logement, voiture et ballon inclus. Sans capteur associé, la valeur est calculée avec réseau + solaire.</p>}
    {kind==='grid'&&<><label className="check"><input type="checkbox" checked={value.invert_grid} onChange={e=>set({...value,invert_grid:e.target.checked})}/>Inverser le signe réseau (import positif attendu)</label>
      <details open><summary>Courant, tension et limite par phase</summary><PhaseSettings value={value} onChange={set}/></details></>}
    <div className="actions"><button type="button" onClick={()=>void run(()=>api('/connections/home-assistant/test','POST',{config:config(),token:null}),'Lecture Home Assistant vérifiée')}>Tester la lecture</button><button className="primary">Enregistrer la source</button></div>
  </form>
}
