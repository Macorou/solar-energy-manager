import type {LiveState} from '../api/types'
import {watts} from '../api/client'
import {Icon} from './Icon'
export function PowerFlow({state}:{state:LiveState|null}) {
  const valid=(sample:LiveState['grid'])=>sample?.usable?sample.value:null
  const grid=state?valid(state.grid):null
  const solar=state?valid(state.solar):null
  return <section className="flow panel"><div className="section-title"><h2>Les flux de la maison</h2><span className="hint">Mesures instantanées</span></div>
    <div className="flow-nodes"><div className="flow-node sun"><Icon name="sun" size={34}/><span>Production solaire</span><strong>{watts(solar)}</strong></div>
      <div className={'flow-line '+(solar&&solar>0?'active':'')}><Icon name="arrow"/></div>
      <div className="flow-node house"><Icon name="home" size={40}/><span>Maison</span><small>Point de mesure réseau</small></div>
      <div className={'flow-line '+(grid?'active':'')}><Icon name="arrow"/></div>
      <div className="flow-node network"><Icon name="grid" size={34}/><span>{grid==null?'Réseau':grid<0?'Injection réseau':'Import réseau'}</span><strong>{watts(grid==null?null:Math.abs(grid))}</strong></div></div>
    <div className="flow-footer"><span><Icon name="sun" size={17}/>Budget solaire total des appareils</span><strong>{watts(state?.solar_budget_w)}</strong></div></section>
}
