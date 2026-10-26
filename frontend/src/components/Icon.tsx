export function Icon({name,size=22}:{name:string;size?:number}) {
  const paths:Record<string,string>={sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5',
    home:'m3 11 9-8 9 8M5 10v11h14V10M9 21v-8h6v8',car:'m5 7 2-4h10l2 4 2 3v8H3v-8Zm-2 3h18M6 13h2m8 0h2M5 18v3m14-3v3',
    drop:'M12 2s-8 9-8 14a8 8 0 0 0 16 0c0-5-8-14-8-14Z',calendar:'M5 3v4m14-4v4M3 9h18M3 5h18v16H3Zm4 8h3m4 0h3m-10 4h3',
    history:'M4 8a9 9 0 1 1-1 8M3 3v6h6m3-3v6l4 2',settings:'m10 2-1 4-4 1-3 4 3 3v5l5 1 4 2 3-3h4l1-5-2-4-1-4h-5Zm2 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
    bolt:'m13 2-9 12h7l-1 8 10-13h-8Z',grid:'m12 2-7 20m7-20 7 20M8 8h8M6 14h12M4 20h16',arrow:'M4 12h16m-6-6 6 6-6 6',plus:'M12 4v16M4 12h16',check:'m4 12 5 5L20 6',link:'m10 8 2-2a5 5 0 0 1 7 7l-2 2M7 9l-2 2a5 5 0 0 0 7 7l2-2m-6-1 8-8'}
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.bolt}/></svg>
}
