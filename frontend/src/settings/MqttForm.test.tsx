import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import type {Settings} from '../api/types'
import {ConnectionForm} from './ConnectionForm'
import {api} from '../api/client'
vi.mock('../api/client',()=>({api:vi.fn().mockResolvedValue({ok:true})}))
afterEach(()=>{cleanup();vi.clearAllMocks();vi.restoreAllMocks()})
const mqtt={broker:'192.168.1.30:1883',topic:'sem',client_id:'',username:'sem',allow_self_signed:false,tls:false,discovery_prefix:'homeassistant'}
const initial={devices:[],vehicles:[],schedules:[],off_peak:[],mqtt,site_limit_w:12000,timezone:'Europe/Paris'} as unknown as Settings
const run=async(op:()=>Promise<unknown>,_message?:string)=>{await op()}
const show=(connections:Record<string,boolean>={mqtt:true},runner:typeof run=run)=>render(<ConnectionForm section="mqtt" settings={initial} save={vi.fn()} run={runner} connections={connections}/>)
it('saves the config with the password then empties the field',async()=>{
  show()
  const password=screen.getByLabelText('Mot de passe') as HTMLInputElement
  expect(password.value).toBe('');expect(password.placeholder).toBe('Conservé si vide')
  fireEvent.change(screen.getByLabelText('Courtier'),{target:{value:'broker.local:8883'}})
  fireEvent.change(password,{target:{value:'secret'}})
  fireEvent.click(screen.getByLabelText('Autoriser les certificats auto-signés'))
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/mqtt','PUT',{config:{...mqtt,broker:'broker.local:8883',allow_self_signed:true},password:'secret'}))
  await waitFor(()=>expect(password.value).toBe(''))
})
it('sends a null password when left blank',async()=>{
  show();fireEvent.click(screen.getByRole('button',{name:'Enregistrer'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/mqtt','PUT',{config:mqtt,password:null}))
})
it('shows the labels, hints and advanced settings',()=>{
  show({})
  expect((screen.getByLabelText('Mot de passe') as HTMLInputElement).placeholder).toBe('')
  expect(screen.getByText('Exemple : 192.168.1.30:1883')).toBeTruthy()
  expect(screen.getByText('Laisser vide pour désactiver la publication.')).toBeTruthy()
  const selfSigned=screen.getByLabelText('Autoriser les certificats auto-signés')
  expect(selfSigned.getAttribute('aria-describedby')).toBe('mqtt-self-signed-hint')
  expect(document.getElementById('mqtt-self-signed-hint')?.textContent).toBe("Sans effet si la connexion chiffrée (TLS) n'est pas activée dans les paramètres avancés.")
  expect((screen.getByLabelText('Identifiant client') as HTMLInputElement).placeholder).toBe('sem-[aléatoire]')
  expect(screen.getByLabelText('Nom d\'utilisateur')).toBeTruthy()
  expect(screen.getByText('Paramètres avancés').closest('details')).toBeTruthy()
  expect(screen.getByLabelText('Connexion chiffrée (TLS)')).toBeTruthy();expect(screen.getByLabelText('Préfixe de découverte Home Assistant')).toBeTruthy()
})
it('tests the connection and reports success',async()=>{
  const runner=vi.fn(run);show({mqtt:true},runner as typeof run)
  fireEvent.click(screen.getByRole('button',{name:'Tester'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/mqtt/test','POST',{config:mqtt,password:null}))
  expect(runner).toHaveBeenCalledWith(expect.any(Function),'Connexion MQTT réussie')
})
it('asks for confirmation before deleting and explains a manual cleanup',async()=>{
  vi.mocked(api).mockResolvedValue({ok:true,entities_removed:false} as never)
  const confirm=vi.spyOn(window,'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
  show()
  fireEvent.click(screen.getByRole('button',{name:'Supprimer'}))
  expect(confirm).toHaveBeenCalledWith('Supprimer la connexion MQTT ?');expect(api).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'Supprimer'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/mqtt','DELETE'))
  expect((await screen.findByRole('status')).textContent).toBe('Connexion supprimée : entités à supprimer à la main dans Home Assistant (courtier injoignable)')
  expect((screen.getByLabelText('Courtier') as HTMLInputElement).value).toBe('')
})
it('confirms a normal deletion',async()=>{
  vi.mocked(api).mockResolvedValue({ok:true,entities_removed:true} as never)
  vi.spyOn(window,'confirm').mockReturnValue(true);show()
  fireEvent.click(screen.getByRole('button',{name:'Supprimer'}))
  expect((await screen.findByRole('status')).textContent).toBe('Connexion MQTT supprimée')
})
it('resets the whole form to the server defaults after a deletion',async()=>{
  vi.mocked(api).mockResolvedValue({ok:true,entities_removed:true} as never)
  vi.spyOn(window,'confirm').mockReturnValue(true)
  const custom={...initial,mqtt:{...mqtt,topic:'',discovery_prefix:'ha2',tls:true}} as Settings
  const props={save:vi.fn(),run,connections:{mqtt:true}},view=render(<ConnectionForm section="mqtt" settings={custom} {...props}/>)
  fireEvent.change(screen.getByLabelText('Mot de passe'),{target:{value:'secret'}})
  fireEvent.click(screen.getByRole('button',{name:'Supprimer'}))
  await screen.findByRole('status')
  // The app refreshes settings from the server after a run: it now holds the defaults
  view.rerender(<ConnectionForm section="mqtt" settings={{...custom,mqtt:{broker:'',topic:'sem',client_id:'',username:'',allow_self_signed:false,tls:false,discovery_prefix:'homeassistant'}} as Settings} {...props}/>)
  expect((screen.getByLabelText('Sujet') as HTMLInputElement).value).toBe('sem')
  expect((screen.getByLabelText('Préfixe de découverte Home Assistant') as HTMLInputElement).value).toBe('homeassistant')
  expect((screen.getByLabelText('Connexion chiffrée (TLS)') as HTMLInputElement).checked).toBe(false)
  expect((screen.getByLabelText('Mot de passe') as HTMLInputElement).value).toBe('')
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/connections/mqtt','PUT',{config:{broker:'',topic:'sem',client_id:'',username:'',allow_self_signed:false,tls:false,discovery_prefix:'homeassistant'},password:null}))
})
it('warns and stays open when a save that disables publication could not remove the entities',async()=>{
  vi.mocked(api).mockResolvedValue({ok:true,entities_removed:false} as never)
  const onSaved=vi.fn()
  render(<ConnectionForm section="mqtt" settings={initial} save={vi.fn()} run={run} connections={{mqtt:true}} onSaved={onSaved}/>)
  fireEvent.change(screen.getByLabelText('Sujet'),{target:{value:''}})
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer'}))
  expect((await screen.findByRole('status')).textContent).toBe('Connexion enregistrée : entités à supprimer à la main dans Home Assistant (courtier injoignable)')
  expect(onSaved).not.toHaveBeenCalled()
})
it('closes normally after a save that reports entities removed or no information',async()=>{
  vi.mocked(api).mockResolvedValue({ok:true,entities_removed:null} as never)
  const onSaved=vi.fn()
  render(<ConnectionForm section="mqtt" settings={initial} save={vi.fn()} run={run} connections={{mqtt:true}} onSaved={onSaved}/>)
  fireEvent.click(screen.getByRole('button',{name:'Enregistrer'}))
  await waitFor(()=>expect(onSaved).toHaveBeenCalledOnce());expect(screen.queryByRole('status')).toBeNull()
})
