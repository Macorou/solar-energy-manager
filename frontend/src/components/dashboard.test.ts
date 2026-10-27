import {expect,it} from 'vitest'
import type {LiveDevice,LiveState,Sample} from '../api/types'
import {clockSegments,housePower,sumDevicePower} from './dashboard'

const at='2026-10-27T12:00:00Z'
const sample=(value:number,extra:Partial<Sample>={}):Sample=>({value,measured_at:at,quality:'fresh',usable:true,...extra})
const device=(id:string,kind:'charger'|'water_heater',power:Sample|null):LiveDevice=>({
  config:{id,kind},state:{observed_power:power},
} as LiveDevice)
const state=(grid=4800,solar=0):LiveState=>({grid:sample(grid),solar:sample(solar),devices:[
  device('car','charger',sample(3700)),device('tank','water_heater',sample(0)),
]} as LiveState)

it('derives the rest of the house without counting the car and tank twice',()=>{
  expect(housePower(state())).toBe(1100)
  const exporting=state(-1000,5000)
  exporting.devices=[device('car','charger',sample(1000))]
  expect(housePower(exporting)).toBe(3000)
})

it('does not invent house consumption from missing, unusable or incoherent measures',()=>{
  expect(housePower(null)).toBeNull()
  expect(housePower({...state(),solar:null})).toBeNull()
  expect(housePower({...state(),grid:sample(4800,{usable:false})})).toBeNull()
  expect(housePower({...state(),grid:sample(Number.NaN)})).toBeNull()
  expect(housePower({...state(),solar:sample(0,{measured_at:null})})).toBeNull()
  expect(housePower({...state(),solar:sample(0,{measured_at:'2026-10-27T11:59:57Z'})})).toBeNull()
  expect(housePower({...state(),devices:[device('car','charger',null)]})).toBeNull()
  expect(housePower(state(2000))).toBeNull()
})

it('keeps an unknown device out of totals instead of treating it as zero',()=>{
  const value=state()
  value.devices.push(device('other','charger',sample(2000,{usable:false})))
  expect(sumDevicePower(value,'charger')).toBeNull()
  expect(housePower(value)).toBeNull()
  expect(sumDevicePower(state(),'water_heater')).toBe(0)
})

it('shows the two parts of a window that crosses midnight',()=>{
  expect(clockSegments('22:00','06:00')).toEqual([{start:0,end:360},{start:1320,end:1440}])
  expect(clockSegments('01:30','05:45')).toEqual([{start:90,end:345}])
  expect(clockSegments('00:00','00:00')).toEqual([{start:0,end:1440}])
})
