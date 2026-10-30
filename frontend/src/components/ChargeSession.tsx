import type {ChargingSummary,LiveDevice} from '../api/types'

const number=(value:number,digits=2)=>value.toLocaleString('fr-FR',{maximumFractionDigits:digits})
export function vehicleStatus(device:LiveDevice) {
  const s=device.state
  if(!s.connected)return 'État inconnu · borne hors connexion'
  if(s.fault)return 'État à vérifier · défaut de la borne'
  if(s.vehicle_connected===false)return 'Débranchée'
  const plugged=s.vehicle_connected===true||['Preparing','Charging','SuspendedEV','SuspendedEVSE','Finishing'].includes(s.observed_state)
  if(!plugged)return 'Branchement inconnu'
  if(s.observed_power?.usable&&s.observed_power.value!=null&&s.observed_power.value>20&&s.observed_state==='Charging')return 'En charge'
  if(s.target_reached||device.reason==='Objectif atteint')return 'Charge terminée · toujours branchée'
  if(s.observed_state==='Charging')return 'Branchée · charge à confirmer'
  if(['SuspendedEV','SuspendedEVSE'].includes(s.observed_state)||device.config.armed)return 'En attente de charge'
  return 'Branchée'
}

export function ChargeSession({value}:{value:ChargingSummary}) {
  return <section className="charge-session" aria-label="Bilan de recharge">
    <div className="charge-totals">
      <div><span>Énergie chargée{value.energy_partial?' · partielle':''}</span><strong>{number(value.energy_kwh)} kWh</strong></div>
      <div><span>Coût{value.cost_partial?' partiel':' de la recharge'}</span><strong>{value.cost_eur==null?'—':value.cost_eur.toLocaleString('fr-FR',{style:'currency',currency:'EUR'})}</strong></div>
      <div><span>Part solaire estimée</span><strong>{value.solar_percent==null?'—':number(value.solar_percent,1)+' %'}</strong></div>
    </div>
  </section>
}
