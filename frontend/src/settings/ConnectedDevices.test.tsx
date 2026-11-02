import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {ConnectedDevices} from './ConnectedDevices'
import {api} from '../api/client'
vi.mock('../api/client',async importOriginal=>({...await importOriginal<typeof import('../api/client')>(),api:vi.fn()}))
afterEach(()=>{cleanup();vi.clearAllMocks()})

const computer={id:'a1',device:'Chrome · Windows',ip:'192.168.1.20',created_at:'2026-11-01T08:00:00Z',last_seen_at:'2026-11-02T09:30:00Z',current:true}
const phone={id:'b2',device:'Safari · iPhone',ip:'192.168.1.31',created_at:'2026-10-20T18:00:00Z',last_seen_at:'2026-11-01T19:05:00Z',current:false}
const legacy={id:'c3',device:'Appareil inconnu',ip:'',created_at:null,last_seen_at:null,current:false}
const run=async(op:()=>Promise<unknown>)=>{await op()}

it('lists devices, marks the current one and only offers to disconnect the others',async()=>{
  vi.mocked(api).mockResolvedValue([computer,phone,legacy] as never)
  render(<ConnectedDevices run={run} timezone="Europe/Paris"/>)
  expect(await screen.findByText('Safari · iPhone')).toBeTruthy()
  expect(screen.getByText('Cet appareil')).toBeTruthy()
  expect(screen.getByText(/Connecté le 20\/10\/2026 20:00 · dernière activité le 01\/11\/2026 20:05 · 192\.168\.1\.31/)).toBeTruthy()
  expect(screen.getByText(/Connecté avant la version 0\.1\.32 · pas encore revu/)).toBeTruthy()
  expect(screen.queryByRole('button',{name:/Déconnecter Chrome/})).toBeNull()
  expect(screen.getAllByRole('button',{name:/^Déconnecter (Safari|Appareil)/})).toHaveLength(2)
})

it('disconnects one device then reloads the list',async()=>{
  vi.mocked(api).mockResolvedValueOnce([computer,phone] as never).mockResolvedValueOnce({ok:true} as never).mockResolvedValueOnce([computer] as never)
  render(<ConnectedDevices run={run} timezone="Europe/Paris"/>)
  fireEvent.click(await screen.findByRole('button',{name:'Déconnecter Safari · iPhone (192.168.1.31)'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/auth/sessions/b2','DELETE'))
  await waitFor(()=>expect(screen.queryByText('Safari · iPhone')).toBeNull())
})

it('disconnects every other device at once',async()=>{
  vi.mocked(api).mockResolvedValueOnce([computer,phone] as never).mockResolvedValueOnce({revoked:1} as never).mockResolvedValueOnce([computer] as never)
  render(<ConnectedDevices run={run} timezone="Europe/Paris"/>)
  fireEvent.click(await screen.findByRole('button',{name:'Déconnecter les autres appareils'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/auth/sessions/revoke-others','POST'))
  await waitFor(()=>expect(screen.queryByRole('button',{name:'Déconnecter les autres appareils'})).toBeNull())
})

it('shows an error when the list cannot be read',async()=>{
  vi.mocked(api).mockRejectedValue(new Error('Connexion requise'))
  render(<ConnectedDevices run={run} timezone="Europe/Paris"/>)
  expect((await screen.findByRole('alert')).textContent).toBe('Connexion requise')
})
