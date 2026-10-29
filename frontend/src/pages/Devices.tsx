import {useState} from 'react'
import type {Device,Settings,Vehicle} from '../api/types'
import {CloudSettingsForm,cloudDefaults} from '../components/Editors'
import {Icon} from '../components/Icon'
import {api} from '../api/client'
import {createId} from '../api/id'
export type Run=(operation:()=>Promise<unknown>,message?:string)=>Promise<void>
const modes={off:'Arrêt',solar:'Solaire',planned:'Planifié',off_peak_solar:'HC/HP + solaire',manual:'Manuel temporaire'}
export function Devices({settings,save,run,kind}:{settings:Settings;save:(value:Settings)=>Promise<void>;run:Run;kind:Device['kind']}) {
  const [editing,setEditing]=useState<Device|null>(null)
  const [vehicle,setVehicle]=useState<Vehicle|null>(null)
  const [arming,setArming]=useState<string|null>(null)
  const [checks,setChecks]=useState([false,false,false])
  const [probe,setProbe]=useState<Record<string,string>>({})
  const devices=settings.devices.filter(d=>d.kind===kind)
  function createDevice() {
    setEditing({id:createId(),name:kind==='charger'?'Wallbox Pulsar Plus':'Ariston NUOS',kind,mode:'off',
      armed:false,capabilities_verified:false,offline_behavior_verified:false,priority:settings.devices.length+1,
      min_power_w:kind==='charger'?1380:700,max_power_w:kind==='charger'?3700:700,min_current_a:6,max_current_a:16,
      phases:1,grid_phases:[],voltage:230,charge_point_id:'',allow_insecure_identity:false,connector_id:1,vehicle_id:kind==='charger'?(settings.vehicles[0]?.id||''):'',
      gateway_id:'',target:kind==='charger'?null:55,solar_target:null,default_soc_target:80,confirmation_timeout_s:kind==='charger'?90:300,cloud:{...cloudDefaults}})
  }
  return <><div className="section-title"><p className="subtitle">{kind==='charger'?'Enregistrez vos bornes OCPP et associez chaque véhicule.':'Une demande native de chauffe, avec sa puissance électrique mesurée.'}</p>
    <button className="primary" onClick={createDevice}><Icon name="plus" size={17}/>Ajouter {kind==='charger'?'une borne':'un ballon'}</button></div>
    {!devices.length&&<div className="empty panel"><Icon name={kind==='charger'?'car':'drop'} size={48}/><h2>Aucun {kind==='charger'?'point de recharge':'ballon'} enregistré</h2><p>Commencez par la connexion en observation, puis vérifiez les capacités avant l’activation.</p></div>}
    <div className="config-list">{devices.map(d=><article className="panel" key={d.id}><div className="section-title"><div><h2>{d.name}</h2><p className="hint">{d.kind==='charger'?d.charge_point_id||'Identifiant OCPP à renseigner':d.gateway_id||'Passerelle à renseigner'}</p></div>
      <span className={'badge '+(d.armed?'green':'neutral')}>{d.armed?'Activé':'Observation'}</span></div>
      <div className="device-summary"><span>Mode <b>{modes[d.mode]}</b></span><span>Priorité <b>{d.priority}</b></span><span>Puissance maximale <b>{d.max_power_w} W</b></span></div>
      {probe[d.id]&&<p className="notice">{probe[d.id]}</p>}
      <div className="actions"><button onClick={()=>setEditing(structuredClone(d))}>Configurer</button>
        <button onClick={()=>run(async()=>{const result=await api<{supported?:string[];capabilities?:{supported:string[]}}>(`/${kind==='charger'?'chargers':'water-heaters'}/${d.id}/test`,'POST');
          setProbe({...probe,[d.id]:'Capacités : '+(result.supported||result.capabilities?.supported||[]).join(', ')})},'Lecture de connexion effectuée')}>Tester la connexion</button>
        <button onClick={()=>{setArming(d.id);setChecks([false,false,false])}} disabled={d.armed}>Activer le pilotage</button>
        {d.armed&&<button onClick={()=>run(()=>api(`/devices/${d.id}/disarm`,'POST'),'Appareil désactivé')}>Désactiver après arrêt</button>}
        <button className="danger" disabled={d.armed} onClick={()=>run(()=>api(`/${kind==='charger'?'chargers':'water-heaters'}/${d.id}`,'DELETE'),'Appareil supprimé')}>Supprimer</button></div>
      {arming===d.id&&<div className="arm-box"><h3>Vérification avant pilotage</h3><p>Effectuez ces essais sur l’installation avant de les confirmer. Le test de connexion ci-dessus ne commande aucun démarrage.</p>
        {['Commande et limites natives vérifiées sur cet appareil','Comportement en perte de connexion et hors ligne vérifié','J’autorise les commandes automatiques de cet appareil'].map((s,i)=><label className="check" key={s}><input type="checkbox" checked={checks[i]} onChange={e=>setChecks(checks.map((v,n)=>n===i?e.target.checked:v))}/>{s}</label>)}
        <div className="actions"><button className="primary" disabled={!checks.every(Boolean)} onClick={()=>run(async()=>{await api(`/${kind==='charger'?'chargers':'water-heaters'}/${d.id}/arm`,'POST',
          {confirm_control:true,capabilities_verified:true,offline_behavior_verified:true});setArming(null)},'Pilotage activé')}>Confirmer l’activation</button><button onClick={()=>setArming(null)}>Annuler</button></div></div>}
    </article>)}</div>
    {editing&&<section className="panel editor"><div className="section-title"><h2>Configuration de l’appareil</h2><button onClick={()=>setEditing(null)}>Fermer</button></div>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{await save({...settings,devices:[...settings.devices.filter(d=>d.id!==editing.id),editing]});setEditing(null)},'Appareil enregistré')}}>
        <div className="form-grid"><label>Nom<input required value={editing.name} onChange={e=>setEditing({...editing,name:e.target.value})}/></label>
          <label>Mode<select value={editing.mode} onChange={e=>setEditing({...editing,mode:e.target.value as Device['mode']})}>{Object.entries(modes).filter(([m])=>m!=='manual'&&(kind==='charger'?m!=='off_peak_solar':m!=='planned')).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
          <label>Priorité (1 = premier)<input required type="number" min="1" max="100" value={editing.priority} onChange={e=>setEditing({...editing,priority:Number(e.target.value)})}/></label>
          <label>Puissance minimale (W)<input required type="number" min="1" value={editing.min_power_w} onChange={e=>setEditing({...editing,min_power_w:Number(e.target.value)})}/></label>
          <label>Puissance maximale (W)<input required type="number" min="1" value={editing.max_power_w} onChange={e=>setEditing({...editing,max_power_w:Number(e.target.value)})}/></label>
          <label>Délai de confirmation physique (s)<input required type="number" min="30" max="3600" value={editing.confirmation_timeout_s} onChange={e=>setEditing({...editing,confirmation_timeout_s:Number(e.target.value)})}/></label>
          {kind==='charger'?<><label>Identifiant de la borne OCPP<input required value={editing.charge_point_id} onChange={e=>setEditing({...editing,charge_point_id:e.target.value})}/></label>
            <label>Numéro de connecteur<input type="number" min="1" required value={editing.connector_id} onChange={e=>setEditing({...editing,connector_id:Number(e.target.value)})}/></label>
            <label>Véhicule associé<select required value={editing.vehicle_id} onChange={e=>setEditing({...editing,vehicle_id:e.target.value})}><option value="">Choisir</option>{settings.vehicles.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label>
            <label>Phases<select value={editing.phases} onChange={e=>setEditing({...editing,phases:Number(e.target.value) as 1|3,grid_phases:[]})}><option value="1">Monophasé</option><option value="3">Triphasé</option></select></label>
            <label>Phase réseau utilisée<select value={(editing.grid_phases||[]).join(',')} onChange={e=>setEditing({...editing,grid_phases:e.target.value?e.target.value.split(',') as Device['grid_phases']:[]})}>
              <option value="">À renseigner pour la limitation par phase</option>{editing.phases===1?['L1','L2','L3'].map(p=><option key={p} value={p}>{p}</option>):<><option value="L1,L2,L3">L1, L2, L3</option><option value="L2,L3,L1">L2, L3, L1</option><option value="L3,L1,L2">L3, L1, L2</option></>}</select></label>
            <label>Courant minimal (A)<input required type="number" min="6" value={editing.min_current_a} onChange={e=>setEditing({...editing,min_current_a:Number(e.target.value)})}/></label>
            <label>Courant maximal (A)<input required type="number" min="6" max="80" value={editing.max_current_a} onChange={e=>setEditing({...editing,max_current_a:Number(e.target.value)})}/></label>
            <label>Objectif solaire habituel (%)<input type="number" min="1" max="100" required value={editing.default_soc_target} onChange={e=>setEditing({...editing,default_soc_target:Number(e.target.value)})}/></label></>:
            <><label>Identifiant passerelle Ariston<input required value={editing.gateway_id} onChange={e=>setEditing({...editing,gateway_id:e.target.value})}/></label>
              <label>Consigne sur le réseau (°C)<input type="number" required value={editing.target??55} onChange={e=>setEditing({...editing,target:Number(e.target.value)})}/></label>
              <label>Consigne sur surplus solaire (°C)<input type="number" min="0" max="100" required value={editing.solar_target??editing.target??55} onChange={e=>setEditing({...editing,solar_target:Number(e.target.value)})}/></label></>}
        </div>
        {kind==='water_heater'&&<p className="hint">Le surplus solaire peut chauffer au-delà de la consigne réseau. Les deux températures doivent respecter les limites natives du ballon. Le mode manuel utilise la consigne réseau.</p>}
        {kind==='charger'&&<label className="check"><input type="checkbox" checked={editing.allow_insecure_identity} onChange={e=>setEditing({...editing,allow_insecure_identity:e.target.checked})}/>Autoriser l’identité OCPP sans mot de passe sur le réseau local de confiance</label>}
        <CloudSettingsForm value={editing.cloud} onChange={cloud=>setEditing({...editing,cloud})}/>
        <button className="primary">Enregistrer l’appareil</button></form></section>}
    {kind==='charger'&&<section className="panel"><div className="section-title"><h2>Véhicules</h2><button onClick={()=>setVehicle({id:createId(),name:'Peugeot e-208 2020',vin:'',capacity_kwh:null,efficiency:.85})}>Ajouter un véhicule</button></div>
      {settings.vehicles.map(v=><div className="list-row" key={v.id}><div><strong>{v.name}</strong><span className="hint">{v.vin?'VIN renseigné':'VIN à renseigner'}</span></div><button onClick={()=>setVehicle(v)}>Modifier</button></div>)}
      {vehicle&&<form onSubmit={e=>{e.preventDefault();run(async()=>{await save({...settings,vehicles:[...settings.vehicles.filter(v=>v.id!==vehicle.id),vehicle]});setVehicle(null)},'Véhicule enregistré')}}>
        <div className="form-grid"><label>Nom du véhicule<input required value={vehicle.name} onChange={e=>setVehicle({...vehicle,name:e.target.value})}/></label><label>VIN Peugeot<input value={vehicle.vin} onChange={e=>setVehicle({...vehicle,vin:e.target.value.trim().toUpperCase()})}/></label>
          <label>Capacité utile connue (kWh, facultatif)<input type="number" min="1" step=".1" value={vehicle.capacity_kwh??''} onChange={e=>setVehicle({...vehicle,capacity_kwh:e.target.value?Number(e.target.value):null})}/></label>
          </div>
        <p className="hint">L’estimation EVCC utilise la capacité et les kWh de la borne pour suivre la batterie entre les réponses Peugeot. Son rendement initial de 85 % s’ajuste automatiquement aux relevés du véhicule.</p>
        <div className="actions"><button className="primary">Enregistrer le véhicule</button><button type="button" onClick={()=>setVehicle(null)}>Annuler</button></div></form>}</section>}
  </>
}
