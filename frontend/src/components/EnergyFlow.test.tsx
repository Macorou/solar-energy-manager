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
it('does not fabricate source readings from missing or invalid values',()=>{
  expect(energyBalance(settings,null)).toBeNull()
  expect(energyBalance(settings,{...live(),solar:null})).toBeNull()
  expect(energyBalance(settings,{...live(),grid:sample(Number.NaN)})).toBeNull()
  expect(energyBalance(settings,{...live(),solar:sample(-1)})).toBeNull()
})
it('keeps known appliances visible when another reading is missing or totals arrive separately',()=>{
  const state=live();state.devices[0].state.observed_power=null
  expect(energyBalance(settings,state)!.notice).toContain('non répartie')
  expect(energyBalance(settings,state)!.uses.map(p=>[p.key,p.power])).toEqual([['house',4350],['tank',2570],['export',0]])
  expect(energyBalance(settings,live(50,0))!.uses.map(p=>[p.key,p.power])).toEqual([['house',0],['ev',3700],['tank',2570],['export',0]])
})
it('displays the last source readings even when their checks arrive separately',()=>{
  const state=live();state.house_configured=true;state.house=sample(6920)
  state.solar={...sample(4800),checked_at:'2026-10-29T11:59:40Z'}
  expect(energyBalance(settings,state)!.house).toBe(6920)
  expect(energyBalance(settings,state)!.uses.map(p=>p.power)).toEqual([650,3700,2570,0])
})
it('retains the reported appliance power when its timestamp differs from the grid',()=>{
  const state=live();state.devices[0].state.observed_power={...sample(3700),checked_at:'2026-10-29T11:59:35Z'}
  const model=energyBalance(settings,state)!
  expect(model.segments.map(p=>p.power)).toEqual([4800,2120,0])
  expect(model.uses.map(p=>[p.key,p.power])).toEqual([['house',650],['ev',3700],['tank',2570],['export',0]])
})
it('renders one bar with icon-only markers and stable appliance totals',()=>{
  render(<EnergyFlow settings={settings} state={live(6920,0)}/> )
  expect(document.querySelectorAll('.energy-track')).toHaveLength(1)
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('style')).toContain('3700')
  expect([...document.querySelectorAll('.energy-bracket')].every(n=>n.textContent==='')).toBe(true)
  expect(screen.getByRole('region',{name:'Flux d’énergie'})).toBeTruthy()
})
it('keeps each last power through missing readings and updates or removes only the reporting appliance',()=>{
  const state=live(6920,0)
  const {rerender}=render(<EnergyFlow settings={settings} state={state}/> )
  const missing=live(6920,0);missing.devices[0].state.observed_power=null
  missing.devices[1].state.observed_power={...sample(2570),usable:false,quality:'stale'}
  rerender(<EnergyFlow settings={settings} state={missing}/> )
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('aria-label')).toBe('Wallbox : 3,7 kW')
  expect(document.querySelector('[data-use="tank"]')?.getAttribute('aria-label')).toBe('Ballon : 2,57 kW')
  const reduced=live(4680,0);reduced.devices[0].state.observed_power=sample(2300);reduced.devices[1].state.observed_power=null
  rerender(<EnergyFlow settings={settings} state={reduced}/> )
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('aria-label')).toBe('Wallbox : 2,3 kW')
  expect(document.querySelector('[data-use="tank"]')?.getAttribute('aria-label')).toBe('Ballon : 2,57 kW')
  const stopped=live(1000,0);stopped.devices[0].state.observed_power=sample(0);stopped.devices[1].state.observed_power=null
  rerender(<EnergyFlow settings={settings} state={stopped}/> )
  expect(document.querySelector('[data-use="ev"]')).toBeNull()
  expect(document.querySelector('[data-use="tank"]')).not.toBeNull()
  stopped.devices[1].state.observed_power=sample(0)
  rerender(<EnergyFlow settings={settings} state={{...stopped}}/> )
  expect(document.querySelector('[data-use="tank"]')).toBeNull()
  expect(state.devices[0].state.observed_power?.value).toBe(3700)
  expect(missing.devices[0].state.observed_power).toBeNull()
})
it('retains the diagram during an interrupted refresh without reviving a previously reported zero',()=>{
  const state=live(4680,0);state.devices[1].state.observed_power=sample(0)
  const {rerender}=render(<EnergyFlow settings={settings} state={state}/> )
  rerender(<EnergyFlow settings={settings} state={null}/> )
  expect(document.querySelector('.energy-track .energy-import')?.textContent).toBe('4,68 kW')
  expect(document.querySelector('[data-use="ev"]')).not.toBeNull()
  expect(document.querySelector('[data-use="tank"]')).toBeNull()
  const stopped=live(980,0);stopped.devices[0].state.observed_power=sample(0);stopped.devices[1].state.observed_power=sample(0)
  rerender(<EnergyFlow settings={settings} state={stopped}/> )
  rerender(<EnergyFlow settings={settings} state={null}/> )
  expect(document.querySelector('[data-use="ev"]')).toBeNull()
})
it('does not reuse readings after a power source or device is removed from configuration',()=>{
  const {rerender}=render(<EnergyFlow settings={settings} state={live(6920,0)}/> )
  const removed={...settings,devices:settings.devices.filter(d=>d.id!=='ev')}
  rerender(<EnergyFlow settings={removed} state={live(6920,0)}/> )
  expect(document.querySelector('[data-use="ev"]')).toBeNull()
  const changed={...removed,home_assistant:{grid_entity:'sensor.new_grid'}} as Settings
  rerender(<EnergyFlow settings={changed} state={null}/> )
  expect(document.querySelector('.energy-track')).toBeNull()
})
it('keeps an appliance while grid and solar reach zero before its own next reading',()=>{
  const state=live(4680,0);state.devices[1].state.observed_power=sample(0)
  const {rerender}=render(<EnergyFlow settings={settings} state={state}/> )
  const waiting=live(0,0);waiting.devices[0].state.observed_power=null;waiting.devices[1].state.observed_power=null
  rerender(<EnergyFlow settings={settings} state={waiting}/> )
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('aria-label')).toBe('Wallbox : 3,7 kW')
  waiting.devices[0].state.observed_power=sample(0)
  rerender(<EnergyFlow settings={settings} state={{...waiting}}/> )
  expect(document.querySelector('[data-use="ev"]')).toBeNull()
})
it.each([[0,3700],[3700,0]])('keeps newer %s W when an older %s W fallback arrives', (latest,older)=>{
  const state=live(4680,0);state.devices[1].state.observed_power=sample(0)
  state.devices[0].state.observed_power={...sample(latest),checked_at:'2026-10-29T12:01:00Z'}
  const {rerender}=render(<EnergyFlow settings={settings} state={state}/> )
  const fallback=live(4680,0);fallback.devices[1].state.observed_power=sample(0)
  fallback.devices[0].state.observed_power={...sample(older),usable:false,quality:'stale'}
  rerender(<EnergyFlow settings={settings} state={fallback}/> )
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('aria-label')??null).toBe(latest===0?null:'Wallbox : 3,7 kW')
  fallback.devices[0].state.observed_power={...sample(older),measured_at:'2026-10-28T12:00:00Z',checked_at:'2026-10-29T12:02:00Z'}
  rerender(<EnergyFlow settings={settings} state={{...fallback}}/> )
  expect(document.querySelector('[data-use="ev"]')?.getAttribute('aria-label')??null).toBe(older===0?null:'Wallbox : 3,7 kW')
})
