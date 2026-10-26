import {useEffect,useState} from 'react'
import {api,date,watts} from './api/client'
import type {Settings,LiveState,EventRow} from './api/types'
import {Icon} from './components/Icon'
import {PowerFlow} from './components/PowerFlow'
import {DeviceCard} from './components/DeviceCard'
import {Devices} from './pages/Devices'
import {Planning} from './pages/Planning'
import {SettingsPage} from './pages/Settings'
const navigation=[['overview','Vue d’ensemble','home'],['chargers','Bornes et véhicules','car'],['water','Eau chaude','drop'],
  ['planning','Planning','calendar'],['history','Historique','history'],['settings','Réglages et connexions','settings']]
export function App() {
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
  const title=navigation.find(n=>n[0]===page)?.[1]
  function action(id:string,action:string){run(()=>api(`/devices/${id}/${action}`,'POST',action==='manual'?{duration_minutes:30}:undefined),'Demande enregistrée ; le résultat sera confirmé par les mesures.')}
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><Icon name="sun" size={31}/><span>solar<span>energy manager</span></span></div><div className="sidebar-label">VOTRE ÉNERGIE</div>
    <nav>{navigation.map(([id,label,icon])=><button key={id} className={page===id?'active':''} onClick={()=>{setPage(id);setError('');setMessage('')}}><Icon name={icon}/><span>{label}</span></button>)}</nav>
    <div className="sidebar-bottom"><span className="status-dot"/><span>Auto-hébergé · v0.1.0</span><button onClick={()=>run(async()=>{await api('/auth/logout','POST');setAuth(false)})}>Déconnexion</button></div></aside>
    <main className="main"><header><div><span className="eyebrow">SOLAR ENERGY MANAGER</span><h1>{title}</h1></div><div className="header-status"><span className={'badge '+(state?.off_peak?'green':'neutral')}>{state?.off_peak?'Heures creuses':'Heures pleines'}</span><span className="hint">{date(state?.at)}</span></div></header>
      {error&&<div role="alert" className="alert error"><strong>Action à vérifier</strong><span>{error}</span><button onClick={()=>setError('')} aria-label="Fermer l’erreur">×</button></div>}
      {message&&<div role="status" className="alert success">{message}</div>}{busy&&<div className="busy" role="status">En cours…</div>}
      <fieldset disabled={busy} className="page-content">
      {page==='overview'&&<><div className="welcome-line"><p className="subtitle">Chaque watt solaire trouve sa place.</p><button onClick={()=>{setDemo(!demo);setDemoResult(null)}}>{demo?'Fermer la démonstration':'Explorer une simulation'}</button></div>
        {demo&&<section className="panel demo"><span className="badge amber">SIMULATION · DONNÉES FICTIVES</span><h2>Et si le soleil produisait davantage ?</h2><p>Ce calcul isolé n’envoie aucune commande et ne modifie aucun réglage.</p><label>Surplus simulé : {watts(surplus)}<input type="range" min="0" max="8000" step="100" value={surplus} onChange={e=>setSurplus(Number(e.target.value))}/></label>
          <button onClick={()=>run(async()=>setDemoResult(await api('/simulation','POST',{surplus_w:surplus})))}>Calculer la répartition simulée</button>{demoResult&&<div className="simulation-result">{Object.entries(demoResult.reasons).map(([id,reason])=><p key={id}><strong>{id==='demo-car'?'Voiture':'Ballon'} : {watts(demoResult.commands.find(c=>c.device_id===id)?.limit_w||0)}</strong> · {reason}</p>)}</div>}</section>}
        <div className="stat-grid">{[['sun','Production solaire',state?.solar?.usable?state.solar.value:null],['grid','Réseau signé',state?.grid?.usable?state.grid.value:null],['car','Bornes de recharge',sumPower(state,'charger')],['drop','Eau chaude',sumPower(state,'water_heater')]].map(([icon,label,value])=><div className="stat-card" key={String(label)}><span className={'stat-icon '+icon}><Icon name={String(icon)} size={30}/></span><div><span>{label}</span><strong>{watts(value as number|null)}</strong></div></div>)}</div>
        {!settings.devices.length&&<div className="notice onboarding"><Icon name="link" size={28}/><div><strong>Votre installation est prête à être configurée</strong><p>Renseignez les mesures et les appareils. Le pilotage reste désactivé pendant la configuration.</p></div><button className="primary" onClick={()=>setPage('settings')}>Configurer les connexions</button></div>}
        <PowerFlow state={state}/><div className="device-grid">{state?.devices.map(d=><DeviceCard key={d.config.id} device={d} telemetry={state.vehicles[d.config.vehicle_id]} onAction={action}/>)}</div>
        {state&&Object.keys(state.errors).length>0&&<section className="panel"><h2>Points à vérifier</h2>{Object.entries(state.errors).map(([id,text])=><p key={id}>{settings.devices.find(d=>d.id===id)?.name||id} : {text}</p>)}</section>}
        <div className="overview-bottom"><section className="panel"><div className="section-title"><h2>Vos prochains rendez-vous</h2><button onClick={()=>setPage('planning')}>Voir le planning →</button></div>{settings.schedules.length?settings.schedules.map(p=><div className="list-row" key={p.id}><span>{p.name}</span><strong>{p.target_soc} % · {p.deadline}</strong></div>):<p className="hint">Aucun programme enregistré. Le solaire reste disponible selon le mode de chaque appareil.</p>}</section>
          <section className="panel connection-card"><Icon name="home" size={30}/><h2>Home Assistant</h2><p>{connections.home_assistant?'Accès aux mesures enregistré':'Connectez les mesures de votre maison'}</p><span className="hint">Intégration de retour et EDF Tempo prévus après la base.</span></section></div></>}
      {page==='chargers'&&<Devices settings={settings} save={save} run={run} kind="charger"/>}
      {page==='water'&&<Devices settings={settings} save={save} run={run} kind="water_heater"/>}
      {page==='planning'&&<Planning settings={settings} save={save} run={run}/>}
      {page==='settings'&&<SettingsPage settings={settings} save={save} run={run} connections={connections}/>}
      {page==='history'&&<section className="panel"><div className="section-title"><h2>Journal des décisions et commandes</h2><button onClick={()=>run(async()=>setEvents(await api('/events')))}>Actualiser</button></div>{events.length?events.map(e=><div className="event-row" key={e.id}><span className="hint">{date(e.at)}</span><div><strong>{eventName(e.kind)}</strong><p>{e.device_id&&<b>{settings.devices.find(d=>d.id===e.device_id)?.name||e.device_id} · </b>}{e.details.reason||e.details.action||''}</p></div></div>):<p className="hint">Aucun événement. Les commandes et leurs confirmations apparaîtront ici.</p>}</section>}
      </fieldset><footer>Solar Energy Manager <span>Décisions locales · connexions cloud indiquées par appareil</span></footer>
    </main></div>
}
function sumPower(state:LiveState|null,kind:string) {const devices=state?.devices.filter(d=>d.config.kind===kind);return !devices?.length||devices.some(d=>d.state.observed_power?.value==null)?null:devices.reduce((sum,d)=>sum+(d.state.observed_power?.value||0),0)}
function eventName(kind:string){return ({command_accepted:'Commande acceptée',command_unknown:'Résultat inconnu',command_observed:'Effet observé',manual:'Commande manuelle',armed:'Pilotage activé',schedule_incomplete:'Échéance non atteinte ou non vérifiable',schedule_complete:'Objectif atteint à l’échéance'} as Record<string,string>)[kind]||kind}
