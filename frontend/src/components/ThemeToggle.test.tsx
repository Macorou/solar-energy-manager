import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {ThemeToggle} from './ThemeToggle'

afterEach(()=>{cleanup();localStorage.clear();delete document.documentElement.dataset.theme;vi.restoreAllMocks()})
it('restores the chosen theme and persists switching across remounts',()=>{
  localStorage.setItem('sem-theme','light')
  const view=render(<ThemeToggle/> )
  expect(document.documentElement.dataset.theme).toBe('light')
  fireEvent.click(screen.getByRole('button',{name:'Passer au thème sombre'}))
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(localStorage.getItem('sem-theme')).toBe('dark')
  view.unmount();render(<ThemeToggle/> )
  expect(screen.getByRole('button',{name:'Passer au thème clair'})).toBeTruthy()
})
it('allows theme switching when browser storage is unavailable',()=>{
  vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw Error('blocked')})
  vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw Error('blocked')})
  render(<ThemeToggle/> )
  fireEvent.click(screen.getByRole('button',{name:'Passer au thème clair'}))
  expect(document.documentElement.dataset.theme).toBe('light')
})
