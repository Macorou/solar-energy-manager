import {afterEach,expect,test,vi} from 'vitest'
import {render,screen} from '@testing-library/react'
import {Overview} from './Overview'
import type {Settings} from '../api/types'

const settings={devices:[],vehicles:[],timezone:'Europe/Paris',schedules:[],off_peak:[],priority:[]} as unknown as Settings

function mqtt(body:unknown,ok=true){
  vi.stubGlobal('fetch',vi.fn(async()=>({ok,json:async()=>body})))
}
function show(connections:Record<string,boolean>={home_assistant:true}){
  render(<Overview settings={settings} state={null} connections={connections} onAction={()=>{}} onNavigate={()=>{}}/>)
}
afterEach(()=>vi.unstubAllGlobals())

test('home assistant card reports an active MQTT publication with its last send',async()=>{
  mqtt({state:'connected',last_publish_at:'2026-11-02T13:42:00Z',error:null})
  show()
  expect(await screen.findByText('Envoi vers Home Assistant par MQTT · dernier envoi 14:42')).toBeTruthy()
  expect(screen.getByText('Accès enregistré')).toBeTruthy()
  expect(screen.queryByText(/prévue ensuite/)).toBeNull()
})

test('home assistant card says when MQTT publication is off or unreachable',async()=>{
  mqtt({state:'disabled',last_publish_at:null,error:null})
  const {unmount}=render(<Overview settings={settings} state={null} connections={{}} onAction={()=>{}} onNavigate={()=>{}}/>)
  expect(await screen.findByText('Envoi vers Home Assistant désactivé (MQTT).')).toBeTruthy()
  expect(screen.getByText('À connecter')).toBeTruthy()
  unmount()
  mqtt({state:'disconnected',last_publish_at:null,error:'refused'})
  show()
  expect(await screen.findByText('Envoi MQTT hors connexion : courtier injoignable.')).toBeTruthy()
})

test('home assistant card stays readable when the MQTT status cannot be read',async()=>{
  mqtt({detail:'Non authentifié'},false)
  show()
  expect(await screen.findByText('État de l’envoi MQTT indisponible.')).toBeTruthy()
})
