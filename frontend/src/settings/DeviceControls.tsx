import {useState} from 'react'
import type {Device} from '../api/types'
import {api} from '../api/client'
import type {Run} from '../pages/Devices'
export function DeviceControls({device,run,onRemoved}:{device:Device;run:Run;onRemoved:()=>void}){
  const [arming,setArming]=useState(false),[checks,setChecks]=useState([false,false,false]),[probe,setProbe]=useState(''),[removing,setRemoving]=useState(false)
  const path=`/${device.kind==='charger'?'chargers':'water-heaters'}/${device.id}`
  return <section className="device-commissioning" aria-label="Connexion et pilotage"><h3>Connexion et pilotage</h3>
    <p className="hint">{device.armed?'Pilotage activé':'Observation · aucune commande automatique'}</p>{probe&&<p className="notice">{probe}</p>}
    <div className="actions"><button type="button" onClick={()=>void run(async()=>{const r=await api<{supported?:string[];capabilities?:{supported:string[]}}>(path+'/test','POST');setProbe('Capacités : '+(r.supported||r.capabilities?.supported||[]).join(', '))},'Lecture de connexion effectuée')}>Tester la connexion</button>
      {device.armed?<button type="button" onClick={()=>void run(()=>api(`/devices/${device.id}/disarm`,'POST'),'Appareil désactivé')}>Désactiver après arrêt</button>:<button type="button" onClick={()=>{setArming(true);setChecks([false,false,false])}}>Activer le pilotage</button>}
      <button type="button" className="danger" disabled={device.armed} onClick={()=>setRemoving(true)}>Supprimer l’appareil</button></div>
    {removing&&<div className="notice"><p>Supprimer {device.name} et sa configuration ?</p><div className="actions"><button type="button" className="danger" onClick={()=>void run(async()=>{await api(path,'DELETE');onRemoved()},'Appareil supprimé')}>Confirmer la suppression</button><button type="button" onClick={()=>setRemoving(false)}>Conserver l’appareil</button></div></div>}
    {arming&&!device.armed&&<div className="arm-box"><h3>Vérification avant pilotage</h3><p>Effectuez ces essais sur l’installation. Le test de connexion ne commande aucun démarrage.</p>
      {['Commande et limites natives vérifiées sur cet appareil','Comportement en perte de connexion et hors ligne vérifié','J’autorise les commandes automatiques de cet appareil'].map((text,i)=><label className="check" key={text}><input type="checkbox" checked={checks[i]} onChange={e=>setChecks(checks.map((v,n)=>n===i?e.target.checked:v))}/>{text}</label>)}
      <div className="actions"><button type="button" className="primary" disabled={!checks.every(Boolean)} onClick={()=>void run(async()=>{await api(path+'/arm','POST',{confirm_control:true,capabilities_verified:true,offline_behavior_verified:true});setArming(false)},'Pilotage activé')}>Confirmer l’activation</button><button type="button" onClick={()=>setArming(false)}>Annuler l’activation</button></div></div>}
  </section>
}
