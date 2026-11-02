import type {Device,Vehicle} from '../api/types'
import {CloudSettingsForm} from './Editors'
export const deviceModes={off:'Arrêt',solar:'Solaire',planned:'Planifié',off_peak_solar:'HC/HP + solaire',manual:'Manuel'}
export function DeviceFields({editing,setEditing,vehicles}:{editing:Device;setEditing:(value:Device)=>void;vehicles:Vehicle[]}){const kind=editing.kind,modes=deviceModes;return <>
        <div className="form-grid"><label>Nom<input required value={editing.name} onChange={e=>setEditing({...editing,name:e.target.value})}/></label>
          <label>Mode<select value={editing.mode} onChange={e=>setEditing({...editing,mode:e.target.value as Device['mode']})}>{Object.entries(modes).filter(([m])=>m!=='manual'&&(kind==='charger'?m!=='off_peak_solar':m!=='planned')).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
          <label>Priorité (1 = premier)<input required type="number" min="1" max="100" value={editing.priority} onChange={e=>setEditing({...editing,priority:Number(e.target.value)})}/></label>
          <label>Puissance minimale (W)<input required type="number" min="1" value={editing.min_power_w} onChange={e=>setEditing({...editing,min_power_w:Number(e.target.value)})}/></label>
          <label>Puissance maximale (W)<input required type="number" min="1" value={editing.max_power_w} onChange={e=>setEditing({...editing,max_power_w:Number(e.target.value)})}/></label>
          <label>Délai de confirmation physique (s)<input required type="number" min="30" max="3600" value={editing.confirmation_timeout_s} onChange={e=>setEditing({...editing,confirmation_timeout_s:Number(e.target.value)})}/></label>
          {kind==='charger'?<><label>Identifiant de la borne OCPP<input required value={editing.charge_point_id} onChange={e=>setEditing({...editing,charge_point_id:e.target.value})}/></label>
            <label>Compatibilité de la borne<select value={editing.ocpp_profile||'auto'} onChange={e=>setEditing({...editing,ocpp_profile:e.target.value as Device['ocpp_profile']})}><option value="auto">Automatique</option><option value="wallbox">Wallbox</option><option value="wallbox_fw5">Wallbox · firmware 5.x</option><option value="standard">OCPP standard</option></select></label>
            <label>Numéro de connecteur<input type="number" min="1" required value={editing.connector_id} onChange={e=>setEditing({...editing,connector_id:Number(e.target.value)})}/></label>
            <label>Véhicule associé<select required value={editing.vehicle_id} onChange={e=>setEditing({...editing,vehicle_id:e.target.value})}><option value="">Choisir</option>{vehicles.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label>
            <label>Phases<select value={editing.phases} onChange={e=>setEditing({...editing,phases:Number(e.target.value) as 1|3,grid_phases:[]})}><option value="1">Monophasé</option><option value="3">Triphasé</option></select></label>
            <label>Phase réseau utilisée<select value={(editing.grid_phases||[]).join(',')} onChange={e=>setEditing({...editing,grid_phases:e.target.value?e.target.value.split(',') as Device['grid_phases']:[]})}>
              <option value="">À renseigner pour la limitation par phase</option>{editing.phases===1?['L1','L2','L3'].map(p=><option key={p} value={p}>{p}</option>):<><option value="L1,L2,L3">L1, L2, L3</option><option value="L2,L3,L1">L2, L3, L1</option><option value="L3,L1,L2">L3, L1, L2</option></>}</select></label>
            <label>Courant minimal (A)<input required type="number" min="6" value={editing.min_current_a} onChange={e=>setEditing({...editing,min_current_a:Number(e.target.value)})}/></label>
            <label>Courant maximal (A)<input required type="number" min="6" max="80" value={editing.max_current_a} onChange={e=>setEditing({...editing,max_current_a:Number(e.target.value)})}/></label>
            <label>Objectif habituel (%)<input type="number" min="1" max="100" required value={editing.default_soc_target} onChange={e=>setEditing({...editing,default_soc_target:Number(e.target.value)})}/></label>
            <label>Objectif sur surplus solaire (%)<input type="number" min="1" max="100" placeholder="Aucun" value={editing.solar_target??''} onChange={e=>setEditing({...editing,solar_target:e.target.value===''?null:Number(e.target.value)})}/></label></>:
            <><label>Identifiant passerelle Ariston<input required value={editing.gateway_id} onChange={e=>setEditing({...editing,gateway_id:e.target.value})}/></label>
              <label>Consigne sur le réseau (°C)<input type="number" required value={editing.target??55} onChange={e=>setEditing({...editing,target:Number(e.target.value)})}/></label>
              <label>Consigne sur surplus solaire (°C)<input type="number" min="0" max="100" required value={editing.solar_target??editing.target??55} onChange={e=>setEditing({...editing,solar_target:Number(e.target.value)})}/></label></>}
        </div>
        {kind==='water_heater'&&<p className="hint">Le surplus solaire peut chauffer au-delà de la consigne réseau. Les deux températures doivent respecter les limites natives du ballon. Le mode manuel utilise la consigne réseau.</p>}
        {kind==='charger'&&<p className="hint">Au-delà de l’objectif du programme ou de l’objectif habituel, seul le surplus solaire charge la voiture, jusqu’à l’objectif sur surplus. Vide : la charge s’arrête à l’objectif. Le mode manuel n’est pas concerné.</p>}
        {kind==='charger'&&<label className="check"><input type="checkbox" checked={editing.allow_insecure_identity} onChange={e=>setEditing({...editing,allow_insecure_identity:e.target.checked})}/>Autoriser l’identité OCPP sans mot de passe sur le réseau local de confiance</label>}
        <CloudSettingsForm value={editing.cloud} onChange={cloud=>setEditing({...editing,cloud})}/>
  </>
}
