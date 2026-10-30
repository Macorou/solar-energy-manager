import type {Period,Group,Metric,SessionPage,Bucket,Series} from './types'
export const number=(value:number|null|undefined,digits=1)=>value==null?'—':value.toLocaleString('fr-FR',{maximumFractionDigits:digits})
export const energy=(value:number|null|undefined)=>value==null?'—':`${number(value,2)} kWh`
export const money=(value:number|null|undefined)=>value==null?'—':value.toLocaleString('fr-FR',{style:'currency',currency:'EUR'})
export const percent=(value:number|null|undefined)=>value==null?'—':`${number(value,0)} %`
export function duration(seconds:number|null|undefined){if(seconds==null)return '—';const minutes=Math.floor(seconds/60);return minutes>=60?`${Math.floor(minutes/60)} h ${String(minutes%60).padStart(2,'0')}`:`${minutes} min`}
export const fullDate=(value:string|null|undefined,timezone:string)=>value?new Date(value).toLocaleString('fr-FR',{dateStyle:'medium',timeStyle:'short',timeZone:timezone}):'—'
export function movePeriod(period:Period,year:number,month:number,delta:number){
  if(period==='year')return {year:year+delta,month}
  if(period==='total')return {year,month}
  const d=new Date(Date.UTC(year,month-1+delta,1));return {year:d.getUTCFullYear(),month:d.getUTCMonth()+1}
}
export const periodLabel=(period:Period,year:number,month:number)=>period==='total'?'Tout l’historique':period==='year'?String(year):new Date(Date.UTC(year,month-1,1)).toLocaleDateString('fr-FR',{month:'long',year:'numeric',timeZone:'UTC'})
export function localPeriod(timezone:string){const parts=new Intl.DateTimeFormat('en',{year:'numeric',month:'numeric',timeZone:timezone}).formatToParts(new Date());return {year:Number(parts.find(p=>p.type==='year')!.value),month:Number(parts.find(p=>p.type==='month')!.value)}}
const palette=['#63b5f6','#a991ef','#f3b35d','#eb839a','#5ccebb','#b4ca68','#df96da','#90acdb','#d39576','#73bfde']
export function colorFor(id:string){let hash=2166136261;for(const char of id){hash^=char.charCodeAt(0);hash=Math.imul(hash,16777619)}return palette[(hash>>>0)%palette.length]}
export function equipmentColors(data:SessionPage,group:Group){
  const options=group==='charger'?data.chargers:data.vehicles,colors:Record<string,string>={},used=new Set<string>()
  for(const option of [...(options||[])].sort((a,b)=>a.id.localeCompare(b.id))){
    let index=palette.indexOf(colorFor(option.id)),color=palette[index]
    for(let i=0;i<palette.length&&used.has(color);i++)color=palette[++index%palette.length]
    colors[option.id]=color;used.add(color)
  }
  return colors
}
export function seriesFor(data:SessionPage,group:Group,metric:Metric):Series[]{
  if(group!=='solar'){const colors=equipmentColors(data,group);return data.groups.filter(g=>metric!=='cost'||g.totals.priced_count>0).map(g=>({id:g.id,name:g.name,color:colors[g.id]||colorFor(g.id)}))}
  if(metric==='cost')return [{id:'cost',name:'Coût des recharges',color:'var(--blue)'}]
  const series=[{id:'grid',name:'Réseau électrique',color:'#939ba8'},{id:'solar',name:'Solaire',color:'#42c995'}]
  if(data.buckets.some(b=>(b.energy.unknown||0)>1e-8))series.push({id:'unknown',name:'Origine inconnue',color:'#b59bc9'})
  return series
}
export function chartBounds(buckets:Bucket[],metric:Metric){let min=0,max=0;for(const b of buckets){const v=Object.values(b[metric]).map(n=>n??0);max=Math.max(max,v.reduce((a,n)=>a+Math.max(0,n),0));min=Math.min(min,v.reduce((a,n)=>a+Math.min(0,n),0))}return {min,max}}
export function bucketLabel(key:string,period:Period,year:number,month:number,short=false){
  if(period==='total')return key
  if(period==='year')return new Date(Date.UTC(year,Number(key)-1,1)).toLocaleDateString('fr-FR',{month:short?'short':'long',timeZone:'UTC'})
  return short?key:new Date(Date.UTC(year,month-1,Number(key))).toLocaleDateString('fr-FR',{day:'numeric',month:'long',timeZone:'UTC'})
}
