import {render,act,screen,fireEvent,cleanup,waitFor,within} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {SettingsPage} from './Settings'
import {api} from '../api/client'
import type {Settings,LiveState} from '../api/types'
vi.mock('../api/client',async importOriginal=>({...await importOriginal<typeof import('../api/client')>(),api:vi.fn()}))
beforeEach(()=>{vi.mocked(api).mockImplementation(async path=>(path==='/connections/ocpp'?{stations:[]}:{ok:true}) as never)})
afterEach(()=>{cleanup();vi.clearAllMocks()})
const initial:Settings={timezone:'Europe/Paris',site_limit_w:11000,export_margin_w:100,sample_max_age_s:30,phase_control_enabled:false,phase_margin_a:1,solar_price_per_kwh:0,devices:[],vehicles:[],schedules:[],off_peak:[],
  home_assistant:{url:'http://ha.test',grid_entity:'sensor.grid',solar_entity:'sensor.solar',house_entity:'',price_entity:'',phases:{},invert_grid:false,device_power_entities:{}},
  peugeot:{username:'',client_id:'',country:'fr',poll_interval_s:900,max_age_s:1800},ariston:{username:'',poll_interval_s:120,max_age_s:600}}
const run=async(op:()=>Promise<unknown>)=>{await op()}
const live=(power=732):LiveState=>({simulation:false,at:'2026-10-29T12:00:00Z',running:true,grid:{value:power,measured_at:'2026-10-29T12:00:00Z',quality:'fresh',usable:true},solar:null,solar_budget_w:0,off_peak:false,errors:{},devices:[],vehicles:{}})
it('updates grouped readings without resetting an open draft',async()=>{
  const props={settings:structuredClone(initial),save:vi.fn(),run,connections:{home_assistant:true}}
  const view=render(<SettingsPage {...props} state={live()}/> )
  await act(async()=>{})
  expect(within(screen.getByRole('article',{name:'Compteur réseau'})).getByText('732 W')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Configurer Compteur réseau'}))
  fireEvent.change(screen.getByLabelText('Entité puissance réseau signée'),{target:{value:'sensor.edited_grid'}})
  view.rerender(<SettingsPage {...props} state={live(1430)}/> )
  expect((screen.getByLabelText('Entité puissance réseau signée') as HTMLInputElement).value).toBe('sensor.edited_grid')
  expect(within(screen.getByRole('article',{name:'Compteur réseau'})).getByText('1,43 kW')).toBeTruthy()
})
it('keeps unavailable readings distinct from zero and stored credentials distinct from live connectivity',async()=>{
  render(<SettingsPage settings={initial} connections={{home_assistant:true}} save={vi.fn()} run={run}/> )
  await act(async()=>{})
  expect(within(screen.getByRole('article',{name:'Compteur réseau'})).getByText('—',{selector:'.settings-primary-value'})).toBeTruthy()
  fireEvent.click(screen.getByRole('tab',{name:'Intégrations'}))
  expect(within(screen.getByRole('article',{name:'Home Assistant'})).getByText('Accès enregistré')).toBeTruthy()
  expect(within(screen.getByRole('article',{name:'Home Assistant'})).queryByText('Connecté')).toBeNull()
})
it('saves the household sensor preserving other mappings and the existing credential',async()=>{
  render(<SettingsPage settings={structuredClone(initial)} connections={{home_assistant:true}} save={vi.fn()} run={run}/> )
  fireEvent.click(screen.getByRole('button',{name:'Configurer Consommation maison'}))
  fireEvent.change(screen.getByLabelText('Entité consommation totale de la maison (facultatif)'),{target:{value:'sensor.house_total'}})
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer la source'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/home-assistant','PUT',{config:expect.objectContaining({house_entity:'sensor.house_total',grid_entity:'sensor.grid',solar_entity:'sensor.solar'}),token:null}))
  await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
})
it('cancels a draft without saving or commanding a device',async()=>{
  const save=vi.fn();render(<SettingsPage settings={initial} connections={{}} save={save} run={run}/> )
  await act(async()=>{})
  fireEvent.click(screen.getByRole('button',{name:'Configurer Production solaire'}))
  fireEvent.change(screen.getByLabelText('Entité production solaire'),{target:{value:'sensor.unsaved'}})
  fireEvent.click(screen.getByRole('button',{name:'Annuler'}))
  expect(save).not.toHaveBeenCalled()
  expect(vi.mocked(api).mock.calls.filter(([,method])=>method&&method!=='GET')).toEqual([])
  fireEvent.click(screen.getByRole('button',{name:'Configurer Production solaire'}))
  expect((screen.getByLabelText('Entité production solaire') as HTMLInputElement).value).toBe('sensor.solar')
})
it('keeps a failed draft open and shows the error in its dialog',async()=>{
  vi.mocked(api).mockImplementation(async(_path,method)=>{if(method==='PUT')throw Error('Capteur non valide');return {stations:[]} as never})
  render(<SettingsPage settings={initial} connections={{}} save={vi.fn()} run={async op=>{try{await op()}catch{}}}/> )
  fireEvent.click(screen.getByRole('button',{name:'Configurer Production solaire'}))
  fireEvent.change(screen.getByLabelText('Entité production solaire'),{target:{value:'sensor.retry'}})
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer la source'}))
  await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('alert').textContent).toContain('Capteur non valide'))
  expect((screen.getByLabelText('Entité production solaire') as HTMLInputElement).value).toBe('sensor.retry')
})
it.each([0,null])('does not claim the heater is heating with %s watts confirmed',async power=>{
  const config={id:'tank',name:'Ariston test',kind:'water_heater',target:55,solar_target:75} as Settings['devices'][number]
  const state=live();state.devices=[{config,state:{connected:true,observed_state:'on',observed_power:{value:power,quality:'fresh',usable:power!=null,measured_at:state.at},temperature:58,target_temperature:55,fault:null},reason:'Objectif atteint',reservation_w:0,command:null,authorization:null}]
  render(<SettingsPage settings={{...initial,devices:[config]}} connections={{}} save={vi.fn()} run={run} state={state}/> )
  await act(async()=>{})
  expect(within(screen.getByRole('article',{name:'Ariston test'})).queryByText('En chauffe')).toBeNull()
})
it('labels historical Peugeot readings while retaining their last known percentage',async()=>{
  const settings={...initial,vehicles:[{id:'car',name:'Peugeot test',vin:'',capacity_kwh:50,efficiency:.85}]}
  const state=live();state.vehicles.car={soc:60,range_km:176,measured_at:'2026-10-27T08:00:00Z',fresh:false}
  render(<SettingsPage settings={settings} connections={{}} save={vi.fn()} run={run} state={state}/> )
  await act(async()=>{})
  const card=within(screen.getByRole('article',{name:'Peugeot test'}))
  expect(card.getByText('60 %')).toBeTruthy()
  expect(card.getByText('Donnée ancienne')).toBeTruthy()
})
