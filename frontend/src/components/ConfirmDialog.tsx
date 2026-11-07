import {useEffect,useId,useRef} from 'react'
import {createPortal} from 'react-dom'

export function ConfirmDialog({title,text,onCancel,onConfirm}:{title:string;text:string;onCancel:()=>void;onConfirm:()=>void}) {
  const ref=useRef<HTMLDialogElement>(null),cancel=useRef<HTMLButtonElement>(null),heading=useId(),body=useId()
  useEffect(()=>{const dialog=ref.current!,previous=document.activeElement as HTMLElement|null
    if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','')
    cancel.current?.focus()
    return()=>{if(dialog.close)dialog.close();previous?.focus()}
  },[])
  return createPortal(<dialog ref={ref} className="settings-dialog confirm-dialog" aria-labelledby={heading} aria-describedby={body} onCancel={e=>{e.preventDefault();onCancel()}}>
    <div className="settings-dialog-body"><h2 id={heading}>{title}</h2><p id={body}>{text}</p></div>
    <footer className="settings-dialog-foot confirm-actions"><button type="button" ref={cancel} onClick={onCancel}>Annuler</button>
      <button type="button" className="primary" onClick={onConfirm}>Continuer</button></footer>
  </dialog>,document.body)
}
