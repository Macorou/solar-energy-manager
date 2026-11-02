import {useEffect,useId,useRef,type ReactNode} from 'react'
import {createPortal} from 'react-dom'
import {Icon} from '../components/Icon'

export function SettingsDialog({title,onClose,pending,error,message,children}:{title:string;onClose:()=>void;pending:boolean;error:string;message:string;children:ReactNode}){
  const ref=useRef<HTMLDialogElement>(null),heading=useId()
  useEffect(()=>{const dialog=ref.current!,previous=document.activeElement as HTMLElement|null
    if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','')
    return()=>{if(dialog.close)dialog.close();previous?.focus()}
  },[])
  return createPortal(<dialog ref={ref} className="settings-dialog" aria-labelledby={heading} onCancel={e=>{e.preventDefault();if(!pending)onClose()}}>
    <header className="settings-dialog-head"><div><span className="eyebrow">PARAMÈTRES ET CONNEXION</span><h2 id={heading}>{title}</h2></div>
      <button type="button" className="icon-button" aria-label="Fermer la configuration" disabled={pending} onClick={onClose}><Icon name="close"/></button></header>
    <div className="settings-dialog-body">{error&&<p className="alert error" role="alert">{error}</p>}{message&&<p className="alert success" role="status">{message}</p>}
      <fieldset className="dialog-fields" disabled={pending}>{children}</fieldset></div>
    <footer className="settings-dialog-foot"><span>{pending?'Enregistrement en cours…':'Les modifications sont appliquées après enregistrement.'}</span><button type="button" onClick={onClose} disabled={pending}>Annuler</button></footer>
  </dialog>,document.body)
}
