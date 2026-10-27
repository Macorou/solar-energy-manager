import type {Settings} from '../api/types'
import {clockSegments} from './dashboard'
import {Icon} from './Icon'

const days=['lun.','mar.','mer.','jeu.','ven.','sam.','dim.']
export function ScheduleTimeline({settings,onOpen}:{settings:Pick<Settings,'schedules'|'off_peak'>;onOpen:()=>void}) {
  const rows=[...settings.schedules.filter(program=>program.enabled).map(program=>({id:program.id,kind:'car',label:'Voiture',
    detail:program.name,start:program.earliest_start,end:program.deadline,weekdays:program.weekdays,target:`${program.target_soc} % à ${program.deadline}`})),
    ...settings.off_peak.map((window,index)=>({id:'hc-'+index,kind:'drop',label:'Eau chaude',detail:'Heures creuses',
      start:window.start,end:window.end,weekdays:window.weekdays,target:'HC/HP'}))]
  const endMinute=Math.max(480,Math.ceil(Math.max(0,...rows.flatMap(row=>clockSegments(row.start,row.end).map(segment=>segment.end)))/240)*240)
  return <section className="panel timeline-panel">
    <div className="section-title"><h2><Icon name="calendar" size={24}/>Planning</h2><button className="text-button" onClick={onOpen}>Voir le détail <Icon name="arrow" size={15}/></button></div>
    <p className="timeline-caption">Créneaux réseau autorisés · le solaire peut anticiper.</p>
    <div className="timeline" role="list" aria-label="Plages configurées">
      <div className="timeline-axis" aria-hidden="true"><span/>{[0,1,2,3,4].map(index=><span key={index}>{String(index*endMinute/240).padStart(2,'0')}:00</span>)}</div>
      {rows.length?rows.map(row=><div className={'timeline-row '+row.kind} key={row.id} role="listitem">
        <div className="timeline-label"><Icon name={row.kind} size={20}/><span>{row.label}<small>{row.detail}</small></span></div>
        <div className="timeline-window"><div className="timeline-track" aria-hidden="true">{clockSegments(row.start,row.end).map((segment,index)=><i key={index} style={{left:segment.start/endMinute*100+'%',width:(segment.end-segment.start)/endMinute*100+'%'}}/>)}</div>
          <span className="timeline-description">{row.start} – {row.end}{row.start>=row.end?(row.kind==='car'?' · début la veille':' · fin le lendemain'):''} · {row.kind==='car'?'échéance':'début'} {row.weekdays.map(day=>days[day]).join(' ')} · {row.target}</span>
        </div></div>):<div className="timeline-empty"><Icon name="calendar" size={27}/><p>Aucun créneau enregistré.<br/><button className="text-button" onClick={onOpen}>Créer votre premier planning</button></p></div>}
    </div>
    <p className="timeline-footnote"><Icon name="info" size={14}/>Ces plages autorisent le réseau ; elles ne prédisent pas la durée de fonctionnement.</p>
  </section>
}
