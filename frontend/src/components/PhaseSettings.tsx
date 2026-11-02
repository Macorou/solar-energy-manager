import type {Settings} from '../api/types'
type HA=Settings['home_assistant']
export function PhaseSettings({value,onChange}:{value:HA;onChange:(next:HA)=>void}) {
  const phases=value.phases||{}
  return <div className="phase-settings"><h3>Mesures réseau par phase</h3>
    <p className="hint">Associez les canaux à leur phase réelle. La puissance doit être en W/kW, le courant en A/mA. Une puissance signée permet de distinguer import et injection.</p>
    {(['L1','L2','L3'] as const).map(phase=>{
      const config=phases[phase]
      function update(next:Partial<NonNullable<typeof config>>) {if(config)onChange({...value,phases:{...phases,[phase]:{...config,...next}}})}
      return <fieldset key={phase}><legend>{phase}</legend><label className="check"><input type="checkbox" checked={!!config} onChange={e=>{
        const next={...phases};if(e.target.checked)next[phase]={current_entity:'',voltage_entity:'',power_entity:'',max_current_a:20};else delete next[phase]
        onChange({...value,phases:next})}}/>Suivre {phase}</label>
        {config&&<div className="form-grid">
          <label>Courant réseau {phase} (A ou mA)<input value={config.current_entity} onChange={e=>update({current_entity:e.target.value.trim()})}/></label>
          <label>Tension réseau {phase} (V, facultatif)<input value={config.voltage_entity} onChange={e=>update({voltage_entity:e.target.value.trim()})}/></label>
          <label>Puissance réseau {phase} (W ou kW, facultatif)<input value={config.power_entity} onChange={e=>update({power_entity:e.target.value.trim()})}/></label>
          <label>Limite {phase} (A)<input type="number" min="1" max="1000" step=".1" value={config.max_current_a} onChange={e=>update({max_current_a:Number(e.target.value)})}/></label>
        </div>}
      </fieldset>
    })}
  </div>
}
