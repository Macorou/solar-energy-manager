import {render,screen,cleanup,within} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {ScheduleTimeline} from './ScheduleTimeline'
import type {Program} from '../api/types'

afterEach(cleanup)
it('distinguishes the car deadline day from the hot water start day across midnight',()=>{
  const program:Program={id:'monday',name:'Travail',vehicle_id:'car',weekdays:[0],earliest_start:'22:00',
    deadline:'06:00',target_soc:80,solar_early:true,solar_horizon_hours:24,enabled:true}
  render(<ScheduleTimeline settings={{schedules:[program],off_peak:[{start:'22:00',end:'06:00',weekdays:[0]}]}} onOpen={()=>{}}/>)
  const rows=screen.getAllByRole('listitem')
  expect(within(rows[0]).getByText(/début la veille · échéance lun\./)).toBeTruthy()
  expect(within(rows[0]).queryByText(/fin le lendemain/)).toBeNull()
  expect(within(rows[1]).getByText(/fin le lendemain · début lun\./)).toBeTruthy()
})
