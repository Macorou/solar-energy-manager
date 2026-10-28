import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {SocReference} from './SocReference'
import {api} from '../api/client'
vi.mock('../api/client',()=>({api:vi.fn().mockResolvedValue({ok:true})}))
afterEach(()=>{cleanup();vi.clearAllMocks()})
it('binds an explicit current battery confirmation to this plug session',async()=>{
  render(<SocReference deviceId="ev" sessionId="current-plug"/> )
  const button=screen.getByRole('button',{name:'Confirmer pour cette recharge'}) as HTMLButtonElement
  expect(button.disabled).toBe(true)
  fireEvent.change(screen.getByLabelText('Pourcentage actuel confirmé (%)'),{target:{value:'78'}})
  fireEvent.click(button)
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/devices/ev/soc-reference','POST',{soc:78,session_id:'current-plug'}))
  expect(await screen.findByText('Référence enregistrée pour cette recharge.')).toBeTruthy()
})

it('can request a new meter reading while keeping confirmation a separate explicit action',async()=>{
  render(<SocReference deviceId="ev" sessionId="current-plug"/> )
  fireEvent.click(screen.getByRole('button',{name:'Actualiser le compteur de la borne'}))
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/devices/ev/meter-read','POST'))
  expect(api).not.toHaveBeenCalledWith('/devices/ev/soc-reference',expect.anything(),expect.anything())
})
