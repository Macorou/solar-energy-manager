import {useId} from 'react'

/** Original local vector drawings; no remote image request or manufacturer asset. */
export function DeviceIllustration({kind}:{kind:'charger'|'water_heater'}) {
  const id=useId().replaceAll(':','')
  if(kind==='water_heater')return <svg className="tank-illustration" viewBox="0 0 190 285" role="img" aria-label="Illustration d’un ballon d’eau chaude">
    <defs><linearGradient id={id+'shell'}><stop stopColor="#dce2e9"/><stop offset=".2" stopColor="#f9fafc"/><stop offset=".54" stopColor="#fff"/><stop offset=".83" stopColor="#f0f3f7"/><stop offset="1" stopColor="#cfd7e1"/></linearGradient>
      <linearGradient id={id+'top'} x2="0" y2="1"><stop stopColor="#e2e7ef"/><stop offset="1" stopColor="#fff"/></linearGradient></defs>
    <ellipse cx="96" cy="268" rx="76" ry="10" fill="#eef1f5"/>
    <g stroke="#7b899b" strokeWidth="1.7" strokeLinejoin="round">
      <path d="M78 230v34h8v-27m23-7v31h8v-25" fill="#e8edf3"/><path d="M77 253h10m21-1h10" stroke="#9aa8b8"/>
      <path d="M40 34c0-21 112-21 112 0v193c0 23-112 23-112 0Z" fill={'url(#'+id+'shell)'}/>
      <ellipse cx="96" cy="34" rx="56" ry="13" fill={'url(#'+id+'top)'}/>
      <path d="M40 35c10 14 102 14 112 0M40 222c13 14 98 14 112 0" fill="none" stroke="#a4afbd"/>
      <path d="M48 49v167m96-167v167" stroke="#c4ccd7" strokeWidth="1"/>
      <path d="M42 43c28-7 79-7 108 0" fill="none" stroke="#e1e6ed"/>
      <circle cx="96" cy="105" r="16" fill="#f5f7fa"/>
      <path d="M93 97a3 3 0 0 1 6 0v14a5 5 0 1 1-6 0Z" fill="#d6dfe9" strokeWidth="1.4"/>
      <path d="M96 99v15" stroke="#647a94" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M54 234c24 7 60 7 84 0" fill="none" stroke="#c4ccd6"/>
    </g>
    <path d="M56 56v145" stroke="#fff" strokeWidth="5" strokeLinecap="round" opacity=".9"/>
  </svg>
  return <svg className="car-illustration" viewBox="15 35 300 170" role="img" aria-label="Illustration d’une voiture électrique blanche">
    <defs><linearGradient id={id+'body'} x1="0" y1="0" x2=".15" y2="1"><stop stopColor="#fff"/><stop offset=".55" stopColor="#f3f6fa"/><stop offset="1" stopColor="#c8d2df"/></linearGradient>
      <linearGradient id={id+'glass'} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f2f6fb"/><stop offset=".5" stopColor="#d5e0ec"/><stop offset="1" stopColor="#aebed0"/></linearGradient>
      <linearGradient id={id+'wheel'}><stop stopColor="#44566c"/><stop offset=".6" stopColor="#25364b"/><stop offset="1" stopColor="#77879b"/></linearGradient></defs>
    <ellipse cx="164" cy="193" rx="143" ry="13" fill="#e9edf3"/>
    <g stroke="#75869c" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="255" cy="160" rx="19" ry="29" fill={'url(#'+id+'wheel)'}/><ellipse cx="257" cy="161" rx="11" ry="23" fill="#d4dce7"/>
      <path d="m253 141 5 40m-13-22 22 6m-17 13 13-31" stroke="#8b9aaf"/>
      <path d="M24 163 27 134Q28 122 44 114L84 99l35-40q10-11 30-13l63-1q24 1 37 15l29 35 15 13q9 10 11 30l-4 24-21 10q2-38-19-43-22-2-23 43l-90 13q-5-38-27-34-22 3-23 38l-53-4q-19-3-20-22Z" fill={'url(#'+id+'body)'}/>
      <path d="m83 101 39-37q6-6 20-7l42-1-8 41Z" fill={'url(#'+id+'glass)'}/>
      <path d="m190 57 21 1q20 1 30 13l20 28-69-3Z" fill={'url(#'+id+'glass)'}/>
      <path d="m250 73 21 29-8-1-19-28Z" fill="#aebdce"/>
      <path d="m181 56-5 41 13 1-1-42Z" fill="#7e90a6"/>
      <path d="m94 106 82-4 94 8-50 16-120 13-58-20Z" fill="#f9fbfd"/>
      <path d="m94 108 77-5m26-1 57 7" stroke="#c3cdda"/>
      <path d="m186 103-1 51-32 9m109-54 6 15m-1 46-68 10" fill="none" stroke="#a0adbe"/>
      <path d="m185 154 50-6" stroke="#c9d3df"/>
      <path d="m198 115 11-1m62 2 9-1" stroke="#72859d" strokeWidth="3"/>
      <path d="m169 99 4-12q10-6 16 0l-1 9Z" fill="#e2e9f1"/>
      <path d="m30 135 17-7 26 5-8 9-25 2Z" fill="#faffff"/><path d="m107 139 27-6 13-10 6 7-15 16-28 3Z" fill="#eff8ff"/>
      <path d="m35 139 23-2m56 7 23-6" stroke="#b3cce1" strokeWidth="2.8"/>
      <path d="m48 151 49 5 30-4-6 12-27 3-45-5Z" fill="#3e5169" stroke="#596d85"/>
      <path d="m33 165 22 3 35 6 35-5-4 13-36 5-46-7Z" fill="#8294aa"/>
      <path d="m45 172 38 6 30-5" fill="none" stroke="#344b65" strokeWidth="3"/>
      <path d="m31 147-1 11m111-8-3 12" stroke="#e3edf6" strokeWidth="3"/>
      <circle cx="92" cy="145" r="4" fill="#c8d3df"/>
      <ellipse cx="132" cy="170" rx="21" ry="30" fill={'url(#'+id+'wheel)'}/>
      <ellipse cx="135" cy="170" rx="13" ry="24" fill="#e1e7ee"/><ellipse cx="136" cy="171" rx="4" ry="6" fill="#9aabba"/>
      <path d="m134 148 3 44m-14-24 24 8m-21 9 19-29" fill="none" stroke="#8d9fb2"/>
      <path d="m103 188 11-2m37-5 84-14" stroke="#7488a0"/>
      <path d="m280 106 8-2 4 12-10 2Z" fill="#e4ebf4"/>
    </g>
    <g stroke="#2786df" strokeWidth="3" strokeLinecap="round" fill="none"><path d="m287 110 8 3q8 4 8 13v57q0 12 11 12"/><path d="m290 107 9 5-4 10-9-5Z" fill="#2589e7"/><path d="m296 108 4 2m-2-6 4 2" strokeWidth="2"/></g>
    <path d="m113 76 25-15m60 2 33 27" stroke="white" strokeWidth="3" opacity=".7" strokeLinecap="round"/>
  </svg>
}
