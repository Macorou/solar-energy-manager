import {render,screen,cleanup} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {TempoStatus} from './TempoStatus'
afterEach(cleanup)
it('shows the colour and the red peak pill',()=>{
  render(<TempoStatus tempo={{configured:true,color:'rouge',red_peak:true,unknown:false}}/>)
  expect(screen.getByText('Tempo : Rouge')).toBeTruthy()
  expect(screen.getByText('Heures pleines rouges : pas de réseau en automatique')).toBeTruthy()
})
it('shows an unknown colour',()=>{
  render(<TempoStatus tempo={{configured:true,color:null,red_peak:false,unknown:true}}/>)
  expect(screen.getByText('Couleur Tempo inconnue')).toBeTruthy()
  expect(screen.queryByText(/Tempo :/)).toBeNull()
})
it('shows nothing when not configured',()=>{
  const {container}=render(<TempoStatus tempo={{configured:false,color:null,red_peak:false,unknown:false}}/>)
  expect(container.textContent).toBe('')
  const b=render(<TempoStatus/>);expect(b.container.textContent).toBe('')
})
it('shows Bleu without pill',()=>{
  render(<TempoStatus tempo={{configured:true,color:'bleu',red_peak:false,unknown:false}}/>)
  expect(screen.getByText('Tempo : Bleu')).toBeTruthy();expect(screen.queryByText(/pas de réseau/)).toBeNull()
})
