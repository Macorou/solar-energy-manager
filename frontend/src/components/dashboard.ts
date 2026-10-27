import type {LiveState,Sample} from '../api/types'

const usable=(value:Sample|null|undefined):value is Sample & {value:number}=>
  Boolean(value?.usable&&value.value!=null&&Number.isFinite(value.value))

export function sumDevicePower(state:LiveState|null,kind:string):number|null {
  const devices=state?.devices.filter(device=>device.config.kind===kind)
  if(!devices?.length||devices.some(device=>!usable(device.state.observed_power)))return null
  return devices.reduce((total,device)=>total+device.state.observed_power!.value!,0)
}

export function housePower(state:LiveState|null):number|null {
  if(!state)return null
  const samples=[state.grid,state.solar,...state.devices.map(device=>device.state.observed_power)]
  if(samples.some(value=>!usable(value)))return null
  const times=samples.map(value=>value?.measured_at?Date.parse(value.measured_at):Number.NaN)
  if(times.some(value=>!Number.isFinite(value))||Math.max(...times)-Math.min(...times)>2000)return null
  const house=state.grid!.value!+state.solar!.value!-state.devices.reduce((total,device)=>total+device.state.observed_power!.value!,0)
  return house>=0?house:null
}

export function clockSegments(start:string,end:string):{start:number;end:number}[] {
  const minutes=(clock:string)=>{const [hours,mins]=clock.split(':').map(Number);return hours*60+mins}
  const from=minutes(start),to=minutes(end)
  if(from===to)return [{start:0,end:1440}]
  return from<to?[{start:from,end:to}]:[{start:0,end:to},{start:from,end:1440}].filter(value=>value.end>value.start)
}
