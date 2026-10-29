import {useState} from 'react'
import type {Device,Settings,Vehicle} from '../api/types'
import {DeviceFields} from '../components/DeviceFields'
import {cloudDefaults} from '../components/Editors'
import {createId} from '../api/id'
import type {Run} from '../pages/Devices'
import {mergeDraft} from './mergeDraft'

export function newDevice(settings:Settings,kind:Device['kind']):Device{return {id:createId(),name:kind==='charger'?'Wallbox Pulsar Plus':'Ariston NUOS',kind,mode:'off',armed:false,capabilities_verified:false,offline_behavior_verified:false,priority:settings.devices.length+1,min_power_w:kind==='charger'?1380:700,max_power_w:kind==='charger'?3700:700,min_current_a:6,max_current_a:16,phases:1,grid_phases:[],voltage:230,charge_point_id:'',allow_insecure_identity:false,ocpp_profile:'auto',connector_id:1,vehicle_id:kind==='charger'?(settings.vehicles[0]?.id||''):'',gateway_id:'',target:kind==='charger'?null:55,solar_target:null,default_soc_target:80,confirmation_timeout_s:kind==='charger'?90:300,cloud:{...cloudDefaults}}}
export function DeviceEditor({initial,settings,save,run,onSaved}:{initial:Device;settings:Settings;save:(s:Settings)=>Promise<void>;run:Run;onSaved:()=>void}){
  const [base]=useState(()=>structuredClone(initial)),[baseEntity]=useState(settings.home_assistant.device_power_entities[initial.id]||'')
  const [value,set]=useState(()=>structuredClone(initial)),[entity,setEntity]=useState(baseEntity)
  return <form onSubmit={e=>{e.preventDefault();void run(async()=>{const exists=settings.devices.some(d=>d.id===value.id)
    await save({...settings,devices:exists?settings.devices.map(d=>d.id===value.id?{...mergeDraft(d,base,value),armed:d.armed,capabilities_verified:d.capabilities_verified,offline_behavior_verified:d.offline_behavior_verified}:d):[...settings.devices,value],home_assistant:{...settings.home_assistant,device_power_entities:entity===baseEntity?settings.home_assistant.device_power_entities:{...settings.home_assistant.device_power_entities,[value.id]:entity}}});onSaved()},'Appareil enregistré')}}>
    <DeviceFields editing={value} setEditing={set} vehicles={settings.vehicles}/>
    <label>Puissance mesurée · {value.name}<input value={entity} placeholder="sensor.puissance_appareil" onChange={e=>setEntity(e.target.value.trim())}/></label>
    <p className="hint">Enregistrez la configuration avant de tester la connexion et d’activer le pilotage.</p>
    <div className="actions"><button className="primary">Enregistrer l’appareil</button></div>
  </form>
}
export function VehicleEditor({initial,settings,save,run,onSaved}:{initial:Vehicle;settings:Settings;save:(s:Settings)=>Promise<void>;run:Run;onSaved:()=>void}){
  const [base]=useState(()=>structuredClone(initial)),[value,set]=useState(()=>structuredClone(initial))
  return <form onSubmit={e=>{e.preventDefault();void run(async()=>{await save({...settings,vehicles:settings.vehicles.some(v=>v.id===value.id)?settings.vehicles.map(v=>v.id===value.id?mergeDraft(v,base,value):v):[...settings.vehicles,value]});onSaved()},'Véhicule enregistré')}}>
    <div className="form-grid"><label>Nom du véhicule<input required value={value.name} onChange={e=>set({...value,name:e.target.value})}/></label><label>VIN Peugeot<input value={value.vin} onChange={e=>set({...value,vin:e.target.value.trim().toUpperCase()})}/></label>
      <label>Capacité utile connue (kWh, facultatif)<input type="number" min="1" step=".1" value={value.capacity_kwh??''} onChange={e=>set({...value,capacity_kwh:e.target.value?Number(e.target.value):null})}/></label></div>
    <p className="hint">L’estimation utilise la dernière valeur Peugeot et l’énergie chargée. Le rendement initial de 85 % s’ajuste aux nouveaux relevés.</p>
    <div className="actions"><button className="primary">Enregistrer le véhicule</button></div>
  </form>
}
