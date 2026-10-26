import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {ChargeProgramEditor,CloudSettingsForm} from './Editors'
afterEach(cleanup)
it('saves a weekday target with previous evening start and solar horizon',()=>{
  const save=vi.fn()
  render(<ChargeProgramEditor vehicles={[{id:'car',name:'e-208'}]} onSave={save}/> )
  fireEvent.change(screen.getByLabelText('Nom du programme'),{target:{value:'Travail'}})
  fireEvent.change(screen.getByLabelText('Début réseau autorisé'),{target:{value:'22:00'}})
  fireEvent.change(screen.getByLabelText('Prêt à'),{target:{value:'05:45'}})
  fireEvent.click(screen.getByText('Enregistrer le programme'))
  expect(save.mock.calls[0][0]).toMatchObject({vehicle_id:'car',weekdays:[0,1,2,3,4],target_soc:80,
    earliest_start:'22:00',deadline:'05:45',solar_horizon_hours:24})
})
it('edits cloud watts and delays independently',()=>{
  const change=vi.fn()
  render(<CloudSettingsForm value={{start_surplus_w:1500,start_delay_s:60,import_tolerance_w:100,
    stop_delay_s:180,min_run_s:300,restart_delay_s:120}} onChange={change}/> )
  fireEvent.change(screen.getByLabelText('Tolérance réseau (W)'),{target:{value:'250'}})
  expect(change.mock.calls[0][0]).toMatchObject({import_tolerance_w:250,stop_delay_s:180,start_delay_s:60})
})
