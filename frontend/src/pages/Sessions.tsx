import {useEffect,useMemo,useState} from 'react'
import {Icon} from '../components/Icon'
import {SessionChart} from '../sessions/SessionChart'
import {SessionBreakdown} from '../sessions/SessionBreakdown'
import {SessionTable} from '../sessions/SessionTable'
import {SessionDetail} from '../sessions/SessionDetail'
import {localPeriod,movePeriod,periodLabel,seriesFor,energy,money,percent,number,knownCost} from '../sessions/model'
import type {Period,Group,Metric,Sort,SessionPage,Option} from '../sessions/types'

export function Sessions({timezone,vehicles}:{timezone:string;vehicles:Option[]}){
  const [period,setPeriod]=useState<Period>('month'),[date,setDate]=useState(()=>localPeriod(timezone))
  const [metric,setMetric]=useState<Metric>('energy'),[group,setGroup]=useState<Group>('solar')
  const [vehicle,setVehicle]=useState('all'),[charger,setCharger]=useState('all'),[includeEmpty,setIncludeEmpty]=useState(false)
  const [sort,setSort]=useState<Sort>('date'),[direction,setDirection]=useState<'asc'|'desc'>('desc'),[page,setPage]=useState(1)
  const [response,setResponse]=useState<{key:string;data:SessionPage}|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0)
  const [selected,setSelected]=useState<string|null>(null),[exporting,setExporting]=useState(false)
  const query=useMemo(()=>new URLSearchParams({period,year:String(date.year),month:String(date.month),group,sort,direction,page:String(page),page_size:'25',include_empty:String(includeEmpty),...(vehicle!=='all'?{vehicle_id:vehicle}:{}),...(charger!=='all'?{device_id:charger}:{})}).toString(),[period,date,group,sort,direction,page,includeEmpty,vehicle,charger])
  const data=response?.key===query?response.data:null
  // Option lists remain available while a different selection loads.
  const options=response?.data
  useEffect(()=>{const controller=new AbortController();let active=true;setLoading(true);setError('')
    async function load(){try{const result=await fetch('/api/v1/charging-sessions?'+query,{credentials:'same-origin',signal:controller.signal});if(!result.ok)throw new Error(result.status===401?'Reconnectez-vous pour consulter les sessions.':'Impossible de charger les sessions.');const value=await result.json() as SessionPage
      if(active){setResponse({key:query,data:value});setError('');setLoading(false)}}catch(e){if(active&&(e as Error).name!=='AbortError'){setError((e as Error).message);setLoading(false)}}}
    void load();const timer=setInterval(()=>{if(document.visibilityState==='visible')void load()},30000)
    return()=>{active=false;controller.abort();clearInterval(timer)}
  },[query,revision])
  const activeMetric=metric==='cost'&&!data?.available.cost?'energy':metric
  const series=data?seriesFor(data,group,activeMetric):[]
  function changePeriod(next:Period){setPeriod(next);setPage(1)}
  function navigate(delta:number){setDate(movePeriod(period,date.year,date.month,delta));setPage(1)}
  function changeSort(value:Sort){setDirection(sort===value&&direction==='desc'?'asc':'desc');setSort(value);setPage(1)}
  async function download(format:'csv'|'xlsx'){
    setExporting(true);setError('')
    try{const result=await fetch('/api/v1/charging-sessions/export?'+query+'&format='+format,{credentials:'same-origin'});if(!result.ok)throw new Error('Export impossible. Réessayez après avoir vérifié la connexion.');const blob=await result.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`sessions-${period}-${date.year}-${date.month}.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
    catch(e){setError((e as Error).message)}finally{setExporting(false)}
  }
  const total=data?.totals
  const current=localPeriod(timezone),atFuture=period==='year'?date.year>=current.year:date.year>current.year||date.year===current.year&&date.month>=current.month
  return <div className="sessions-page">
    <div className="sessions-period-header"><div className="sessions-segmented" role="group" aria-label="Période">{([['month','Mois'],['year','Année'],['total','Total']] as const).map(([id,name])=><button type="button" key={id} aria-pressed={period===id} onClick={()=>changePeriod(id)}>{name}</button>)}</div>
      {period!=='total'?<div className="sessions-date-nav"><button type="button" onClick={()=>navigate(-1)} disabled={date.year<=1970&&(period==='year'||date.month===1)} aria-label="Période précédente"><Icon name="left"/></button><span aria-live="polite">{periodLabel(period,date.year,date.month)}</span><button type="button" onClick={()=>navigate(1)} disabled={atFuture} aria-label="Période suivante"><Icon name="right"/></button></div>:<span className="sessions-all-time">Tout l’historique</span>}
    </div>
    <div className="sessions-toolbar"><div className="sessions-segmented sessions-icon-options" role="group" aria-label="Statistique"><button type="button" aria-label="Énergie chargée" title="Énergie chargée" aria-pressed={activeMetric==='energy'} onClick={()=>setMetric('energy')}><Icon name="bolt"/><span>Énergie</span></button><button type="button" aria-label="Coût des recharges" title="Coût des recharges" aria-pressed={activeMetric==='cost'} disabled={!data?.available.cost} onClick={()=>setMetric('cost')}><Icon name="euro"/><span>Coût</span></button></div>
      <div className="sessions-segmented sessions-icon-options" role="group" aria-label="Regroupement">{([['solar','sun','Répartition solaire'],['charger','plug','Par point de charge'],['vehicle','car','Par véhicule']] as const).map(([id,icon,name])=><button type="button" key={id} aria-pressed={group===id} aria-label={name} title={name} onClick={()=>{setGroup(id);setPage(1)}}><Icon name={icon}/><span>{name}</span></button>)}</div>
    </div>
    <div className="sessions-filters"><label>Véhicule<select aria-label="Véhicule" value={vehicle} onChange={e=>{setVehicle(e.target.value);setPage(1)}}><option value="all">Tous les véhicules</option>{options?.vehicles.map(v=><option value={v.id} key={v.id}>{v.name}</option>)}</select></label><label>Point de charge<select aria-label="Point de charge" value={charger} onChange={e=>{setCharger(e.target.value);setPage(1)}}><option value="all">Tous les points de charge</option>{options?.chargers.map(c=><option value={c.id} key={c.id}>{c.name}</option>)}</select></label><label className="sessions-empty-check"><input type="checkbox" checked={includeEmpty} onChange={e=>{setIncludeEmpty(e.target.checked);setPage(1)}}/>Inclure les sessions sans énergie</label></div>
    {error&&<div className="alert error" role="alert"><span>{error}</span><button type="button" onClick={()=>setRevision(n=>n+1)}>Réessayer</button></div>}
    {loading&&!data&&<section className="panel sessions-loading" role="status">Chargement des sessions…</section>}
    {data&&total&&<div aria-busy={loading}>
      <section className="panel sessions-main-chart"><h2>{activeMetric==='energy'?'Énergie chargée':'Coût des recharges'}</h2><p className="sessions-chart-summary">{activeMetric==='energy'?<><strong>{energy(total.energy_kwh)}</strong> au total{total.energy_partial?' · mesures partielles':''}{total.solar_percent!=null&&<> · <strong>{percent(total.solar_percent)}</strong> solaire{total.solar_partial?' sur l’énergie d’origine connue':''}</>}</>:<><strong>{money(knownCost(total))}</strong>{total.cost_partial?' connus · coût partiel':' au total'}{total.average_price_per_kwh!=null&&<> · Ø {number(total.average_price_per_kwh,4)} €/kWh</>}</>}</p>
        <SessionChart buckets={data.buckets} series={series} metric={activeMetric} period={period} year={date.year} month={date.month}/>
        {!data.total&&<p className="sessions-empty">Aucune recharge pour cette période.</p>}
        {(total.unknown_kwh>1e-8||total.missing_energy_count>0)&&<p className="sessions-data-note">{total.unknown_kwh>1e-8?`${energy(total.unknown_kwh)} sans répartition solaire/réseau. `:''}{total.missing_energy_count>0?`${total.missing_energy_count} session(s) sans mesure d’énergie.`:''}</p>}
        {activeMetric==='cost'&&total.cost_missing_count>0&&<p className="sessions-data-note">Montant connu sur {total.known_cost_count} session(s). {total.cost_missing_count} session(s) sans coût complet. Le prix moyen utilise uniquement les sessions entièrement mesurées et tarifées.</p>}
      </section>
      {data.total>0&&(group==='solar'?activeMetric==='energy'&&period!=='month':data.groups.length>1)&&<SessionBreakdown data={data} metric={activeMetric} period={period} year={date.year} month={date.month} group={group}/>}
      <SessionTable data={data} sort={sort} direction={direction} onSort={changeSort} onPage={setPage} onOpen={s=>setSelected(s.id)}/>
      <div className="sessions-export"><button type="button" disabled={exporting||!data.total} onClick={()=>download('csv')}><Icon name="download" size={18}/>Exporter en CSV</button><button type="button" disabled={exporting||!data.total} onClick={()=>download('xlsx')}>Excel (.xlsx)</button><small>La période et les filtres sont appliqués à l’export.</small></div>
      <details className="sessions-method"><summary>À propos des mesures</summary><p>Une session couvre le branchement au débranchement. Les graphiques affectent son énergie à sa date de début, dans le fuseau {data.timezone}. La part solaire est estimée à partir des mesures de production et d’import du logement. Une origine inconnue reste inconnue ; aucune énergie de batterie domestique n’est attribuée au solaire. Les sessions entièrement mesurées à 0 kWh sont masquées par défaut. Seules les dernières sessions encore présentes avant cette mise à jour peuvent être récupérées.</p></details>
    </div>}
    {selected&&<SessionDetail id={selected} timezone={timezone} vehicles={vehicles} onClose={()=>setSelected(null)} onChanged={()=>{setPage(1);setRevision(n=>n+1)}}/>}
  </div>
}
