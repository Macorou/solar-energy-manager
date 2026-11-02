import {useEffect,useState} from 'react'
import {Icon} from './Icon'

type Theme='light'|'dark'
export function ThemeToggle(){
  const [theme,setTheme]=useState<Theme>(()=>{try{return localStorage.getItem('sem-theme')==='light'?'light':'dark'}catch{return 'dark'}})
  useEffect(()=>{document.documentElement.dataset.theme=theme},[theme])
  function toggle(){const next=theme==='dark'?'light':'dark';setTheme(next);try{localStorage.setItem('sem-theme',next)}catch{/* Keep the choice in memory when storage is blocked. */}}
  return <button type="button" className="theme-toggle" aria-label={'Passer au thème '+(theme==='dark'?'clair':'sombre')} onClick={toggle}>
    <Icon name={theme==='dark'?'sun':'moon'} size={20}/></button>
}
