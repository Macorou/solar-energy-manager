export function Icon({name,size=22}:{name:string;size?:number}) {
  const paths:Record<string,string>={sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5',
    home:'m3 11 9-8 9 8M5 10v11h14V10M9 21v-8h6v8',car:'m5 7 2-4h10l2 4 2 3v8H3v-8Zm-2 3h18M6 13h2m8 0h2M5 18v3m14-3v3',
    drop:'M12 2s-8 9-8 14a8 8 0 0 0 16 0c0-5-8-14-8-14Z',calendar:'M5 3v4m14-4v4M3 9h18M3 5h18v16H3Zm4 8h3m4 0h3m-10 4h3',
    history:'M4 8a9 9 0 1 1-1 8M3 3v6h6m3-3v6l4 2',settings:'m10 2-1 4-4 1-3 4 3 3v5l5 1 4 2 3-3h4l1-5-2-4-1-4h-5Zm2 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
    bolt:'m13 2-9 12h7l-1 8 10-13h-8Z',grid:'m12 2-7 20m7-20 7 20M8 8h8M6 14h12M4 20h16',arrow:'M4 12h16m-6-6 6 6-6 6',plus:'M12 4v16M4 12h16',check:'m4 12 5 5L20 6',link:'m10 8 2-2a5 5 0 0 1 7 7l-2 2M7 9l-2 2a5 5 0 0 0 7 7l2-2m-6-1 8-8',
    clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 7v5l3 2',pause:'M8 5v14M16 5v14',play:'m8 4 12 8-12 8Z',
    info:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 11v6M12 7v.1',leaf:'M19 3C8 2 3 7 5 13c2 6 11 4 14-10ZM4 21 15 9',
    hand:'M8 12V6a2 2 0 0 1 4 0v5-7a2 2 0 0 1 4 0v7-4a2 2 0 0 1 4 0v8c0 5-3 7-7 7-4 0-6-4-9-8-1-2 1-4 3-2l3 3',
    eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm14 0a4 4 0 1 0-8 0 4 4 0 0 0 8 0',
    moon:'M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z',close:'m6 6 12 12M6 18 18 6',plug:'M8 2v5m8-5v5M6 7h12v4a6 6 0 0 1-12 0ZM12 17v5',sliders:'M4 7h9m4 0h3M4 17h3m4 0h9M13 4v6M7 14v6',battery:'M3 7h16v12H3ZM22 11v4M7 10v6m4-6v6m4-6v6',copy:'M9 3h12v12H9ZM3 9h3v12h12v-3',
    tank:'M5 5a7 3 0 0 1 14 0v13a7 3 0 0 1-14 0ZM5 5a7 3 0 0 0 14 0M8 21v2m8-2v2M12 9v6m0 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3',up:'m6 15 6-6 6 6',down:'m6 9 6 6 6-6',
    chart:'M5 20V10m7 10V4m7 16V7',ha:'m3 10 9-8 9 8v12H3Zm9-3v11m0-5-5-4m5 7 5-5M7 8v2m10 0v2'}
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.bolt}/></svg>
}
