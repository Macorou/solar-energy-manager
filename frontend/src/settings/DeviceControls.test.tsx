import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {DeviceControls} from './DeviceControls'
import {api} from '../api/client'
import type {Device} from '../api/types'
vi.mock('../api/client',()=>({api:vi.fn().mockResolvedValue({supported:['start','suspend']})}))
afterEach(()=>{cleanup();vi.clearAllMocks()})
it('requires all three attestations before activation from Settings',async()=>{
  render(<DeviceControls device={{id:'ev',name:'Wallbox',kind:'charger',armed:false} as Device} run={async op=>{await op()}} onRemoved={()=>{}}/> )
  fireEvent.click(screen.getByRole('button',{name:'Activer le pilotage'}))
  const confirm=screen.getByRole('button',{name:'Confirmer l’activation'}) as HTMLButtonElement
  expect(confirm.disabled).toBe(true)
  expect(api).not.toHaveBeenCalled()
  screen.getAllByRole('checkbox').forEach(n=>fireEvent.click(n))
  fireEvent.click(confirm)
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/chargers/ev/arm','POST',{confirm_control:true,capabilities_verified:true,offline_behavior_verified:true}))
})
