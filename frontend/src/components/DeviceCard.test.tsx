import {render,screen,cleanup} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {DeviceCard} from './DeviceCard'
import type {LiveDevice} from '../api/types'
afterEach(cleanup)
it('labels protocol estimates explicitly and hides unusable power',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_power:{value:0,quality:'estimated',measured_at:new Date().toISOString(),usable:true},
      observed_state:'Preparing',connected:true,temperature:null,target_temperature:null,fault:null},
    reason:'Observation',reservation_w:0,command:null,authorization:null} as LiveDevice
  const {rerender}=render(<DeviceCard device={device} onAction={()=>{}}/> )
  expect(screen.getByText('Puissance estimée · état OCPP')).toBeTruthy()
  rerender(<DeviceCard device={{...device,state:{...device.state,observed_power:{...device.state.observed_power!,value:3456,usable:false}}}} onAction={()=>{}}/> )
  expect(screen.queryByText('3,46 kW')).toBeNull()
})
