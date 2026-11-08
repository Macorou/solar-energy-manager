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
  expect(action).toHaveBeenCalledExactlyOnceWith('pulsar','manual',240)
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

const carDevice={config:{id:'ev',name:'EV',kind:'charger',armed:true,priority:1,default_soc_target:80,mode:'planned'},
  state:{observed_power:null,observed_state:'Preparing',connected:true,temperature:null,target_temperature:null,fault:null},
  reason:'x',reservation_w:0,command:null,authorization:null} as LiveDevice
const tankDevice={config:{id:'tank',name:'NUOS',kind:'water_heater',target:55,armed:true,priority:2,mode:'off_peak_solar'},
  state:{observed_power:null,observed_state:'off',connected:true,temperature:50},reason:'x',command:null,authorization:null} as unknown as LiveDevice
const red={configured:true,color:'rouge' as const,red_peak:true,unknown:false}
it('offers 12 durations, 4 h by default, and sends the chosen duration',()=>{
  localStorage.clear();const action=vi.fn()
  render(<DeviceCard device={carDevice} onAction={action}/>)
  const select=screen.getByLabelText('Durée du mode manuel') as HTMLSelectElement
  expect(select.options.length).toBe(12);expect(select.value).toBe('240')
  expect([...select.options].map(o=>o.text)).toEqual(Array.from({length:12},(_,i)=>(i+1)+' h'))
  fireEvent.click(screen.getByRole('button',{name:'Manuel'}))
  expect(action).toHaveBeenCalledWith('ev','manual',240)
  fireEvent.change(select,{target:{value:'420'}})
  fireEvent.click(screen.getByRole('button',{name:'Charger maintenant'}))
  expect(action).toHaveBeenLastCalledWith('ev','manual',420)
  expect(screen.queryByRole('dialog')).toBeNull()
})
it('remembers the last duration per car',()=>{
  localStorage.setItem('sem.manualHours.ev','9')
  render(<DeviceCard device={carDevice} onAction={()=>{}}/>)
  expect((screen.getByLabelText('Durée du mode manuel') as HTMLSelectElement).value).toBe('540')
  fireEvent.change(screen.getByLabelText('Durée du mode manuel'),{target:{value:'120'}})
  expect(localStorage.getItem('sem.manualHours.ev')).toBe('2')
})
it('asks for confirmation on a red peak before a manual start',()=>{
  localStorage.clear();const action=vi.fn()
  render(<DeviceCard device={carDevice} tempo={red} onAction={action}/>)
  fireEvent.click(screen.getByRole('button',{name:'Manuel'}))
  expect(screen.getByRole('dialog',{name:'Jour rouge Tempo'})).toBeTruthy()
  expect(screen.getByText('Heures pleines d’un jour rouge : cette charge sera payée au tarif le plus cher. Continuer ?')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Annuler'}))
  expect(action).not.toHaveBeenCalled();expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'Charger maintenant'}))
  fireEvent.click(screen.getByRole('button',{name:'Continuer'}))
  expect(action).toHaveBeenCalledExactlyOnceWith('ev','manual',240)
})
it('offers the water heater 30 min to 4 h, 30 min by default, and sends the chosen duration',()=>{
  localStorage.clear();const action=vi.fn()
  render(<DeviceCard device={tankDevice} onAction={action}/>)
  const select=screen.getByLabelText('Durée du mode manuel') as HTMLSelectElement
  expect([...select.options].map(o=>o.text)).toEqual(['30 min','1 h','1 h 30','2 h','3 h','4 h']);expect(select.value).toBe('30')
  fireEvent.click(screen.getByRole('button',{name:'Chauffer maintenant'}))
  expect(action).toHaveBeenLastCalledWith('tank','manual',30)
  fireEvent.change(select,{target:{value:'90'}})
  expect(localStorage.getItem('sem.manualMinutes.tank')).toBe('90')
  fireEvent.click(screen.getByRole('button',{name:'Manuel'}))
  expect(action).toHaveBeenLastCalledWith('tank','manual',90)
})
it('ignores a stored water heater duration outside the list',()=>{
  localStorage.setItem('sem.manualMinutes.tank','45')
  render(<DeviceCard device={tankDevice} onAction={()=>{}}/>)
  expect((screen.getByLabelText('Durée du mode manuel') as HTMLSelectElement).value).toBe('30')
})
it('confirms the water heater on a red peak with its own wording',()=>{
  localStorage.clear();const action=vi.fn()
  render(<DeviceCard device={tankDevice} tempo={red} onAction={action}/>)
  fireEvent.click(screen.getByRole('button',{name:'Chauffer maintenant'}))
  expect(screen.getByText('Heures pleines d’un jour rouge : cette chauffe sera payée au tarif le plus cher. Continuer ?')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Continuer'}))
  expect(action).toHaveBeenCalledExactlyOnceWith('tank','manual',30)
})
it('shows when the water heater Manual ends',()=>{
  render(<DeviceCard device={{...tankDevice,config:{...tankDevice.config,mode:'manual'},manual_until:'2026-11-06T13:30:00Z'} as LiveDevice} timezone="Europe/Paris" onAction={()=>{}}/>)
  expect(screen.getByText(/Manuel jusqu’à 14:30/)).toBeTruthy()
})
const manualCar={...carDevice,config:{...carDevice.config,mode:'manual'},manual_until:'2026-11-06T13:30:00Z'} as LiveDevice
it('shows when the car Manual ends, in the user timezone',()=>{
  render(<DeviceCard device={manualCar} timezone="Europe/Paris" onAction={()=>{}}/>)
  expect(screen.getByText(/Manuel jusqu’à 14:30/)).toBeTruthy()
  cleanup();render(<DeviceCard device={carDevice} timezone="Europe/Paris" onAction={()=>{}}/>)
  expect(screen.queryByText(/Manuel jusqu’à/)).toBeNull()
})
it('changes the duration of a running Manual at once',()=>{
  localStorage.clear();const action=vi.fn()
  const {rerender}=render(<DeviceCard device={carDevice} onAction={action}/>)
  fireEvent.change(screen.getByLabelText('Durée du mode manuel'),{target:{value:'300'}})
  expect(action).not.toHaveBeenCalled()   // outside Manual, the choice only applies to the next start
  rerender(<DeviceCard device={manualCar} onAction={action}/>)
  fireEvent.change(screen.getByLabelText('Durée du mode manuel'),{target:{value:'360'}})
  expect(action).toHaveBeenCalledExactlyOnceWith('ev','manual',360)
  expect((screen.getByLabelText('Durée du mode manuel') as HTMLSelectElement).value).toBe('360')
})
it('confirms a duration change of a running Manual on a red peak',()=>{
  localStorage.clear();const action=vi.fn()
  render(<DeviceCard device={manualCar} tempo={red} onAction={action}/>)
  const select=()=>screen.getByLabelText('Durée du mode manuel') as HTMLSelectElement
  fireEvent.change(select(),{target:{value:'480'}})
  expect(screen.getByRole('dialog',{name:'Jour rouge Tempo',description:/tarif le plus cher/})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Annuler'}))
  expect(action).not.toHaveBeenCalled();expect(select().value).toBe('240')
  fireEvent.change(select(),{target:{value:'480'}})
  fireEvent.click(screen.getByRole('button',{name:'Continuer'}))
  expect(action).toHaveBeenCalledExactlyOnceWith('ev','manual',480);expect(select().value).toBe('480')
})
