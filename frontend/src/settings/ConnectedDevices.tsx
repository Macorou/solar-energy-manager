import {useEffect,useState} from 'react'
import type {ConnectedDevice} from '../api/types'
import type {Run} from '../pages/Devices'
import {api} from '../api/client'

const when=(value:string|null,timezone:string)=>value&&new Date(value).toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'short',timeZone:timezone})

export function ConnectedDevices({run,timezone}:{run:Run;timezone:string}){
  const [devices,setDevices]=useState<ConnectedDevice[]|null>(null),[error,setError]=useState('')
  const load=async()=>{try{setDevices(await api<ConnectedDevice[]>('/auth/sessions'));setError('')}catch(e){setError(e instanceof Error?e.message:'Liste des appareils indisponible')}}
  useEffect(()=>{load()},[])
  const others=devices?.filter(d=>!d.current).length??0
  return <section className="settings-installation connected-devices">
    <div className="section-title"><div><h2>Appareils connectés</h2><p className="hint">Un appareil reste connecté 30 jours après sa dernière utilisation. Déconnectez ceux que vous ne reconnaissez pas ou n’utilisez plus.</p></div>
      {others>0&&<button type="button" onClick={()=>run(async()=>{await api('/auth/sessions/revoke-others','POST');await load()},'Les autres appareils sont déconnectés.')}>Déconnecter les autres appareils</button>}</div>
    {error&&<p className="alert error" role="alert">{error}</p>}
    {!devices?!error&&<p className="hint">Chargement…</p>:<ul className="device-sessions">{devices.map(d=><li key={d.id}>
      <div><strong>{d.device}{d.current&&<span className="badge green">Cet appareil</span>}</strong>
        <span>{when(d.created_at,timezone)?'Connecté le '+when(d.created_at,timezone):'Connecté avant la version 0.1.32'} · {when(d.last_seen_at,timezone)?'dernière activité le '+when(d.last_seen_at,timezone):'pas encore revu'}{d.ip&&' · '+d.ip}</span></div>
      {!d.current&&<button type="button" aria-label={'Déconnecter '+d.device+(d.ip?' ('+d.ip+')':'')} onClick={()=>run(async()=>{await api('/auth/sessions/'+encodeURIComponent(d.id),'DELETE');await load()},d.device+' est déconnecté.')}>Déconnecter</button>}</li>)}</ul>}
  </section>
}
