// The original demo artwork is bundled unchanged. SVG viewports display only
// the requested drawing, preserving the exact source pixels and proportions.
const conceptUrl=new URL('../assets/pilotage-concept-original.png',import.meta.url).href

export function DeviceIllustration({kind}:{kind:'charger'|'water_heater'}) {
  const car=kind==='charger'
  return <svg className={car?'car-illustration':'tank-illustration'}
    viewBox={car?'282 368 302 157':'976 306 183 294'}
    role="img" aria-label={car?'Illustration d’une voiture électrique blanche':'Illustration d’un ballon d’eau chaude'}>
    <image href={conceptUrl} width="1586" height="992"/>
  </svg>
}
