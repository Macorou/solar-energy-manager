import {useEffect,useMemo,useRef,useState} from 'react'
import {Icon} from '../components/Icon'
import {levels,logQuery,logTime,type LogLevel} from '../logs/model'
import {useJournal} from '../logs/useJournal'
import {ZonePicker} from '../logs/ZonePicker'

export function Logs({timezone}:{timezone:string}){
  const [running,setRunning]=useState(true),[level,setLevel]=useState<LogLevel>('DEBUG')
  const [search,setSearch]=useState(''),[debounced,setDebounced]=useState(''),[areas,setAreas]=useState<string[]|null>(null)
  const [exporting,setExporting]=useState(false),[exportError,setExportError]=useState(''),[following,setFollowing]=useState(true)
  const viewport=useRef<HTMLDivElement>(null),follow=useRef(true)
  useEffect(()=>{const timer=setTimeout(()=>setDebounced(search),250);return()=>clearTimeout(timer)},[search])
  const query=useMemo(()=>logQuery(level,areas,debounced),[level,areas,debounced])
  const {data,areas:available,error,loading,retry,loadOlder,reset}=useJournal(query,running)
  useEffect(()=>{if(follow.current&&viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight},[data?.entries])
  useEffect(()=>{follow.current=true;setFollowing(true)},[query])
  async function download(){
    setExporting(true);setExportError('')
    try{
      const response=await fetch('/api/v1/logs/export?'+query,{credentials:'same-origin',cache:'no-store'})
      if(!response.ok)throw new Error('Téléchargement impossible. Vérifiez la connexion puis réessayez.')
      const url=URL.createObjectURL(await response.blob()),link=document.createElement('a')
      link.href=url;link.download='solar-energy-manager-journaux.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
    }catch(e){setExportError((e as Error).message)}finally{setExporting(false)}
  }
  return <div className="journal-page">
    <section className="panel journal-panel" aria-label="Journaux de communication">
      <div className="journal-toolbar">
        <div className="journal-playback"><button type="button" className={running?'journal-running':''} aria-label={running?'Mettre en pause les journaux':'Reprendre les journaux'} aria-pressed={running} onClick={()=>setRunning(!running)}><span>Mise à jour automatique</span><Icon name={running?'pause':'play'} size={18}/></button><button type="button" aria-label="Télécharger les journaux" title="Télécharger les lignes correspondant aux filtres" disabled={exporting} onClick={()=>void download()}><Icon name="download" size={20}/></button></div>
        <input className="journal-search" type="search" placeholder="Rechercher" aria-label="Rechercher dans les journaux" value={search} maxLength={200} onChange={e=>setSearch(e.target.value)}/>
        <select className="journal-level" aria-label="Niveau des journaux" value={level} onChange={e=>setLevel(e.target.value as LogLevel)}>{levels.map(value=><option key={value}>{value}</option>)}</select>
        <ZonePicker areas={available} selected={areas} onChange={setAreas}/>
      </div>
      {(error||exportError)&&<div className="journal-error" role="alert"><span>{error||exportError}</span><button type="button" onClick={()=>{setExportError('');retry()}}>Réessayer</button></div>}
      <div className="journal-status"><span><i className={running?'status-dot':'journal-paused'}/>{running?'En direct':'En pause'}{loading?' · Chargement…':''}</span><span>{data?.entries.length??0} lignes · {timezone}</span></div>
      {data?.gap&&<p className="journal-notice">Certaines lignes ont expiré pendant l’interruption. Les journaux encore conservés sont affichés.</p>}
      {!!data?.dropped&&<p className="journal-notice">{data.dropped} ligne(s) n’ont pas pu être enregistrées par le service.</p>}
      {data?.has_older&&<button type="button" className="journal-older" onClick={()=>{setRunning(false);follow.current=false;setFollowing(false);loadOlder()}}>Charger les lignes précédentes</button>}
      <div className="journal-console" role="region" aria-label="Console des journaux" tabIndex={0} ref={viewport} onScroll={()=>{
        const el=viewport.current;if(!el)return
        const atBottom=el.scrollHeight-el.clientHeight-el.scrollTop<40
        follow.current=atBottom;setFollowing(atBottom)
      }}>
        {data?.entries.map(row=><div className={'journal-line level-'+row.level.toLowerCase()} key={row.id}><span className="journal-area">[{row.area}]</span>{' '}<span className="journal-severity">{row.level}</span>{' '}<time dateTime={row.at}>{logTime(row.at,timezone)}</time>{' '}<span>{row.message}</span></div>)}
        {!loading&&!data?.entries.length&&!error&&<p className="journal-empty">Aucune ligne pour ces filtres.</p>}
        {loading&&!data&&<p className="journal-empty" role="status">Chargement des journaux…</p>}
      </div>
      {(!following||data&&data.entries.length>=2000)&&<button type="button" className="journal-latest" onClick={()=>{follow.current=true;setFollowing(true);reset();setRunning(true)}}><Icon name="down" size={16}/>Revenir aux dernières lignes</button>}
    </section>
    <p className="journal-footnote">Conservation : 7 jours, jusqu’à 10 000 lignes. Le téléchargement respecte les filtres et inclut toutes les lignes conservées. La pause concerne uniquement l’affichage. Les secrets et les contenus d’authentification sont masqués.</p>
  </div>
}
