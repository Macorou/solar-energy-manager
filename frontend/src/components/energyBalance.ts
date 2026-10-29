import type {LiveState,Sample,Settings} from '../api/types'
import {housePower} from './dashboard'
export interface FlowPart {key:string;label:string;icon:string;power:number}
export interface EnergyBalance {total:number;house:number;sources:FlowPart[];segments:FlowPart[];uses:FlowPart[];notice:string}
export const flowReading=(s:Sample|null|undefined):number|null=>s?.usable&&s.value!=null&&Number.isFinite(s.value)?s.value:null
const checkTime=(s:Sample|null|undefined)=>Date.parse(s?.checked_at||s?.received_at||s?.measured_at||'')
export function energyBalance(settings:Settings,state:LiveState|null):EnergyBalance|null{
  const grid=flowReading(state?.grid),solar=flowReading(state?.solar),house=housePower(state)
  if(!state||grid==null||solar==null||solar<0||house==null)return null
  const times=[checkTime(state.grid),checkTime(state.solar),...(state.house_configured?[checkTime(state.house)]:[])]
  if(times.some(t=>!Number.isFinite(t))||Math.max(...times)-Math.min(...times)>2000)return null
  const demand=grid+solar,total=Math.max(demand,solar)
  if(!Number.isFinite(total)||demand<0||Math.abs(demand-house)>Math.max(100,demand*.05))return null
  const part=(key:string,label:string,icon:string,power:number):FlowPart=>({key,label,icon,power})
  const segments=[part('solar','Solaire consommé sur place','sun',Math.min(solar,demand)),part('import','Import réseau','grid',Math.max(0,grid)),part('export','Export réseau','grid',Math.max(0,-grid))]
  const sources=[part('solar','Production solaire','sun',solar),segments[1]]
  let missing=false,asynchronous=false
  const appliances=settings.devices.map(d=>{const reading=state.devices.find(v=>v.config.id===d.id)?.state.observed_power,power=flowReading(reading)
    if(power==null||power<0)missing=true
    if(!Number.isFinite(checkTime(reading))||Math.abs(checkTime(reading)-Math.max(...times))>2000)asynchronous=true
    return part(d.id,d.name,d.kind==='charger'?'car':'tank',Math.max(0,power??0))})
  const used=appliances.reduce((sum,p)=>sum+p.power,0)
  const contradictory=used>demand+Math.max(50,demand*.02)
  const notice=missing?'Consommation non répartie : mesure d’un appareil indisponible.':contradictory||asynchronous?'Attente de mesures cohérentes pour répartir les consommations.':''
  // Keep one common scale. Never normalize contradictory device measurements to make them fit.
  const uses=notice?[part('house','Consommation non répartie','home',demand),segments[2]]:
    [part('house','Autres usages','home',Math.max(0,demand-used)),...appliances,segments[2]]
  if(!notice&&used>demand)return {total,house,sources,segments,uses:[part('house','Consommation non répartie','home',demand),segments[2]],notice:'Attente de mesures cohérentes pour répartir les consommations.'}
  return {total,house,sources,segments,uses,notice}
}
