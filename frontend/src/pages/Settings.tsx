import {useEffect,useId,useRef,useState,type ReactNode} from 'react'
import type {Device,LiveDevice,LiveState,Sample,Settings,Vehicle} from '../api/types'
import type {Run} from './Devices'
import {api,date,watts} from '../api/client'
import {createId} from '../api/id'
import {Icon} from '../components/Icon'
import {OcppSettings,type OcppConnection} from '../components/OcppSettings'
import {housePower} from '../components/dashboard'
import {vehicleStatus} from '../components/ChargeSession'
import {ConnectionForm} from '../settings/ConnectionForm'
import {DeviceEditor,newDevice,VehicleEditor} from '../settings/AssetEditor'
import {SettingsDialog} from '../settings/SettingsDialog'
import {SourceEditor,type SourceKind} from '../settings/SourceEditor'
import {DeviceControls} from '../settings/DeviceControls'

type Editor={kind:'device';value:Device}|{kind:'vehicle';value:Vehicle}|{kind:'source';source:SourceKind}|{kind:'connection';name:'home_assistant'|'peugeot'|'ariston'|'ocpp'|'limits'}|{kind:'add'}
const sources:Record<SourceKind,string>={grid:'Compteur réseau',solar:'Production solaire',house:'Consommation maison',price:'Prix du réseau'}
const number=(n:number|null|undefined,digits=1)=>n==null||!Number.isFinite(n)?'—':n.toLocaleString('fr-FR',{maximumFractionDigits:digits})
function sampleValue(s:Sample|null|undefined,maxAge=30):number|null{
  if(s?.value==null||!Number.isFinite(s.value)||s.usable===false)return null
  if(s.usable===true)return s.value
  const at=Date.parse(s.checked_at||s.received_at||s.measured_at||'')
  return s.quality==='fresh'&&Number.isFinite(at)&&Math.abs(Date.now()-at)<=maxAge*1000?s.value:null
}
function Row({label,value}:{label:string;value:ReactNode}){return <div className="settings-metric-row"><span>{label}</span><strong>{value}</strong></div>}
function Card({name,subtitle,icon,onConfigure,children,note}:{name:string;subtitle:string;icon:string;onConfigure:()=>void;children:ReactNode;note?:ReactNode}){
  return <article className="settings-card" aria-label={name}><div className="settings-card-head"><span className="settings-card-icon"><Icon name={icon} size={20}/></span><div><h3>{name}</h3><p>{subtitle}</p></div>
    <button type="button" className="icon-button" aria-label={'Configurer '+name} onClick={onConfigure}><Icon name="sliders" size={19}/></button></div>
    <div className="settings-card-body">{children}</div>{note&&<div className="settings-card-note">{note}</div>}</article>
}
function Group({name,count,children}:{name:string;count:string;children:ReactNode}){return <section className="settings-group"><div className="settings-group-heading"><h2>{name}</h2><span>{count}</span></div><div className="settings-grid">{children}</div></section>}
function AddCard({label,onClick}:{label:string;onClick:()=>void}){return <button type="button" className="settings-add" aria-label={label} onClick={onClick}><Icon name="plus" size={23}/><strong>{label}</strong><span>Connecter et configurer un équipement</span></button>}
function PhaseTable({state,device,maxAge}:{state?:LiveState|null;device?:LiveDevice;maxAge:number}){
  return <table className="settings-phases"><caption className="sr-only">{device?'Courant de la borne':'Mesures réseau par phase'}</caption><thead><tr><th scope="col">{device?'Borne':'Réseau'}</th>{['L1','L2','L3'].map(p=><th scope="col" key={p}>{p}</th>)}</tr></thead>
    <tbody><tr><th scope="row">Courant</th>{['L1','L2','L3'].map(p=><td key={p}>{number(sampleValue(device?device.state.currents?.[p]:state?.phases?.[p]?.current,maxAge))} A</td>)}</tr>
    {!device&&<><tr><th scope="row">Tension</th>{['L1','L2','L3'].map(p=><td key={p}>{number(sampleValue(state?.phases?.[p]?.voltage,maxAge),0)} V</td>)}</tr><tr><th scope="row">Limite</th>{['L1','L2','L3'].map(p=><td key={p}>{state?.phases?.[p]?number(state.phases[p].limit_a)+' A':'—'}</td>)}</tr></>}
    </tbody></table>
}
export function SettingsPage({settings,state=null,save,run,connections}:{settings:Settings;state?:LiveState|null;save:(value:Settings)=>Promise<void>;run:Run;connections:Record<string,boolean>}){
  const [tab,setTab]=useState('equipment'),[editor,setEditor]=useState<Editor|null>(null)
  const [pending,setPending]=useState(false),[dialogError,setDialogError]=useState(''),[dialogMessage,setDialogMessage]=useState('')
  const closeAfterRun=useRef(false)
  const [ocpp,setOcpp]=useState<OcppConnection[]>([]),[ocppError,setOcppError]=useState(false)
  const tabsId=useId()
  useEffect(()=>{let active=true
    async function refresh(){try{const data=await api<{stations:OcppConnection[]}>('/connections/ocpp');if(active){setOcpp(data.stations||[]);setOcppError(false)}}catch{if(active){setOcpp([]);setOcppError(true)}}}
    void refresh();const timer=setInterval(()=>void refresh(),10000);return()=>{active=false;clearInterval(timer)}
  },[])
  function open(next:Editor){closeAfterRun.current=false;setDialogError('');setDialogMessage('');setEditor(next)}
  function close(){if(!pending)setEditor(null)}
  function saved(){closeAfterRun.current=true}
  const dialogRun:Run=async(operation,message='')=>{
    let succeeded=false
    setPending(true);setDialogError('');setDialogMessage('')
    try{await run(async()=>{try{await operation();succeeded=true}catch(e){setDialogError(e instanceof Error?e.message:'Opération impossible');throw e}},message)}
    finally{setPending(false);if(closeAfterRun.current){setEditor(null);closeAfterRun.current=false}else if(succeeded)setDialogMessage(message)}
  }
  const chargers=settings.devices.filter(d=>d.kind==='charger'),heaters=settings.devices.filter(d=>d.kind==='water_heater')
  const live=(id:string)=>state?.devices.find(d=>d.config.id===id)
  function asset(d:Device){const reading=live(d.id),car=d.kind==='charger',known=reading?.state.connected
    const temperature=known?reading.state.temperature:null,power=sampleValue(reading?.state.observed_power,settings.sample_max_age_s)
    return <Card key={d.id} name={d.name} subtitle={car?'OCPP · '+(d.phases===1?'monophasé':'triphasé'):'Ariston NET · chauffe-eau'} icon={car?'plug':'tank'} onConfigure={()=>open({kind:'device',value:d})} note={reading?.reason||'Aucune mesure reçue'}>
      <Row label="Statut" value={!reading?'Sans mesure':!known?'Hors connexion':car?vehicleStatus(reading):reading.state.observed_state==='on'&&power!=null&&power>20?'En chauffe':'En attente'}/>
      <strong className="settings-primary-value">{car?watts(sampleValue(reading?.state.observed_power,settings.sample_max_age_s)):number(temperature,0)+(temperature==null?'':' °C')}</strong>
      {car?<><Row label={reading?.charging?.active?'Énergie de la session':'Dernière recharge'} value={reading?.charging?number(reading.charging.energy_kwh,2)+' kWh':'—'}/><PhaseTable device={reading} state={null} maxAge={settings.sample_max_age_s}/></>:
        <><Row label="Puissance" value={watts(sampleValue(reading?.state.observed_power,settings.sample_max_age_s))}/><Row label="Consigne réseau" value={number(d.target,0)+' °C'}/><Row label="Consigne solaire" value={number(d.solar_target??d.target,0)+' °C'}/></>}
    </Card>
  }
  function source(kind:SourceKind){const n=kind==='house'?housePower(state):sampleValue(kind==='grid'?state?.grid:kind==='solar'?state?.solar:state?.price,settings.sample_max_age_s)
    return <Card key={kind} name={sources[kind]} subtitle={'Home Assistant · '+(kind==='grid'?'trois phases':kind==='house'?'logement complet':kind==='solar'?'production':'tarif actuel')} icon={kind==='grid'?'grid':kind==='solar'?'sun':kind==='house'?'home':'calendar'} onConfigure={()=>open({kind:'source',source:kind})}
      note={kind==='house'?'Consommation totale, voiture et ballon inclus':kind==='grid'?(settings.phase_control_enabled?'Limitation par phase active · marge '+number(settings.phase_margin_a)+' A':'Limitation par phase désactivée'):kind==='solar'?'Puissance de production mesurée':'Plages HC/HP définies dans Planning'}>
      <Row label={kind==='price'?'Période':'Lecture'} value={n==null?'Indisponible':kind==='price'?(state?.off_peak?'Heures creuses':'Heures pleines'):'Disponible'}/>
      <strong className="settings-primary-value">{kind==='price'?number(n,4)+(n==null?'':' €/kWh'):watts(n)}</strong>
      {kind==='grid'?<PhaseTable state={state} maxAge={settings.sample_max_age_s}/>:kind==='price'?<><Row label="Coût solaire configuré" value={number(settings.solar_price_per_kwh,4)+' €/kWh'}/><Row label="Prix effectif actuel" value={number(state?.effective_price_per_kwh,4)+(state?.effective_price_per_kwh==null?'':' €/kWh')}/></>:
        <Row label="Source" value={kind==='house'?settings.home_assistant.house_entity?'Capteur Home Assistant':'Calcul réseau + solaire':settings.home_assistant.solar_entity?'Capteur Home Assistant':'À configurer'}/>}
    </Card>
  }
  const title=editor?.kind==='device'?'Configurer '+editor.value.name:editor?.kind==='vehicle'?'Configurer '+editor.value.name:editor?.kind==='source'?'Configurer '+sources[editor.source]:editor?.kind==='connection'?'Configurer '+({home_assistant:'Home Assistant',peugeot:'Compte Peugeot',ariston:'Ariston NET',ocpp:'Serveur OCPP',limits:'Gestion de la charge'}[editor.name]):'Ajouter une intégration'
  return <div className="settings-workspace"><p className="settings-intro">Vos équipements et leurs connexions, au même endroit.</p>
    <div className="settings-tabs" role="tablist" aria-label="Sections des réglages">{[['equipment','Équipements','settings'],['integrations','Intégrations','plug'],['installation','Installation','sliders']].map(([id,label,icon])=><button type="button" role="tab" key={id} id={tabsId+id} aria-selected={tab===id} aria-controls={tabsId+'panel'} onClick={()=>setTab(id)}><Icon name={icon} size={18}/>{label}</button>)}</div>
    <div id={tabsId+'panel'} role="tabpanel" aria-labelledby={tabsId+tab}>
      {tab==='equipment'&&<><p className="settings-reading-status"><span className={'status-dot '+(!state?'unavailable':'')}/>{state?.at?'Mesures actualisées à '+new Date(state.at).toLocaleTimeString('fr-FR',{timeZone:settings.timezone}):'En attente de mesures'}</p>
        <Group name="Bornes et véhicules" count={(chargers.length+settings.vehicles.length)+' équipements'}>{chargers.map(asset)}
          {settings.vehicles.map(v=>{const telemetry=state?.vehicles[v.id],session=state?.devices.find(d=>d.config.vehicle_id===v.id)?.charging
            return <Card key={v.id} name={v.name} subtitle="Peugeot · batterie et autonomie" icon="car" onConfigure={()=>open({kind:'vehicle',value:v})} note={telemetry?.measured_at?'Relevé Peugeot : '+date(telemetry.measured_at):'Aucun relevé Peugeot'}>
              <Row label="Source" value={telemetry?'API Peugeot':'En attente de données'}/><strong className="settings-primary-value">{number(telemetry?.soc,0)}{telemetry?.soc==null?'':' %'}</strong>
              {telemetry&&!telemetry.fresh&&<span className="badge amber">Donnée ancienne</span>}
              <Row label="Autonomie" value={telemetry?.range_km==null?'—':number(telemetry.range_km,0)+' km'}/><Row label="Capacité configurée" value={v.capacity_kwh==null?'—':number(v.capacity_kwh)+' kWh'}/>
              {session?.soc_estimated&&<Row label="Batterie estimée" value={number(session.soc,0)+' %'}/>}</Card>})}
          <AddCard label="Ajouter une borne" onClick={()=>open({kind:'device',value:newDevice(settings,'charger')})}/><AddCard label="Ajouter un véhicule" onClick={()=>open({kind:'vehicle',value:{id:createId(),name:'Peugeot e-208',vin:'',capacity_kwh:null,efficiency:.85}})}/>
        </Group>
        <Group name="Eau chaude et consommation" count={heaters.length+1+' équipements'}>{heaters.map(asset)}{source('house')}<AddCard label="Ajouter un ballon" onClick={()=>open({kind:'device',value:newDevice(settings,'water_heater')})}/></Group>
        <Group name="Réseau, solaire et tarifs" count="3 sources">{source('grid')}{source('solar')}{source('price')}</Group>
      </>}
      {tab==='integrations'&&<><p className="settings-reading-status">Connexions utilisées par votre installation</p><Group name="Sources et comptes" count="3 intégrations">
        {(['home_assistant','peugeot','ariston'] as const).map(key=><Card key={key} name={{home_assistant:'Home Assistant',peugeot:'Compte Peugeot',ariston:'Ariston NET'}[key]} subtitle={{home_assistant:'Mesures et capteurs',peugeot:'Batterie du véhicule',ariston:'Commande native du ballon'}[key]} icon={key==='home_assistant'?'ha':key==='peugeot'?'car':'drop'} onConfigure={()=>open({kind:'connection',name:key})} note="Les champs secrets restent vides après enregistrement.">
          <span className={'badge '+(connections[key]?'green':'neutral')}>{connections[key]?'Accès enregistré':'À connecter'}</span>
          <Row label="Équipements associés" value={key==='peugeot'?settings.vehicles.length:key==='ariston'?heaters.length:settings.devices.length}/>
          <Row label="Intervalle de lecture" value={key==='home_assistant'?'Mesures locales':number(settings[key].poll_interval_s,0)+' s'}/></Card>)}
      </Group><Group name="Services locaux" count="2 services">
        <Card name="Serveur OCPP" subtitle="Connexion directe à la borne" icon="link" onConfigure={()=>open({kind:'connection',name:'ocpp'})} note={ocppError?'Lecture du service indisponible':'Authentification conservée sur le serveur'}>
          <span className={'badge '+(ocpp.some(s=>s.connected)?'green':'neutral')}>{ocppError?'État indisponible':ocpp.some(s=>s.connected)?'Connecté':ocpp.length?'Hors connexion':'Aucune borne'}</span>
          <Row label="Bornes connectées" value={ocppError?'—':ocpp.filter(s=>s.connected).length}/><Row label="Bornes configurées" value={chargers.length}/></Card>
        <Card name="Gestion de la charge" subtitle="Limites et budget de puissance" icon="grid" onConfigure={()=>open({kind:'connection',name:'limits'})} note="Pilotage local">
          <span className={'badge '+(settings.phase_control_enabled?'green':'neutral')}>{settings.phase_control_enabled?'Limitation active':'Limitation par phase désactivée'}</span><Row label="Limite totale" value={watts(settings.site_limit_w)}/><Row label="Marge par phase" value={number(settings.phase_margin_a)+' A'}/>
        </Card><AddCard label="Configurer une intégration" onClick={()=>open({kind:'add'})}/>
      </Group></>}
      {tab==='installation'&&<div className="settings-installation"><ConnectionForm section="installation" settings={settings} save={save} run={run} connections={connections}/></div>}
    </div>
    {editor&&<SettingsDialog key={editor.kind==='device'||editor.kind==='vehicle'?editor.value.id:editor.kind==='source'?editor.source:editor.kind==='connection'?editor.name:'add'} title={title} onClose={close} pending={pending} error={dialogError} message={dialogMessage}>
      {editor.kind==='source'&&<SourceEditor kind={editor.source} settings={settings} run={dialogRun} onSaved={saved}/>}
      {editor.kind==='device'&&<DeviceEditor initial={editor.value} settings={settings} save={save} run={dialogRun} onSaved={saved}/>}
      {editor.kind==='device'&&settings.devices.some(d=>d.id===editor.value.id)&&<DeviceControls device={settings.devices.find(d=>d.id===editor.value.id)!} run={dialogRun} onRemoved={saved}/>}
      {editor.kind==='vehicle'&&<VehicleEditor initial={editor.value} settings={settings} save={save} run={dialogRun} onSaved={saved}/>}
      {editor.kind==='connection'&&(editor.name==='ocpp'?<OcppSettings devices={settings.devices} run={dialogRun}/>:<ConnectionForm section={editor.name==='limits'?'installation':editor.name} onSaved={saved} settings={settings} save={save} run={dialogRun} connections={connections}/>)}
      {editor.kind==='add'&&<div className="integration-picker">{(['home_assistant','peugeot','ariston','ocpp'] as const).map(name=><button type="button" key={name} onClick={()=>open({kind:'connection',name})}>{{home_assistant:'Home Assistant',peugeot:'Peugeot',ariston:'Ariston NET',ocpp:'Serveur OCPP'}[name]}<Icon name="arrow" size={18}/></button>)}</div>}
    </SettingsDialog>}
  </div>
}
