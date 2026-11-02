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

it('includes the car and tank in the total household consumption',()=>{
  expect(housePower(state())).toBe(4800)
  const exporting=state(-1000,5000)
  exporting.devices=[device('car','charger',sample(1000))]
  expect(housePower(exporting)).toBe(4000)
})

it('does not invent house consumption from missing, unusable or incoherent measures',()=>{
  expect(housePower(null)).toBeNull()
  expect(housePower({...state(),solar:null})).toBeNull()
  expect(housePower({...state(),grid:sample(4800,{usable:false})})).toBeNull()
  expect(housePower({...state(),grid:sample(Number.NaN)})).toBeNull()
  expect(housePower({...state(),solar:sample(0,{measured_at:null})})).toBeNull()
  expect(housePower({...state(),solar:sample(0,{measured_at:'2026-10-27T11:59:57Z'})})).toBeNull()
  expect(housePower({...state(),devices:[device('car','charger',null)]})).toBe(4800)
  expect(housePower(state(-2000,1000))).toBeNull()
  expect(housePower(state(Number.MAX_VALUE,Number.MAX_VALUE))).toBeNull()
})

it('keeps an unknown device out of totals instead of treating it as zero',()=>{
  const value=state()
  value.devices.push(device('other','charger',sample(2000,{usable:false})))
  expect(sumDevicePower(value,'charger')).toBeNull()
  expect(housePower(value)).toBe(4800)
  expect(sumDevicePower(state(),'water_heater')).toBe(0)
})

it('pairs current HA checks even when unchanged zero publications are old',()=>{
  const value=state(400)
  value.grid=sample(400,{checked_at:at})
  value.solar=sample(0,{measured_at:'2026-10-26T12:00:00Z',checked_at:at})
  expect(housePower(value)).toBe(400)
  value.solar=sample(0,{measured_at:'2026-10-26T12:00:00Z',checked_at:'2026-10-27T11:59:57Z'})
  expect(housePower(value)).toBeNull()
})

it.each([0,5200])('uses the configured total-house sensor value %s independently of grid and devices',value=>{
  expect(housePower({...state(),grid:null,solar:null,house_configured:true,house:sample(value)})).toBe(value)
})

it.each([null,sample(600,{usable:false}),sample(-1),sample(Number.NaN)])('does not silently fall back from an invalid configured sensor',house=>{
  expect(housePower({...state(),house_configured:true,house})).toBeNull()
})

it('shows the two parts of a window that crosses midnight',()=>{
  expect(clockSegments('22:00','06:00')).toEqual([{start:0,end:360},{start:1320,end:1440}])
  expect(clockSegments('01:30','05:45')).toEqual([{start:90,end:345}])
  expect(clockSegments('00:00','00:00')).toEqual([{start:0,end:1440}])
})
