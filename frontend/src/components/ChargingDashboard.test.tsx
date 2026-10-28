import {render,screen,cleanup} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {Overview} from './Overview'
import {DeviceCard} from './DeviceCard'
import {watts} from '../api/client'
import type {LiveDevice,LiveState,Settings} from '../api/types'
afterEach(cleanup)

it('renders W below 1000 and kW from 1000 on the actual overview cards',()=>{
  const settings={devices:[],site_limit_w:12000,timezone:'Europe/Paris',schedules:[],off_peak:[]} as unknown as Settings
  const s=(value:number)=>({value,usable:true,quality:'fresh',measured_at:new Date().toISOString()})
  const state={devices:[],grid:s(400),solar:s(0),house_configured:true,house:s(1250),errors:{},vehicles:{}} as unknown as LiveState
  render(<Overview settings={settings} state={state} connections={{}} onAction={()=>{}} onNavigate={()=>{}}/>)
  expect(screen.getByText('400 W')).toBeTruthy()
  expect(screen.getByText('1,25 kW')).toBeTruthy()
})

it.each([[0,'0 W'],[999,'999 W'],[1000,'1 kW'],[-1250,'-1,25 kW'],[NaN,'—']])('formats electrical magnitude %s as %s',(input,want)=>{
  expect(watts(input as number)).toBe(want)
})

it('shows an estimated SOC with measured session energy cost and solar allocation even in observation',()=>{
  const device={config:{id:'ev',name:'Wallbox',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_state:'SuspendedEVSE',connected:true,vehicle_connected:true,observed_power:null},
    reason:'Attente du planning',command:null,authorization:null,
    charging:{active:true,energy_kwh:12.5,cost_eur:1.24,cost_partial:false,solar_percent:60,soc:78,soc_estimated:true,soc_usable:true,effective_price_per_kwh:.08}} as unknown as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc:75,range_km:214,fresh:false,measured_at:'2026-10-28T06:00:00Z'}} onAction={()=>{}}/>)
  expect(document.querySelector('.big-number')?.textContent).toBe('78%')
  expect(screen.getByText('Batterie estimée')).toBeTruthy()
  expect(screen.getByText('12,5 kWh')).toBeTruthy()
  expect(screen.getByText(/1,24/)).toBeTruthy()
  expect(screen.getByText('60 %')).toBeTruthy()
  expect(screen.getByText(/Voiture : En attente de charge/)).toBeTruthy()
  expect(screen.getByText('Observation')).toBeTruthy()
})

it('never interprets an offline charger as a physically disconnected car',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:false,priority:1},
    state:{observed_state:'Available',connected:false,vehicle_connected:false},reason:'Offline',command:null} as unknown as LiveDevice
  render(<DeviceCard device={device} onAction={()=>{}}/>)
  expect(screen.getByText(/Voiture : État inconnu · borne hors connexion/)).toBeTruthy()
  expect(screen.queryByText(/Voiture : Débranchée/)).toBeNull()
})

it('shows the last Peugeot battery without requesting a manually confirmed percentage',()=>{
  const device={config:{id:'ev',name:'Wallbox',kind:'charger',armed:false,priority:1,default_soc_target:80},
    state:{observed_state:'Preparing',connected:true,vehicle_connected:true,observed_power:null},
    reason:'Attente du planning',command:null,authorization:null,
    charging:{id:'plug',active:true,energy_kwh:0,cost_eur:0,cost_partial:false,solar_percent:null,
      soc:75,soc_estimated:true,soc_usable:true,soc_reference_missing:true,effective_price_per_kwh:null}} as unknown as LiveDevice
  render(<DeviceCard device={device} telemetry={{soc:75,fresh:false,range_km:214,measured_at:'2026-10-26T15:52:17Z'}} onAction={()=>{}}/>)
  expect(document.querySelector('.big-number')?.textContent).toBe('75%')
  expect(screen.queryByRole('spinbutton')).toBeNull()
  expect(screen.queryByRole('button',{name:'Confirmer pour cette recharge'})).toBeNull()
})

it('shows the manual default target rather than the unrelated scheduled target and deadline',()=>{
  const device={config:{id:'ev',name:'EV',kind:'charger',armed:true,mode:'manual',priority:1,default_soc_target:80},
    state:{observed_state:'Preparing',connected:true,vehicle_connected:true},reason:'Commande manuelle',command:null,
    authorization:{target_soc:90,expires_at:'2026-10-28T05:45:00Z'}} as unknown as LiveDevice
  render(<DeviceCard device={device} onAction={()=>{}}/>)
  expect(screen.getByText('Objectif 80 %')).toBeTruthy()
  expect(screen.queryByText(/Objectif 90/)).toBeNull()
})
