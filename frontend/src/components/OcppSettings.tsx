import {useEffect,useState} from 'react'
import {api} from '../api/client'
import type {Device} from '../api/types'
import type {Run} from '../pages/Devices'

export interface OcppConnection {station_id:string;credentials_saved:boolean;connected:boolean;last_error:string|null;firmware?:string|null}
const reasons:Record<string,string>={heartbeat_timeout:'Délai de communication dépassé : reconnexion attendue.',
  authentication_refused:'Authentification refusée : vérifier l’identité et le mot de passe de la borne.',
  secret_unavailable:'Accès enregistré indisponible sur le serveur.',duplicate_connection:'Une connexion de cette borne est déjà active.',
  protocol_required:'La borne doit utiliser le sous-protocole OCPP 1.6.',connection_closed:'Connexion fermée : reconnexion attendue.'}

export function OcppSettings({devices,run}:{devices:Device[];run:Run}) {
  const identities=[...new Set(devices.filter(d=>d.kind==='charger'&&d.charge_point_id).map(d=>d.charge_point_id))]
  const [station,setStation]=useState(identities[0]||''),[secret,setSecret]=useState('')
  const [rows,setRows]=useState<OcppConnection[]>([]),[readError,setReadError]=useState(false)
  const refresh=async()=>{const data=await api<{stations:OcppConnection[]}>('/connections/ocpp');setRows(data.stations||[]);setReadError(false)}
  useEffect(()=>{void refresh().catch(()=>setReadError(true))},[])
  const selected=rows.find(row=>row.station_id===station)
  return <section className="panel"><div className="section-title"><h2>Authentification OCPP</h2>
    <span className={'badge '+(selected?.credentials_saved?'green':'neutral')}>{selected?.credentials_saved?'Accès OCPP enregistrés':'À configurer'}</span></div>
    <p className="hint">Dans l’application Wallbox, saisir cette URL de base et l’identifiant séparément. La borne ajoute elle-même l’identifiant à l’URL. Le sous-protocole attendu est ocpp1.6.</p>
    <label className="ocpp-server-url">URL du serveur OCPP<input readOnly value={window.location.origin.replace(/^http/,'ws')+'/ocpp/'} onFocus={e=>e.target.select()}/></label>
    <div className="form-grid"><label>Identifiant OCPP enregistré<select value={station} onChange={e=>{setStation(e.target.value);setSecret('')}}>
      {!identities.length&&<option value="">Ajouter une borne dans Réglages</option>}{identities.map(id=><option key={id} value={id}>{id}</option>)}</select></label>
      <label>Mot de passe OCPP<input type="password" autoComplete="new-password" value={secret} placeholder={selected?.credentials_saved?'Conservé si vide':''} onChange={e=>setSecret(e.target.value)}/></label></div>
    {selected&&<p className="hint">{selected.connected?'Borne connectée':'Borne hors connexion'}{selected.firmware?' · Firmware '+selected.firmware:''}</p>}
    {selected?.last_error&&<p className="hint">{reasons[selected.last_error]||'Connexion à vérifier.'}</p>}
    {readError&&<p className="hint">Lecture des accès enregistrés indisponible.</p>}
    <button disabled={!station||(!selected?.credentials_saved&&secret.length<12)} onClick={()=>run(async()=>{
      await api('/connections/ocpp/'+encodeURIComponent(station),'PUT',{password:secret||null});setSecret('');await refresh()
    },'Accès OCPP enregistré')}>Enregistrer l’accès OCPP</button>
    <p className="hint">Un champ vide conserve le mot de passe déjà enregistré. Le serveur conserve les accès chiffrés après redémarrage.</p>
  </section>
}
