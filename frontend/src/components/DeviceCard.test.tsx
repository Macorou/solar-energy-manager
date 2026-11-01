import {render,screen,cleanup,fireEvent} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {DeviceCard} from './DeviceCard'
import type {LiveDevice} from '../api/types'
afterEach(cleanup)
it('shows the effective solar temperature rather than the network setting',()=>{
  const device={config:{id:'tank',name:'NUOS',kind:'water_heater',target:55,solar_target:70,armed:true,priority:2,mode:'off_peak_solar'},
    state:{observed_power:null,observed_state:'on',connected:true,temperature:60},
    effective_target:70,target_source:'solar',reason:'Surplus solaire',command:null,authorization:null} as unknown as LiveDevice
  render(<DeviceCard device={device} onAction={()=>{}}/>)
  expect(screen.getByText('Objectif 70 °C · solaire')).toBeTruthy()
  expect(screen.queryByText('Objectif 55 °C')).toBeNull()
})
it('shows the warning when the planned grid window is too short',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:true,priority:1,default_soc_target:80,mode:'planned'},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null,target_temperature:null,fault:null},
    reason:'Solaire avant le créneau réseau',reservation_w:0,command:null,authorization:{target_soc:80,expires_at:null},
    plan_warning:'Objectif 80 % probablement non atteint à 05:45'} as LiveDevice
  render(<DeviceCard device={device} onAction={()=>{}}/>)
  expect(screen.getByText('Objectif 80 % probablement non atteint à 05:45')).toBeTruthy()
})
it('shows the solar target above the car target',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:true,priority:1,default_soc_target:80,solar_target:100,mode:'planned'},
    state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null,target_temperature:null,fault:null},
    reason:'Surplus solaire',reservation_w:0,command:null,authorization:{target_soc:80,expires_at:null}} as LiveDevice
  const {rerender}=render(<DeviceCard device={device} onAction={()=>{}}/>)
  expect(screen.getByText(/surplus jusqu’à 100 %/)).toBeTruthy()
  rerender(<DeviceCard device={{...device,config:{...device.config,mode:'manual'}}} onAction={()=>{}}/>)
  expect(screen.queryByText(/surplus jusqu’à/)).toBeNull()
})
it('retains reported power between updates without confirming a charge from cached power',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_power:{value:3456,quality:'estimated',measured_at:new Date().toISOString(),usable:true},
      observed_state:'Preparing',connected:true,temperature:null,target_temperature:null,fault:null},
    reason:'Observation',reservation_w:0,command:null,authorization:null} as LiveDevice
  const {rerender}=render(<DeviceCard device={device} onAction={()=>{}}/> )
  expect(screen.getByText('Puissance estimée · état OCPP')).toBeTruthy()
  rerender(<DeviceCard device={{...device,state:{...device.state,observed_power:{...device.state.observed_power!,value:3456,usable:false}}}} onAction={()=>{}}/> )
  expect(screen.getByText('3,46 kW')).toBeTruthy()
  rerender(<DeviceCard device={{...device,state:{...device.state,observed_power:null}}} onAction={()=>{}}/> )
  expect(screen.getByText('3,46 kW')).toBeTruthy()
  expect(screen.getByText('Puissance estimée · état OCPP')).toBeTruthy()
  expect(screen.queryByText('En charge')).toBeNull()
  rerender(<DeviceCard device={{...device,state:{...device.state,observed_power:{...device.state.observed_power!,value:0}}}} onAction={()=>{}}/> )
  expect(screen.getByText('0 W')).toBeTruthy()
})

it('keeps immediate start unavailable until activation and sends the manual action',()=>{
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
