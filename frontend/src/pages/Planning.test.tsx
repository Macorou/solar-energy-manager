import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {Planning} from './Planning'
import {cloudDefaults} from '../components/Editors'
import type {Settings} from '../api/types'
afterEach(cleanup)
const initial={timezone:'Europe/Paris',devices:[{id:'ev',name:'Wallbox',kind:'charger',mode:'planned',priority:1,cloud:{...cloudDefaults}},
  {id:'tank',name:'Ariston NUOS',kind:'water_heater',mode:'off_peak_solar',priority:2,cloud:{...cloudDefaults}}],vehicles:[{id:'car',name:'Peugeot e-208'}],
  schedules:[{id:'work',name:'Travail',vehicle_id:'car',weekdays:[0,1,2,3,4],target_soc:80,deadline:'05:45',earliest_start:'22:00',solar_early:true,solar_horizon_hours:24,enabled:true}],
  off_peak:[{start:'22:00',end:'06:00',weekdays:[0,2,4]}],home_assistant:{grid_entity:'sensor.keep'},site_limit_w:12000} as Settings
const run=async(op:()=>Promise<unknown>)=>{await op()}
it('saves planning cards, HC weekdays, independent cloud values and priorities in one document',async()=>{
  const save=vi.fn().mockResolvedValue(undefined)
  render(<Planning settings={structuredClone(initial)} save={save} run={run}/> )
  fireEvent.change(screen.getByLabelText('Objectif de charge Travail (%)'),{target:{value:'85'}})
  fireEvent.change(screen.getByLabelText('Surplus pour démarrer · Ariston NUOS (W)'),{target:{value:'350'}})
  fireEvent.click(screen.getByRole('button',{name:'Monter la priorité Ariston NUOS'}))
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer le planning'}))
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  const saved=save.mock.calls[0][0] as Settings
  expect(saved.schedules[0]).toMatchObject({target_soc:85,solar_horizon_hours:24})
  expect(saved.off_peak[0].weekdays).toEqual([0,2,4])
  expect(saved.devices.find(d=>d.id==='tank')).toMatchObject({priority:1,cloud:{start_surplus_w:350}})
  expect(saved.devices.find(d=>d.id==='ev')?.cloud.start_surplus_w).toBe(0)
  expect(saved.home_assistant).toEqual(initial.home_assistant)
})
it('retains drafts across a refresh and merges unrelated newer settings',async()=>{
  const save=vi.fn().mockResolvedValue(undefined),view=render(<Planning settings={initial} save={save} run={run}/> )
  fireEvent.change(screen.getByLabelText('Objectif de charge Travail (%)'),{target:{value:'90'}})
  view.rerender(<Planning settings={{...initial,site_limit_w:10500,devices:initial.devices.map(d=>({...d,armed:true}))}} save={save} run={run}/> )
  expect((screen.getByLabelText('Objectif de charge Travail (%)') as HTMLInputElement).value).toBe('90')
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer le planning'}))
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][0]).toMatchObject({site_limit_w:10500,devices:[{armed:true},{armed:true}]})
})
it('creates several programmes and HC windows without writing before save',()=>{
  const save=vi.fn();render(<Planning settings={initial} save={save} run={run}/> )
  fireEvent.click(screen.getByRole('button',{name:'Créer un programme'}))
  fireEvent.click(screen.getByRole('button',{name:'Ajouter une plage HC'}))
  expect(screen.getAllByLabelText(/Nom du programme/)).toHaveLength(2)
  expect(screen.getAllByLabelText(/Début HC/)).toHaveLength(2)
  expect(save).not.toHaveBeenCalled()
})
it('does not resurrect an unchanged programme removed by a refreshed configuration',async()=>{
  const save=vi.fn().mockResolvedValue(undefined),view=render(<Planning settings={initial} save={save} run={run}/> )
  view.rerender(<Planning settings={{...initial,schedules:[]}} save={save} run={run}/> )
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer le planning'}))
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][0].schedules).toEqual([])
})
it('reports a conflict instead of recreating a programme deleted while it was edited',()=>{
  const save=vi.fn(),view=render(<Planning settings={initial} save={save} run={run}/> )
  fireEvent.change(screen.getByLabelText('Objectif de charge Travail (%)'),{target:{value:'90'}})
  view.rerender(<Planning settings={{...initial,schedules:[]}} save={save} run={run}/> )
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer le planning'}))
  expect(screen.getByRole('alert').textContent).toContain('supprimé')
  expect(save).not.toHaveBeenCalled()
})
