import {render,screen,cleanup} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import type {Settings,LiveState,Sample} from '../api/types'
import {energyBalance} from './energyBalance'
import {EnergyFlow} from './EnergyFlow'
afterEach(cleanup)
const sample=(value:number):Sample=>({value,usable:true,quality:'fresh',measured_at:'2026-10-29T12:00:00Z'})
const settings={devices:[{id:'ev',kind:'charger',name:'Wallbox'},{id:'tank',kind:'water_heater',name:'Ballon'}]} as Settings
const live=(grid=2120,solar=4800):LiveState=>({grid:sample(grid),solar:sample(solar),devices:settings.devices.map(config=>({config,state:{observed_power:sample(config.id==='ev'?3700:2570)}})),house_configured:false} as LiveState)
it('balances import and local solar while keeping total appliance consumption',()=>{
  const model=energyBalance(settings,live())!
  expect(model.segments.map(s=>[s.key,s.power])).toEqual([['solar',4800],['import',2120],['export',0]])
  expect(model.uses.map(s=>[s.key,s.power])).toEqual([['house',650],['ev',3700],['tank',2570],['export',0]])
  expect(model.total).toBe(6920)
})
it('does not count exported solar twice',()=>{
  const state=live(-1850,6200);state.devices[1].state.observed_power=sample(0)
  const model=energyBalance(settings,state)!
  expect(model.segments.map(s=>s.power)).toEqual([4350,0,1850])
  expect(model.segments.reduce((s,v)=>s+v.power,0)).toBe(6200)
})
it('keeps the car and heater segments at night',()=>{
  expect(energyBalance(settings,live(6920,0))!.uses.map(s=>s.power)).toEqual([650,3700,2570,0])
})
it('does not fabricate source readings from unavailable or incoherent measurements',()=>{
  expect(energyBalance(settings,null)).toBeNull()
  expect(energyBalance(settings,{...live(),solar:null})).toBeNull()
  expect(energyBalance(settings,{...live(),grid:{...sample(2120),usable:false}})).toBeNull()
  expect(energyBalance(settings,{...live(),solar:sample(-1)})).toBeNull()
  expect(energyBalance(settings,{...live(),solar:{...sample(4800),measured_at:'2026-10-29T11:58:00Z'}})).toBeNull()
})
it('keeps unknown device consumption unallocated and does not scale contradictory totals',()=>{
  const state=live();state.devices[0].state.observed_power=null
  expect(energyBalance(settings,state)!.notice).toContain('non répartie')
  expect(energyBalance(settings,state)!.uses[0].power).toBe(6920)
  expect(energyBalance(settings,live(50,0))!.notice).toContain('cohérentes')
})
it('requires coherent source checks even with an independent house sensor',()=>{
  const state=live();state.house_configured=true;state.house=sample(6920)
  state.solar={...sample(4800),checked_at:'2026-10-29T11:59:40Z'}
  expect(energyBalance(settings,state)).toBeNull()
})
it('retains source totals but does not attribute outdated appliance power',()=>{
  const state=live();state.devices[0].state.observed_power={...sample(3700),checked_at:'2026-10-29T11:59:35Z'}
  const model=energyBalance(settings,state)!
  expect(model.segments.map(p=>p.power)).toEqual([4800,2120,0])
  expect(model.notice).toContain('cohérentes')
  expect(model.uses[0]).toMatchObject({key:'house',power:6920})
})
it('renders one bar with icon-only markers and stable appliance totals',()=>{
  render(<EnergyFlow settings={settings} state={live(6920,0)}/> )
  expect(document.querySelectorAll('.energy-track')).toHaveLength(1)
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('style')).toContain('3700')
  expect([...document.querySelectorAll('.energy-bracket')].every(n=>n.textContent==='')).toBe(true)
  expect(screen.getByRole('region',{name:'Flux d’énergie'})).toBeTruthy()
})
