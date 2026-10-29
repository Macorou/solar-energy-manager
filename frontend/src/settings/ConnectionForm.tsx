import {useState} from 'react'
import type {Settings} from '../api/types'
import type {Run} from '../pages/Devices'
import {api} from '../api/client'
import {PhaseSettings} from '../components/PhaseSettings'
import {mergeDraft} from './mergeDraft'
export function ConnectionForm({settings,save,run,connections,section,onSaved}:{onSaved?:()=>void;section:'installation'|'home_assistant'|'peugeot'|'ariston';settings:Settings;save:(value:Settings)=>Promise<void>;run:Run;connections:Record<string,boolean>}) {
  const [base,setBase]=useState(()=>structuredClone(settings)),[value,set]=useState(()=>structuredClone(settings))
  const merged=()=>mergeDraft(settings,base,value)
  const [haToken,setHaToken]=useState(''),[password,setPassword]=useState(''),[refresh,setRefresh]=useState('')
  const [callback,setCallback]=useState(''),[authUrl,setAuthUrl]=useState('')
  return <><p className="subtitle">Les accès sont chiffrés sur le serveur. Les champs secrets restent vides après enregistrement.</p>
    {section==='installation'&&<section className="connection-form"><h2>Installation</h2><form onSubmit={e=>{e.preventDefault();run(async()=>{const next=merged();await save(next);setBase(structuredClone(next));set(structuredClone(next));onSaved?.()},'Réglages enregistrés')}}><div className="form-grid">
      <label>Limite totale de consommation (W)<input required type="number" min="1" value={value.site_limit_w??''} onChange={e=>set({...value,site_limit_w:e.target.value?Number(e.target.value):null})}/></label>
      <label>Marge d’injection solaire (W)<input required type="number" min="0" value={value.export_margin_w} onChange={e=>set({...value,export_margin_w:Number(e.target.value)})}/></label>
      <label className="check"><input type="checkbox" checked={value.phase_control_enabled||false} onChange={e=>set({...value,phase_control_enabled:e.target.checked})}/>Limiter la recharge par phase</label>
      <label>Marge de courant par phase (A)<input type="number" min="0" max="100" step=".1" value={value.phase_margin_a??1} onChange={e=>set({...value,phase_margin_a:Number(e.target.value)})}/></label>
      <label>Coût du solaire autoconsommé (€/kWh)<input type="number" min="0" max="100" step=".0001" value={value.solar_price_per_kwh??0} onChange={e=>set({...value,solar_price_per_kwh:Number(e.target.value)})}/></label>
      <label>Âge maximal des mesures électriques (s)<input type="number" min="5" max="3600" required value={value.sample_max_age_s} onChange={e=>set({...value,sample_max_age_s:Number(e.target.value)})}/></label>
      <label>Fuseau horaire<input required value={value.timezone} onChange={e=>set({...value,timezone:e.target.value})}/></label></div><button className="primary">Enregistrer les réglages</button></form>
      <p className="hint">La limite totale et les limites par phase se cumulent. Configurez les capteurs et la phase utilisée par la borne avant d’activer la limitation. Celle-ci nécessite le courant réel de recharge OCPP et ne remplace pas les protections du tableau.</p></section>}
    {section==='home_assistant'&&<section className="connection-form"><div className="section-title"><h2>Home Assistant · mesures</h2><span className={'badge '+(connections.home_assistant?'green':'neutral')}>{connections.home_assistant?'Accès enregistré':'À connecter'}</span></div>
      <div className="form-grid"><label>Adresse Home Assistant<input type="url" placeholder="https://homeassistant.exemple.fr" value={value.home_assistant.url} onChange={e=>set({...value,home_assistant:{...value.home_assistant,url:e.target.value}})}/></label>
        <label>Jeton longue durée<input type="password" autoComplete="new-password" placeholder={connections.home_assistant?'Accès conservé si vide':''} value={haToken} onChange={e=>setHaToken(e.target.value)}/></label>
        <label>Entité puissance réseau signée<input placeholder="sensor.puissance_reseau" value={value.home_assistant.grid_entity} onChange={e=>set({...value,home_assistant:{...value.home_assistant,grid_entity:e.target.value}})}/></label>
        <label>Entité production solaire<input placeholder="sensor.production_solaire" value={value.home_assistant.solar_entity} onChange={e=>set({...value,home_assistant:{...value.home_assistant,solar_entity:e.target.value}})}/></label>
        <label>Entité prix actuel du réseau (€/kWh)<input placeholder="sensor.prix_electricite_actuel" value={value.home_assistant.price_entity||''} onChange={e=>set({...value,home_assistant:{...value.home_assistant,price_entity:e.target.value.trim()}})}/></label>
        <label>Entité consommation totale de la maison (facultatif)<input placeholder="sensor.consommation_totale_maison" value={value.home_assistant.house_entity||''} onChange={e=>set({...value,home_assistant:{...value.home_assistant,house_entity:e.target.value.trim()}})}/></label>
        {value.devices.map(d=><label key={d.id}>Puissance mesurée · {d.name}<input placeholder="sensor.puissance_appareil" value={value.home_assistant.device_power_entities[d.id]||''} onChange={e=>set({...value,home_assistant:{...value.home_assistant,device_power_entities:{...value.home_assistant.device_power_entities,[d.id]:e.target.value}}})}/></label>)}</div>
      <p className="hint">La consommation maison inclut la voiture et le ballon, sur toutes les phases. Ce capteur facultatif doit mesurer la consommation totale en W ou kW. Si le champ reste vide, la carte calcule réseau + solaire. Avec un capteur configuré indisponible, elle affiche « — ».</p>
      <PhaseSettings value={value.home_assistant} onChange={home_assistant=>set({...value,home_assistant})}/>
      <label className="check"><input type="checkbox" checked={value.home_assistant.invert_grid} onChange={e=>set({...value,home_assistant:{...value.home_assistant,invert_grid:e.target.checked}})}/>Inverser le signe réseau (la convention attendue est import positif, export négatif)</label>
      <div className="actions"><button onClick={()=>run(()=>api('/connections/home-assistant/test','POST',{config:merged().home_assistant,token:haToken||null}),'Connexion HA vérifiée')}>Tester Home Assistant</button>
        <button className="primary" onClick={()=>run(async()=>{await api('/connections/home-assistant','PUT',{config:merged().home_assistant,token:haToken||null});setHaToken('');onSaved?.()},'Connexion HA enregistrée')}>Enregistrer Home Assistant</button></div>
      <p className="hint">Les capteurs doivent fournir des W ou kW et être disponibles lors des vérifications Home Assistant. La remontée des états de cette application vers HA arrivera dans une étape suivante.</p></section>}
    {section==='peugeot'&&<section className="connection-form"><div className="section-title"><h2>Peugeot · batterie et autonomie</h2><span className={'badge '+(connections.peugeot?'green':'neutral')}>{connections.peugeot?'Accès enregistré':'À connecter'}</span></div>
      <div className="form-grid"><label>Compte Peugeot (repère)<input autoComplete="username" value={value.peugeot.username} onChange={e=>set({...value,peugeot:{...value.peugeot,username:e.target.value}})}/></label>
        <label>Pays<input value={value.peugeot.country} onChange={e=>set({...value,peugeot:{...value.peugeot,country:e.target.value}})}/></label>
        <label>Intervalle de lecture (s)<input type="number" min="300" value={value.peugeot.poll_interval_s} onChange={e=>set({...value,peugeot:{...value.peugeot,poll_interval_s:Number(e.target.value)}})}/></label>
        </div>
      <div className="actions"><button className="primary" onClick={()=>run(async()=>{await api('/connections/peugeot','PUT',{config:merged().peugeot});const result=await api<{url:string}>('/connections/peugeot/auth','POST');setAuthUrl(result.url)})}>Connecter mon compte Peugeot</button>
        <button onClick={()=>run(()=>api('/connections/peugeot/test','POST'),'Accès Peugeot vérifié')}>Tester l’accès enregistré</button></div>
      {authUrl&&<div className="arm-box"><p><a href={authUrl} target="_blank" rel="noreferrer">Ouvrir la connexion sécurisée Peugeot ↗</a></p><label>Adresse de retour mymap://<input type="password" value={callback} onChange={e=>setCallback(e.target.value)}/></label>
        <button onClick={()=>run(async()=>{await api('/connections/peugeot/complete','POST',{response:callback});setCallback('');setAuthUrl('')},'Compte Peugeot connecté')}>Terminer la connexion</button></div>}
      <details><summary>Import avancé d’un accès compatible</summary><label>Jeton de renouvellement<input type="password" autoComplete="new-password" value={refresh} onChange={e=>setRefresh(e.target.value)}/></label>
        <button onClick={()=>run(async()=>{await api('/connections/peugeot','PUT',{config:merged().peugeot,refresh_token:refresh||null});setRefresh('')},'Accès Peugeot enregistré')}>Enregistrer l’accès Peugeot</button></details>
      <p className="hint">Le VIN se renseigne dans Réglages, sur la carte du véhicule. La compatibilité du compte et la fraîcheur des données seront vérifiées lors de la mise en service.</p></section>}
    {section==='ariston'&&<section className="connection-form"><div className="section-title"><h2>Ariston · commande native du ballon</h2><span className={'badge '+(connections.ariston?'green':'neutral')}>{connections.ariston?'Accès enregistré':'À connecter'}</span></div>
      <div className="form-grid"><label>Compte Ariston<input autoComplete="username" value={value.ariston.username} onChange={e=>set({...value,ariston:{...value.ariston,username:e.target.value}})}/></label>
        <label>Mot de passe Ariston<input type="password" autoComplete="new-password" value={password} placeholder={connections.ariston?'Conservé si vide':''} onChange={e=>setPassword(e.target.value)}/></label>
        <label>Intervalle Ariston (s)<input type="number" min="60" value={value.ariston.poll_interval_s} onChange={e=>set({...value,ariston:{...value.ariston,poll_interval_s:Number(e.target.value)}})}/></label></div>
      <button className="primary" onClick={()=>run(async()=>{await api('/connections/ariston','PUT',{config:merged().ariston,password:password||null});setPassword('');onSaved?.()},'Accès Ariston enregistré')}>Enregistrer Ariston</button>
      <p className="hint">Le test et l’activation se font dans Réglages, sur la carte du ballon. Une compatibilité non vérifiée laisse le ballon en observation.</p></section>}
  </>
}
