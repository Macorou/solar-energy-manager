import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {SessionTable} from './SessionTable'
import type {SessionPage} from './types'

afterEach(cleanup)
const data={items:[{id:'legacy',started_at:'2026-10-29T16:12:00Z',vehicle_name:'Peugeot e-208',device_name:'Wallbox',energy_kwh:13.76,energy_partial:true,cost_eur:1.9,cost_partial:true,solar_percent:null,charge_duration_s:null,duration_partial:true}],total:1,page:1,page_size:25,available:{cost:true},timezone:'Europe/Paris',totals:{energy_kwh:13.76,energy_partial:true,cost_eur:null,known_cost_eur:1.9,cost_partial:true,solar_percent:null}} as unknown as SessionPage

it('offers Chargé and Coût on both mobile metric selectors for partial sessions',()=>{
  render(<SessionTable data={data} sort="date" direction="desc" onSort={vi.fn()} onPage={vi.fn()} onOpen={vi.fn()}/>)
  const second=screen.getByRole('combobox',{name:'Colonne mobile'})
  expect(within(second).getByRole('option',{name:'Chargé'})).toBeTruthy()
  expect(within(second).getByRole('option',{name:'Coût'})).toBeTruthy()
  fireEvent.change(second,{target:{value:'cost'}})
  expect(screen.getAllByText('1,90 €').length).toBeGreaterThan(0)
  const first=screen.getByRole('combobox',{name:'Première colonne mobile'})
  fireEvent.change(first,{target:{value:'duration'}})
  fireEvent.change(second,{target:{value:'energy'}})
  expect((within(second).getByRole('option',{name:'Chargé'}) as HTMLOptionElement).selected).toBe(true)
})

it('flags a solar share computed on part of the session',()=>{
  const items=[{...data.items[0],solar_percent:40,solar_partial:true}]
  render(<SessionTable data={{...data,items,totals:{...data.totals,solar_percent:40,solar_partial:true}}} sort="date" direction="desc" onSort={vi.fn()} onPage={vi.fn()} onOpen={vi.fn()}/>)
  const cells=screen.getAllByText('40 %').map(value=>value.parentElement!)
  expect(cells.length).toBeGreaterThan(0)
  for(const cell of cells)expect(within(cell).getByText('Partielle')).toBeTruthy()
})

it('keeps the cost column available with no price without inventing zero',()=>{
  render(<SessionTable data={{...data,available:{cost:false},items:[{...data.items[0],cost_eur:null}],totals:{...data.totals,known_cost_eur:null}}} sort="date" direction="desc" onSort={vi.fn()} onPage={vi.fn()} onOpen={vi.fn()}/>)
  const second=screen.getByRole('combobox',{name:'Colonne mobile'})
  expect(within(second).getByRole('option',{name:'Coût'})).toBeTruthy()
  fireEvent.change(second,{target:{value:'cost'}})
  expect(screen.queryByText('0,00 €')).toBeNull()
})
