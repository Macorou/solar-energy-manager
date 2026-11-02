import {useEffect,useRef,useState} from 'react'
import {Icon} from '../components/Icon'

export function ZonePicker({areas,selected,onChange}:{areas:string[];selected:string[]|null;onChange:(next:string[]|null)=>void}){
  const [open,setOpen]=useState(false)
  const root=useRef<HTMLDivElement>(null),button=useRef<HTMLButtonElement>(null)
  useEffect(()=>{
    if(!open)return
    function outside(e:PointerEvent){if(!root.current?.contains(e.target as Node))setOpen(false)}
    function escape(e:KeyboardEvent){if(e.key==='Escape'){setOpen(false);button.current?.focus()}}
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape)
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape)}
  },[open])
  const label=selected===null?'Toutes les zones':selected.length===1?'1 zone':`${selected.length} zones`
  return <div className="journal-zones" ref={root}>
    <button type="button" ref={button} aria-expanded={open} aria-controls="journal-zone-list" onClick={()=>setOpen(!open)}>{label}<Icon name="down" size={16}/></button>
    {open&&<div id="journal-zone-list" className="journal-zone-list" role="group" aria-label="Filtrer les zones">
      <label><input type="checkbox" checked={selected===null} onChange={e=>onChange(e.target.checked?null:[])}/>Toutes les zones</label>
      {areas.map(area=><label key={area}><input type="checkbox" checked={selected===null||selected.includes(area)} onChange={e=>{
        const prior=selected===null?areas:selected
        onChange(e.target.checked?[...prior,area]:prior.filter(a=>a!==area))
      }}/><span>{area}</span></label>)}
      {!areas.length&&<p>Aucune zone enregistrée.</p>}
    </div>}
  </div>
}
