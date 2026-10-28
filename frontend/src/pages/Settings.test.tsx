import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {SettingsPage} from './Settings'
import {api} from '../api/client'
import type {Settings} from '../api/types'
vi.mock('../api/client',()=>({api:vi.fn().mockResolvedValue({ok:true})}))
afterEach(()=>{cleanup();vi.clearAllMocks()})

it('saves an optional household total sensor while retaining existing HA mappings and credentials',async()=>{
  const settings:Settings={timezone:'Europe/Paris',site_limit_w:11000,export_margin_w:100,sample_max_age_s:30,devices:[],vehicles:[],schedules:[],off_peak:[],
    home_assistant:{url:'http://ha.test',grid_entity:'sensor.grid',solar_entity:'sensor.solar',house_entity:'',invert_grid:false,device_power_entities:{}},
    peugeot:{username:'',client_id:'',country:'fr',poll_interval_s:900,max_age_s:1800},ariston:{username:'',poll_interval_s:120,max_age_s:600}}
  delete (settings.home_assistant as Partial<typeof settings.home_assistant>).house_entity
  render(<SettingsPage settings={settings} connections={{home_assistant:true}} save={vi.fn()} run={async op=>{await op()}}/>)
  fireEvent.change(screen.getByLabelText('Entité consommation totale de la maison (facultatif)'),{target:{value:'sensor.house_total'}})
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer Home Assistant'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/home-assistant','PUT',{
    config:expect.objectContaining({house_entity:'sensor.house_total',grid_entity:'sensor.grid',solar_entity:'sensor.solar'}),token:null}))
})
