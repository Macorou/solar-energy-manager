import type {TempoState} from '../api/types'

const names={bleu:'Bleu',blanc:'Blanc',rouge:'Rouge'}
export function TempoStatus({tempo}:{tempo?:TempoState}) {
  if(!tempo?.configured)return null
  return <>
    {tempo.color&&<span className={'tempo-context '+tempo.color}>Tempo : {names[tempo.color]}</span>}
    {tempo.unknown&&<span className="tempo-context unknown">Couleur Tempo inconnue</span>}
    {tempo.red_peak&&<span className="tempo-pill">Heures pleines rouges : pas de réseau en automatique</span>}
  </>
}
