import {useEffect,useState} from 'react'
import type {Sample} from '../api/types'

export type PowerReadings=Record<string,number|null>
// Display only: aging/temporarily unavailable readings remain the last reported
// value. Never feed these retained values into command or confirmation decisions.
export const reportedPower=(sample:Sample|null|undefined,signed=false):number|null=>
  sample?.value!=null&&Number.isFinite(sample.value)&&sample.quality!=='invalid'&&(signed||sample.value>=0)?sample.value:null

type DisplayReadings={scope:string;values:PowerReadings;times:PowerReadings;estimated:Record<string,boolean>}
function checkedTime(sample:Sample|null|undefined):number|null{
  return [sample?.checked_at,sample?.received_at,sample?.measured_at].map(value=>Date.parse(value||''))
    .find(Number.isFinite)??null
}
export function useLastPowerReadings(scope:string,current:PowerReadings,samples:Record<string,Sample|null|undefined>={}):DisplayReadings{
  const [previous,setPrevious]=useState<DisplayReadings>(()=>({scope,values:{},times:{},estimated:{}}))
  const next:DisplayReadings={scope,values:{},times:{},estimated:{}}
  for(const [key,value] of Object.entries(current)){
    const known=previous.scope===scope,oldTime=known?previous.times[key]??null:null,time=checkedTime(samples[key])
    // An older fallback is not a new observation. A recent HA check takes
    // precedence over its unchanged provider timestamp, including for zero.
    const accept=value!=null&&(time==null||oldTime==null||time>=oldTime)
    next.values[key]=accept?value:known?previous.values[key]??null:null
    next.times[key]=accept?time??oldTime:oldTime
    next.estimated[key]=accept?samples[key]?.quality==='estimated':known&&Boolean(previous.estimated[key])
  }
  const same=previous.scope===scope&&Object.keys(previous.values).length===Object.keys(next.values).length&&
    Object.keys(next.values).every(key=>previous.values[key]===next.values[key]&&previous.times[key]===next.times[key]&&previous.estimated[key]===next.estimated[key])
  const retained=same?previous:next
  useEffect(()=>{if(retained!==previous)setPrevious(retained)},[retained,previous])
  return retained
}
