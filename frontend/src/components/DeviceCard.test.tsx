import {render,screen,cleanup,fireEvent} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
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

it('keeps immediate start unavailable until activation and sends the existing temporary manual action',()=>{
  const action=vi.fn()
  const device={config:{id:'pulsar',name:'Wallbox',kind:'charger',armed:false,mode:'solar',priority:1,default_soc_target:80},
    state:{observed_power:null,observed_state:'unknown',connected:false,temperature:null},
    reason:'En attente de mesures',reservation_w:0,command:null,authorization:null} as LiveDevice
  const {rerender}=render(<DeviceCard device={device} onAction={action}/>)
  const start=screen.getByRole('button',{name:'Charger maintenant'}) as HTMLButtonElement
  expect(start.disabled).toBe(true)
  fireEvent.click(start)
  expect(action).not.toHaveBeenCalled()
  rerender(<DeviceCard device={{...device,config:{...device.config,armed:true}}} onAction={action}/>)
  fireEvent.click(screen.getByRole('button',{name:'Charger maintenant'}))
  expect(action).toHaveBeenCalledExactlyOnceWith('pulsar','manual')
})

it('shows the last battery with its age without announcing an observed charge',()=>{
  const device={config:{id:'pulsar',name:'Wallbox',kind:'charger',armed:true,mode:'manual',priority:1,default_soc_target:80},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null},
    reason:'Commande en attente',reservation_w:3700,command:{status:'accepted',power_w:3700},authorization:null} as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc:62,range_km:180,fresh:false,measured_at:'2026-10-26T12:00:00Z'}} onAction={()=>{}}/>)
  expect(screen.getByText('En attente de confirmation')).toBeTruthy()
  expect(screen.queryByText('En charge')).toBeNull()
  expect(screen.getByText('62')).toBeTruthy()
  expect(screen.getByText('Donnée ancienne')).toBeTruthy()
  expect(screen.getByText(/Batterie relevée le/).textContent).toContain('26/10/2026')
  expect(screen.getByText(/Batterie relevée le/).textContent).toContain('13:00')
})

it.each([0,100])('shows a valid battery boundary %s even when old',soc=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null},
    reason:'Observation',reservation_w:0,command:null,authorization:null} as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc,range_km:180,fresh:false,measured_at:'2026-10-26T12:00:00Z'}} timezone="Europe/Paris" onAction={()=>{}}/>)
  expect(document.querySelector('.big-number')?.textContent).toBe(`${soc}%`)
  expect(screen.getByText('Donnée ancienne')).toBeTruthy()
  expect(screen.getByText(/Batterie relevée le/).textContent).toContain('13:00')
})

it.each([null,-1,101,NaN])('keeps an absent or invalid battery %s unknown',soc=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null},
    reason:'Observation',reservation_w:0,command:null,authorization:null} as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc,range_km:null,fresh:false,measured_at:null}} onAction={()=>{}}/>)
  expect(document.querySelector('.big-number')?.textContent).toBe('—%')
  expect(screen.queryByText('Donnée ancienne')).toBeNull()
})

it('shows a recent battery without an old-data warning',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null},
    reason:'Observation',reservation_w:0,command:null,authorization:null} as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc:75,range_km:214,fresh:true,measured_at:'2026-10-27T15:52:17Z'}} onAction={()=>{}}/>)
  expect(document.querySelector('.big-number')?.textContent).toBe('75%')
  expect(screen.queryByText('Donnée ancienne')).toBeNull()
  expect(screen.getByText(/Batterie relevée le/).textContent).toContain('16:52')
})

it.each([null,'invalid'])('keeps the last battery visible with an unknown date %s',measured_at=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null},
    reason:'Observation',reservation_w:0,command:null,authorization:null} as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc:75,range_km:214,fresh:false,measured_at}} onAction={()=>{}}/>)
  expect(document.querySelector('.big-number')?.textContent).toBe('75%')
  expect(screen.getByText('Date de mesure indisponible')).toBeTruthy()
})
