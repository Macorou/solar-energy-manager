import {useState} from 'react'
import {api} from '../api/client'
export function SocReference({deviceId,sessionId}:{deviceId:string;sessionId:string}) {
  const [value,setValue]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const number=Number(value)
  async function confirm(){
    setBusy(true);setMessage('')
    try {await api(`/devices/${deviceId}/soc-reference`,'POST',{soc:number,session_id:sessionId});setMessage('Référence enregistrée pour cette recharge.')}
    catch(error){setMessage(error instanceof Error?error.message:'Confirmation indisponible')}
    finally{setBusy(false)}
  }
  async function refresh(){
    setBusy(true);setMessage('')
    try {await api(`/devices/${deviceId}/meter-read`,'POST');setMessage('Lecture demandée. Attendez la remontée du compteur puis confirmez le niveau actuel.')}
    catch(error){setMessage(error instanceof Error?error.message:'Lecture indisponible')}
    finally{setBusy(false)}
  }
  return <div className="soc-reference"><p>Le relevé Peugeot précède l’historique suivi. Attendez une nouvelle mesure, ou confirmez le niveau actuel vérifié sur la voiture. Cette référence permettra le pilotage selon le mode choisi.</p>
    <label>Pourcentage actuel confirmé (%)<input type="number" min="0" max="100" step=".1" value={value} onChange={e=>setValue(e.target.value)}/></label>
    <button disabled={busy||value===''||!Number.isFinite(number)||number<0||number>100} onClick={confirm}>Confirmer pour cette recharge</button>
    <button disabled={busy} onClick={refresh}>Actualiser le compteur de la borne</button>
    {message&&<p role="status">{message}</p>}
  </div>
}
