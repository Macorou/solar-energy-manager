import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {SettingsPage} from './Settings'
import {api} from '../api/client'
import type {Settings} from '../api/types'
vi.mock('../api/client',()=>({api:vi.fn().mockResolvedValue({ok:true})}))
afterEach(()=>{cleanup();vi.clearAllMocks()})

const initial:Settings={timezone:'Europe/Paris',site_limit_w:11000,export_margin_w:100,sample_max_age_s:30,phase_control_enabled:false,phase_margin_a:1,solar_price_per_kwh:0,devices:[],vehicles:[],schedules:[],off_peak:[],
    home_assistant:{url:'http://ha.test',grid_entity:'sensor.grid',solar_entity:'sensor.solar',house_entity:'',price_entity:'',phases:{},invert_grid:false,device_power_entities:{}},
    peugeot:{username:'',client_id:'',country:'fr',poll_interval_s:900,max_age_s:1800},ariston:{username:'',poll_interval_s:120,max_age_s:600}}
it('saves an optional household total sensor while retaining existing HA mappings and credentials',async()=>{
  const settings=structuredClone(initial)
  delete (settings.home_assistant as Partial<typeof settings.home_assistant>).house_entity
  render(<SettingsPage settings={settings} connections={{home_assistant:true}} save={vi.fn()} run={async op=>{await op()}}/>)
  fireEvent.change(screen.getByLabelText('Entité consommation totale de la maison (facultatif)'),{target:{value:'sensor.house_total'}})
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer Home Assistant'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/home-assistant','PUT',{
    config:expect.objectContaining({house_entity:'sensor.house_total',grid_entity:'sensor.grid',solar_entity:'sensor.solar'}),token:null}))
})

it('saves a chosen phase current limit and dynamic price without inserting real installation mappings',async()=>{
  const save=vi.fn().mockResolvedValue(undefined)
  render(<SettingsPage settings={structuredClone(initial)} connections={{home_assistant:true}} save={save} run={async op=>{await op()}}/>)
  fireEvent.click(screen.getByLabelText('Suivre L1'))
  fireEvent.change(screen.getByLabelText('Courant réseau L1 (A ou mA)'),{target:{value:'sensor.phase_current'}})
  fireEvent.change(screen.getByLabelText('Limite L1 (A)'),{target:{value:'18'}})
  fireEvent.change(screen.getByLabelText('Entité prix actuel du réseau (€/kWh)'),{target:{value:'sensor.price'}})
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer les réglages'}))
  await waitFor(()=>expect(save).toHaveBeenCalledWith(expect.objectContaining({home_assistant:expect.objectContaining({price_entity:'sensor.price',phases:{L1:expect.objectContaining({current_entity:'sensor.phase_current',max_current_a:18})}})})))
})

it('shows stored OCPP identity and retains its secret on a blank save',async()=>{
  vi.mocked(api).mockImplementation(async(path)=>path==='/connections/ocpp'?
    {stations:[{station_id:'box',credentials_saved:true,connected:false,last_error:'heartbeat_timeout'}]} as never:
    {ok:true} as never)
  const settings=structuredClone(initial)
  settings.devices=[{id:'ev',name:'Pulsar',kind:'charger',charge_point_id:'box'}] as Settings['devices']
  render(<SettingsPage settings={settings} connections={{}} save={vi.fn()} run={async op=>{await op()}}/>)
  await screen.findByText('Accès OCPP enregistrés')
  expect((screen.getByLabelText('Identifiant OCPP enregistré') as HTMLSelectElement).value).toBe('box')
  expect((screen.getByLabelText('Mot de passe OCPP') as HTMLInputElement).value).toBe('')
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer l’accès OCPP'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/ocpp/box','PUT',{password:null}))
  expect(screen.getByText(/Délai de communication dépassé/)).toBeTruthy()
})
