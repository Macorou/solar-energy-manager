import {useEffect,useRef,useState} from 'react'
import {bucketLabel,colorFor,percent} from './model'
import type {SessionPage} from './types'

export function SolarHistoryChart({data}:{data:SessionPage}){
  const ref=useRef<HTMLDivElement>(null),[width,setWidth]=useState(500)
  useEffect(()=>{const node=ref.current!,observer=new ResizeObserver(()=>setWidth(Math.max(230,node.clientWidth)));observer.observe(node);return()=>observer.disconnect()},[])
  const left=10,right=42,top=15,bottom=175,x=(i:number)=>left+(width-left-right)*i/11,y=(p:number)=>bottom-(bottom-top)*p/100
  return <div ref={ref}><svg viewBox={`0 0 ${width} 207`} width="100%" height="207" role="img" aria-label="Part solaire mensuelle par année">
    {[0,25,50,75,100].map(p=><g key={p}><line x1={left} x2={width-right} y1={y(p)} y2={y(p)} className="chart-grid"/><text x={width-right+7} y={y(p)+4} className="chart-axis">{p} %</text></g>)}
    {[0,2,4,6,8,10].map(m=><text key={m} x={x(m)} y={201} textAnchor={m===0?'start':'middle'} className="chart-axis">{bucketLabel(String(m+1),'year',2026,1,true)}</text>)}
    {data.solar_years.map(year=>{let connected=false;const points=year.months.map((month,i)=>{const value=month.solar_percent;if(value==null){connected=false;return ''}const command=connected?'L':'M';connected=true;return `${command}${x(i)},${y(value)}`}).join(' ')
      return <g key={year.year}><path d={points} fill="none" stroke={colorFor(String(year.year))} strokeWidth="2.5"/>{year.months.map((month,i)=>month.solar_percent!=null?<circle key={i} cx={x(i)} cy={y(month.solar_percent)} r="4" fill={colorFor(String(year.year))}><title>{bucketLabel(String(i+1),'year',year.year,1)} {year.year} : {percent(month.solar_percent)}</title></circle>:null)}</g>
    })}
  </svg><div className="sessions-legends">{data.solar_years.map(year=><div key={year.year}><span><i style={{background:colorFor(String(year.year))}}/>{year.year}</span><strong>{percent(year.totals.solar_percent)}</strong></div>)}</div></div>
}
