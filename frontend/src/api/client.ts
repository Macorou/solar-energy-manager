export async function api<T=unknown>(path:string,method='GET',body?:unknown):Promise<T> {
  const response=await fetch('/api/v1'+path,{method,credentials:'same-origin',
    headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
  const result=await response.json().catch(()=>({detail:'Réponse serveur illisible'}))
  if (!response.ok) {
    const first=Array.isArray(result.detail)?result.detail[0]:null
    throw new Error(typeof result.detail==='string'?result.detail:typeof first?.msg==='string'&&first.msg.startsWith('Value error, ')?first.msg.slice('Value error, '.length):
      'Configuration non valide. Vérifiez les champs et les associations.')
  }
  return result as T
}
export const watts=(value:number|null|undefined)=>value==null||!Number.isFinite(value)?'—':Math.abs(value)>=1000?
  (value/1000).toLocaleString('fr-FR',{maximumFractionDigits:2})+' kW':Math.round(value).toLocaleString('fr-FR')+' W'
export const date=(value:string|null|undefined)=>value?new Date(value).toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'short'}):'Aucune mesure'
