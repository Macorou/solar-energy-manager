const carUrl=new URL('../assets/car-transparent.png',import.meta.url).href
const tankUrl=new URL('../assets/tank-transparent.png',import.meta.url).href

export function DeviceIllustration({kind}:{kind:'charger'|'water_heater'}) {
  const car=kind==='charger'
  return <svg className={car?'car-illustration':'tank-illustration'}
    viewBox={car?'0 0 1774 887':'0 0 1024 1536'}
    role="img" aria-label={car?'Illustration d’une voiture électrique blanche':'Illustration d’un ballon d’eau chaude'}>
    <image href={car?carUrl:tankUrl} width={car?1774:1024} height={car?887:1536}/>
  </svg>
}
