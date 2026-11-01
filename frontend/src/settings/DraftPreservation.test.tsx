import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import type {Settings} from '../api/types'
import {DeviceEditor,VehicleEditor,newDevice} from './AssetEditor'
import {ConnectionForm} from './ConnectionForm'
import {SourceEditor} from './SourceEditor'
import {api} from '../api/client'
vi.mock('../api/client',()=>({api:vi.fn().mockResolvedValue({ok:true})}))
afterEach(()=>{cleanup();vi.clearAllMocks()})
const initial:Settings={devices:[],vehicles:[],schedules:[],off_peak:[],peugeot:{username:'',country:'fr',client_id:'',poll_interval_s:900,max_age_s:1800},home_assistant:{url:'http://ha.test',grid_entity:'sensor.grid',solar_entity:'sensor.solar',house_entity:'',price_entity:'',phases:{},device_power_entities:{},invert_grid:false},ariston:{username:'old',poll_interval_s:120,max_age_s:600},mqtt:{broker:'',topic:'sem',client_id:'',username:'',allow_self_signed:false,tls:false,discovery_prefix:'homeassistant'},site_limit_w:12000,export_margin_w:100,phase_control_enabled:false,phase_margin_a:1,solar_price_per_kwh:0,sample_max_age_s:30,grid_fallback_current_a:0,timezone:'Europe/Paris'}
const run=async(op:()=>Promise<unknown>)=>{await op()}
it('merges only edited device fields and keeps newer targets, cloud settings, arming and power mapping',async()=>{
  const d={...newDevice(initial,'water_heater'),id:'tank',target:55},settings={...initial,devices:[d],home_assistant:{...initial.home_assistant,device_power_entities:{tank:'sensor.old'}}},save=vi.fn().mockResolvedValue(undefined),props={initial:d,settings,save,run,onSaved:vi.fn()}
  const view=render(<DeviceEditor {...props}/> );fireEvent.change(screen.getByLabelText('Nom'),{target:{value:'Nouveau nom'}})
  view.rerender(<DeviceEditor {...props} settings={{...settings,devices:[{...d,target:65,armed:true,cloud:{...d.cloud,stop_delay_s:900}}],home_assistant:{...settings.home_assistant,device_power_entities:{tank:'sensor.new'}}}}/> )
  fireEvent.submit(screen.getByRole('button',{name:'Enregistrer l’appareil'}).closest('form')!)
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][0].devices[0]).toMatchObject({name:'Nouveau nom',target:65,armed:true,cloud:{stop_delay_s:900}})
  expect(save.mock.calls[0][0].home_assistant.device_power_entities.tank).toBe('sensor.new')
})
it('keeps a refreshed vehicle capacity when only its name is edited',async()=>{
  const vehicle={id:'car',name:'Peugeot',vin:'',capacity_kwh:50,efficiency:.85},save=vi.fn().mockResolvedValue(undefined),props={initial:vehicle,settings:{...initial,vehicles:[vehicle]},save,run,onSaved:vi.fn()}
  const view=render(<VehicleEditor {...props}/> );fireEvent.change(screen.getByLabelText('Nom du véhicule'),{target:{value:'Autre nom'}})
  view.rerender(<VehicleEditor {...props} settings={{...initial,vehicles:[{...vehicle,capacity_kwh:45}]}}/> )
  fireEvent.submit(screen.getByRole('button',{name:'Enregistrer le véhicule'}).closest('form')!)
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][0].vehicles[0]).toMatchObject({name:'Autre nom',capacity_kwh:45})
})
it('preserves refreshed connection configuration when saving a single edited account field',async()=>{
  const props={settings:initial,save:vi.fn(),run,connections:{},section:'ariston' as const},view=render(<ConnectionForm {...props}/> )
  fireEvent.change(screen.getByLabelText('Compte Ariston'),{target:{value:'new-account'}})
  view.rerender(<ConnectionForm {...props} settings={{...initial,ariston:{...initial.ariston,poll_interval_s:300}}}/> )
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer Ariston'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/ariston','PUT',{config:{...initial.ariston,username:'new-account',poll_interval_s:300},password:null}))
})
it('does not replace refreshed phases when only the grid entity was edited',async()=>{
  const props={kind:'grid' as const,settings:initial,run,onSaved:vi.fn()},view=render(<SourceEditor {...props}/> )
  fireEvent.change(screen.getByLabelText('Entité puissance réseau signée'),{target:{value:'sensor.new_grid'}})
  const phases={L1:{current_entity:'sensor.current',voltage_entity:'',power_entity:'',max_current_a:18}}
  view.rerender(<SourceEditor {...props} settings={{...initial,home_assistant:{...initial.home_assistant,phases}}}/> )
  fireEvent.submit(screen.getByRole('button',{name:'Enregistrer la source'}).closest('form')!)
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/home-assistant','PUT',{config:{...initial.home_assistant,grid_entity:'sensor.new_grid',phases},token:null}))
})
