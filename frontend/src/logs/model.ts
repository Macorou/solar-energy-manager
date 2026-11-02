import type {components} from '../api/schema'
export type LogEntry=components['schemas']['LogEntry']
export type LogLevel=LogEntry['level']
export type LogPage=components['schemas']['LogPage']
export const levels:LogLevel[]=['FATAL','ERROR','WARN','INFO','DEBUG','TRACE']
export function logQuery(level:LogLevel,areas:string[]|null,search:string){
  const query=new URLSearchParams({level,search})
  if(areas!==null)for(const area of areas.length?[...areas].sort():[''])query.append('area',area)
  return query.toString()
}
export function mergeEntries(previous:LogEntry[],incoming:LogEntry[],limit=2000,keep:'latest'|'oldest'='latest'){
  const rows=[...new Map([...previous,...incoming].map(row=>[row.id,row])).values()].sort((a,b)=>a.id-b.id)
  return keep==='oldest'?rows.slice(0,limit):rows.slice(-limit)
}
export function logTime(at:string,timezone:string){
  return new Date(at).toLocaleString('fr-FR',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})
}
