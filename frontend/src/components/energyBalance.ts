import type {LiveState,Sample,Settings} from '../api/types'
import {reportedPower,type PowerReadings} from './powerDisplay'
export interface FlowPart {key:string;label:string;icon:string;power:number}
export interface EnergyBalance {total:number;house:number|null;sources:FlowPart[];segments:FlowPart[];uses:FlowPart[];notice:string}
export const flowReading=(sample:Parameters<typeof reportedPower>[0])=>reportedPower(sample,true)
export function flowSamples(settings:Settings,state:LiveState|null):Record<string,Sample|null|undefined>{
  return {grid:state?.grid,solar:state?.solar,house:state?.house,
    ...Object.fromEntries(settings.devices.map(d=>['device:'+d.id,state?.devices.find(v=>v.config.id===d.id)?.state.observed_power]))}
}
export function flowReadings(settings:Settings,state:LiveState|null):PowerReadings{
  const samples=flowSamples(settings,state)
  return {...Object.fromEntries(Object.entries(samples).map(([key,sample])=>[key,reportedPower(sample,key==='grid')])),
    house_configured:state?Number(state.house_configured??Boolean(settings.home_assistant?.house_entity)):null,
  }
}
export function flowScope(settings:Settings):string{
  const ha=settings.home_assistant
  return JSON.stringify([ha?.grid_entity,ha?.solar_entity,ha?.house_entity,settings.devices.map(d=>
    [d.id,d.kind,d.charge_point_id,d.connector_id,d.gateway_id,ha?.device_power_entities?.[d.id]])])
}
export function energyBalance(settings:Settings,state:LiveState|null,readings=flowReadings(settings,state)):EnergyBalance|null{
  const grid=readings.grid,solar=readings.solar
  if(grid==null||solar==null||!Number.isFinite(grid+solar))return null
  const demand=Math.max(0,grid+solar),house=readings.house_configured?readings.house:demand
  const part=(key:string,label:string,icon:string,power:number):FlowPart=>({key,label,icon,power})
  const segments=[part('solar','Solaire consommé sur place','sun',Math.min(solar,demand)),part('import','Import réseau','grid',Math.max(0,grid)),part('export','Export réseau','grid',Math.max(0,-grid))]
  const total=segments.reduce((sum,p)=>sum+p.power,0)
  const sources=[part('solar','Production solaire','sun',solar),segments[1]]
  const appliances=settings.devices.flatMap(d=>{const power=readings['device:'+d.id]
    return power==null?[]:[part(d.id,d.name,d.kind==='charger'?'car':'tank',power)]})
  const used=appliances.reduce((sum,p)=>sum+p.power,0)
  const missing=appliances.length<settings.devices.length
  const notice=missing?'Consommation non répartie : mesure d’un appareil indisponible.':''
  // Each meter updates independently. Keep its actual last watts even while
  // source and appliance totals temporarily differ; do not zero or rescale them.
  const uses=[part('house',missing?'Consommation non répartie':'Autres usages','home',Math.max(0,(house??demand)-used)),...appliances,segments[2]]
  return {total,house,sources,segments,uses,notice}
}
