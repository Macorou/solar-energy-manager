import {useEffect,useState} from 'react'
import {api,date,watts} from './api/client'
import type {Settings,LiveState,EventRow} from './api/types'
import {Icon} from './components/Icon'
import {Overview} from './components/Overview'
import {Devices} from './pages/Devices'
import {Planning} from './pages/Planning'
import {SettingsPage} from './pages/Settings'
const navigation=[['overview','Vue d’ensemble','home'],['chargers','Voiture','car'],['water','Eau chaude','drop'],
  ['planning','Planning','calendar'],['history','Historique','chart'],['settings','Réglages','settings']]
export function App() {
  const [clock,setClock]=useState(()=>new Date())
  useEffect(()=>{const timer=setInterval(()=>setClock(new Date()),30000);return()=>clearInterval(timer)},[])
  const [settings,setSettings]=useState<Settings|null>(null),[state,setState]=useState<LiveState|null>(null)
  const [configured,setConfigured]=useState<boolean|null>(null),[auth,setAuth]=useState(false),[page,setPage]=useState('overview')
  const [message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [connections,setConnections]=useState<Record<string,boolean>>({}),[events,setEvents]=useState<EventRow[]>([])
  const [demo,setDemo]=useState(false),[surplus,setSurplus]=useState(3000),[demoResult,setDemoResult]=useState<{commands:{device_id:string;limit_w:number}[];reasons:Record<string,string>}|null>(null)
  const refresh=async()=>{const [s,c,l,e]=await Promise.all([api<Settings>('/settings'),api<Record<string,boolean>>('/connections'),api<LiveState>('/state'),api<EventRow[]>('/events')]);setSettings(s);setConnections(c);setState(l);setEvents(e)}
  useEffect(()=>{api<{configured:boolean}>('/setup/status').then(r=>{setConfigured(r.configured);if(r.configured)refresh().then(()=>setAuth(true)).catch(()=>setAuth(false))}).catch(()=>setError('Serveur inaccessible'))},[])
  useEffect(()=>{if(!auth)return;let active=true;const timer=setInterval(()=>{api<LiveState>('/state').then(r=>{if(active)setState(r)}).catch(()=>{if(active){setState(null);setError('Connexion au serveur interrompue')}})},3000);return()=>{active=false;clearInterval(timer)}},[auth])
  async function run(operation:()=>Promise<unknown>,success='') {
    setBusy(true);setError('');setMessage('')
    try {await operation();await refresh();setMessage(success)} catch(e){setError(e instanceof Error?e.message:'Opération impossible')}
    finally {setBusy(false)}
  }
  const save=async(value:Settings)=>{await api('/settings','PUT',value)}
  async function login(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();const data=new FormData(event.currentTarget)
    setBusy(true);setError('')
    try {await api(configured?'/auth/login':'/setup','POST',{username:data.get('username'),password:data.get('password'),...(!configured?{token:data.get('token')}:{})});await refresh();setConfigured(true);setAuth(true)}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  if(!auth||!settings)return <div className="login-page"><div className="login-intro"><div className="brand"><Icon name="sun" size={36}/><span>solar<span>energy manager</span></span></div><h1>Votre énergie,<br/>au bon moment.</h1><p>Le soleil, votre voiture et votre eau chaude.<br/>Un pilotage commun, chez vous.</p><div className="login-orbit"><Icon name="sun" size={76}/><Icon name="home" size={120}/><Icon name="car" size={76}/></div></div>
    <main className="login-form"><span className="eyebrow">VOTRE INSTALLATION</span><h2>{configured===false?'Première connexion':'Bienvenue chez vous'}</h2><p>{configured===false?'Créez votre compte administrateur.':'Connectez-vous pour suivre et piloter votre énergie.'}</p>
      {error&&<div role="alert" className="alert error">{error}</div>}{configured===null?<p>Connexion au service…</p>:<form onSubmit={login}>
        {!configured&&<label>Code de première installation<input name="token" type="password" required autoComplete="off"/><small>Disponible dans /data/bootstrap-token depuis la console Portainer.</small></label>}
        <label>Identifiant<input name="username" required autoComplete="username" defaultValue="admin"/></label><label>Mot de passe<input name="password" type="password" minLength={configured?1:12} required autoComplete={configured?'current-password':'new-password'}/></label>
        <button className="primary" disabled={busy}>{configured?'Se connecter':'Créer mon compte'}</button></form>}<p className="hint">Application auto-hébergée · vos réglages restent sur votre serveur.</p></main></div>
  const title=page==='overview'?'Pilotage énergie':page==='chargers'?'Bornes et véhicules':page==='settings'?'Réglages et connexions':navigation.find(n=>n[0]===page)?.[1]
  function action(id:string,action:string){run(()=>api(`/devices/${id}/${action}`,'POST',action==='manual'?{duration_minutes:30}:undefined),'Demande enregistrée ; le résultat sera confirmé par les mesures.')}
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><Icon name="sun" size={31}/><span>solar<span>energy manager</span></span></div><div className="sidebar-label">VOTRE ÉNERGIE</div>
    <nav>{navigation.map(([id,label,icon])=><button key={id} className={page===id?'active':''} onClick={()=>{setPage(id);setError('');setMessage('')}}><Icon name={icon}/><span>{label}</span></button>)}</nav>
    <div className="sidebar-bottom"><span className="status-dot"/><span>Auto-hébergé · v0.1.8</span><button onClick={()=>run(async()=>{await api('/auth/logout','POST');setAuth(false)})}>Déconnexion</button></div></aside>
    <main className="main"><header className="dashboard-header"><div><div className="dashboard-title"><h1>{title}</h1>{page==='overview'&&<span className="header-tag">PILOTAGE LOCAL</span>}</div>
      <div className="dashboard-context"><span className="solar-context"><Icon name="sun" size={16}/>Solaire <b>{watts(state?.solar?.usable?state.solar.value:null)}</b></span>
        {state&&<span className={'tariff-context '+(state.off_peak?'off-peak':'')}>{state.off_peak?'Heures creuses':'Heures pleines'}</span>}
        {page==='overview'&&<button className="text-button" onClick={()=>{setDemo(!demo);setDemoResult(null)}}>{demo?'Fermer la démonstration':'Explorer une simulation'}</button>}</div></div>
      <div className="dashboard-clock"><Icon name="sun" size={26}/><time dateTime={clock.toISOString()}><span>{clock.toLocaleDateString('fr-FR',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:settings.timezone})}</span><strong>{clock.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:settings.timezone})}</strong></time></div></header>
      {error&&<div role="alert" className="alert error"><strong>Action à vérifier</strong><span>{error}</span><button onClick={()=>setError('')} aria-label="Fermer l’erreur">×</button></div>}
      {message&&<div role="status" className="alert success">{message}</div>}{busy&&<div className="busy" role="status">En cours…</div>}
      <fieldset disabled={busy} className="page-content">
      {page==='overview'&&<>
        {demo&&<section className="panel demo"><span className="badge amber">SIMULATION · DONNÉES FICTIVES</span><h2>Et si le soleil produisait davantage ?</h2><p>Ce calcul isolé n’envoie aucune commande et ne modifie aucun réglage.</p><label>Surplus simulé : {watts(surplus)}<input type="range" min="0" max="8000" step="100" value={surplus} onChange={e=>setSurplus(Number(e.target.value))}/></label>
          <button onClick={()=>run(async()=>setDemoResult(await api('/simulation','POST',{surplus_w:surplus})))}>Calculer la répartition simulée</button>{demoResult&&<div className="simulation-result">{Object.entries(demoResult.reasons).map(([id,reason])=><p key={id}><strong>{id==='demo-car'?'Voiture':'Ballon'} : {watts(demoResult.commands.find(c=>c.device_id===id)?.limit_w||0)}</strong> · {reason}</p>)}</div>}</section>}
        <Overview settings={settings} state={state} connections={connections} onAction={action} onNavigate={setPage}/></>}
      {page==='chargers'&&<Devices settings={settings} save={save} run={run} kind="charger"/>}
      {page==='water'&&<Devices settings={settings} save={save} run={run} kind="water_heater"/>}
      {page==='planning'&&<Planning settings={settings} save={save} run={run}/>}
      {page==='settings'&&<SettingsPage settings={settings} save={save} run={run} connections={connections}/>}
      {page==='history'&&<section className="panel"><div className="section-title"><h2>Journal des décisions et commandes</h2><button onClick={()=>run(async()=>setEvents(await api('/events')))}>Actualiser</button></div>{events.length?events.map(e=><div className="event-row" key={e.id}><span className="hint">{date(e.at)}</span><div><strong>{eventName(e.kind)}</strong><p>{e.device_id&&<b>{settings.devices.find(d=>d.id===e.device_id)?.name||e.device_id} · </b>}{e.details.reason||e.details.action||''}</p></div></div>):<p className="hint">Aucun événement. Les commandes et leurs confirmations apparaîtront ici.</p>}</section>}
      </fieldset><footer>Solar Energy Manager <span>Décisions locales · connexions cloud indiquées par appareil</span></footer>
    </main></div>
}
function eventName(kind:string){return ({command_accepted:'Commande acceptée',command_unknown:'Résultat inconnu',command_observed:'Effet observé',manual:'Commande manuelle',armed:'Pilotage activé',schedule_incomplete:'Échéance non atteinte ou non vérifiable',schedule_complete:'Objectif atteint à l’échéance'} as Record<string,string>)[kind]||kind}
