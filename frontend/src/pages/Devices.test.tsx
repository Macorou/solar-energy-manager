import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {Devices} from './Devices'
import type {Settings} from '../api/types'
afterEach(cleanup)

it('saves independent network and solar temperature targets',async()=>{
  const settings={devices:[{id:'tank',name:'NUOS',kind:'water_heater',mode:'off_peak_solar',armed:false,
    priority:2,min_power_w:700,max_power_w:2570,confirmation_timeout_s:300,gateway_id:'TEST',target:55,
    cloud:{start_surplus_w:0,start_delay_s:60,import_tolerance_w:0,stop_delay_s:180,min_run_s:0,restart_delay_s:60}}]} as Settings
  const save=vi.fn().mockResolvedValue(undefined)
  render(<Devices kind="water_heater" settings={settings} save={save} run={async op=>{await op()}}/>)
  fireEvent.click(screen.getByRole('button',{name:'Configurer'}))
  expect((screen.getByLabelText('Consigne sur le réseau (°C)') as HTMLInputElement).value).toBe('55')
  expect((screen.getByLabelText('Consigne sur surplus solaire (°C)') as HTMLInputElement).value).toBe('55')
  fireEvent.change(screen.getByLabelText('Consigne sur surplus solaire (°C)'),{target:{value:'70'}})
  fireEvent.submit(screen.getByRole('button',{name:'Enregistrer l’appareil'}).closest('form')!)
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][0].devices[0]).toMatchObject({target:55,solar_target:70})
})
