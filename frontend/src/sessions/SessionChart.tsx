import {useEffect,useRef,useState} from 'react'
import {bucketLabel,chartBounds,energy,money,number} from './model'
import type {Bucket,Metric,Period,Series} from './types'

export function SessionChart({buckets,series,metric,period,year,month}:{buckets:Bucket[];series:Series[];metric:Metric;period:Period;year:number;month:number}){
  const ref=useRef<HTMLDivElement>(null),[width,setWidth]=useState(600),[selected,setSelected]=useState<number|null>(null)
  useEffect(()=>{const node=ref.current!;const measure=()=>setWidth(Math.max(230,node.clientWidth));measure();const observer=new ResizeObserver(measure);observer.observe(node);return()=>observer.disconnect()},[])
  useEffect(()=>setSelected(null),[buckets,metric])
  const bounds=chartBounds(buckets,metric),max=bounds.max>0?bounds.max*1.15:bounds.min<0?0:1,min=bounds.min<0?bounds.min*1.15:0
  const left=metric==='cost'?53:8,right=49,top=23,bottom=231,plot=width-left-right,slot=plot/Math.max(1,buckets.length)
  const y=(v:number)=>bottom-(v-min)/(max-min)*(bottom-top),format=metric==='energy'?energy:money
  const label=(i:number)=>bucketLabel(buckets[i].key,period,year,month)
  const selectedBucket=selected==null?null:buckets[selected]
  const tickEvery=Math.max(1,Math.ceil(buckets.length/(width<450?7:15)))
  const rates=buckets.flatMap(b=>b.totals.average_price_per_kwh==null?[]:[b.totals.average_price_per_kwh])
  const rateMax=Math.max(.001,...rates)*1.15,rateMin=Math.min(0,...rates)*1.15
  const rateY=(v:number)=>bottom-(v-rateMin)/(rateMax-rateMin)*(bottom-top)
  let lineConnected=false
  const rateLine=buckets.map((b,i)=>{const value=b.totals.average_price_per_kwh;if(value==null){lineConnected=false;return ''}const command=lineConnected?'L':'M';lineConnected=true;return `${command}${left+slot*(i+.5)},${rateY(value)}`}).join(' ')
  const pricedEnergy=buckets.reduce((sum,b)=>sum+b.totals.priced_energy_kwh,0),pricedCost=buckets.reduce((sum,b)=>sum+(b.totals.cost_eur||0),0)
  return <><div ref={ref} className="sessions-chart" data-testid="sessions-chart">
    <svg viewBox={`0 0 ${width} 267`} width="100%" height="267" aria-label={metric==='energy'?'Énergie chargée par période en kWh':'Coût des recharges par période en euros'}>
      <text x={width-right+6} y={12} className="chart-axis">{metric==='energy'?'kWh':'€'}</text>
      {metric==='cost'&&<><text x={left-6} y={12} textAnchor="end" className="chart-axis">€/kWh</text>{[0,1,2,3,4].map(t=>{const value=rateMin+(rateMax-rateMin)*t/4;return <text key={t} x={left-6} y={rateY(value)+4} textAnchor="end" className="chart-axis">{number(value,3)}</text>})}</>}
      {[0,1,2,3,4].map(t=>{const v=min+(max-min)*t/4;return <g key={t}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} className="chart-grid"/><text x={width-right+7} y={y(v)+4} className="chart-axis">{number(v,Math.abs(max)<2?2:1)}</text></g>})}
      {buckets.map((bucket,i)=>{
        let positive=0,negative=0;const center=left+slot*(i+.5),barWidth=Math.min(38,slot*.72)
        const unavailable=metric==='cost'&&bucket.totals.count>0&&bucket.totals.priced_count===0
        return <g key={bucket.key} tabIndex={0} role="button" aria-label={`${label(i)} : ${unavailable?'coût indisponible':format(Object.values(bucket[metric]).reduce<number>((a,b)=>a+(b??0),0))}`} onFocus={()=>setSelected(i)} onClick={()=>setSelected(i)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected(i)}if(e.key==='Escape')setSelected(null)}}>
          <rect x={left+slot*i} y={top} width={slot} height={bottom-top} fill={selected===i?'var(--hover)':'transparent'} onPointerEnter={()=>setSelected(i)}/>
          {series.map(s=>{const value=bucket[metric][s.id]||0,start=value>=0?positive:negative;value>=0?positive+=value:negative+=value
            return value!==0?<rect key={s.id} x={center-barWidth/2} y={y(Math.max(start,start+value))} width={barWidth} height={Math.max(.6,Math.abs(y(start)-y(start+value)))} fill={s.color} pointerEvents="none"/>:null})}
          {(i%tickEvery===0||i===buckets.length-1)&&<text x={center} y={253} textAnchor="middle" className="chart-axis">{bucketLabel(bucket.key,period,year,month,true)}</text>}
        </g>
      })}
      {metric==='cost'&&<path d={rateLine} fill="none" stroke="var(--amber)" strokeWidth="2" pointerEvents="none"/>}
      <line x1={left} x2={width-right} y1={y(0)} y2={y(0)} className="chart-zero"/>
    </svg>
    {selectedBucket&&selected!==null&&<div className="sessions-tooltip" role="status" style={{left:`clamp(0px,${left+slot*selected-65}px,max(0px,calc(100% - 218px)))`}}>
      <div><strong>{label(selected)}</strong><button type="button" aria-label="Fermer l’infobulle" onClick={()=>setSelected(null)}>×</button></div>
      {series.map(s=><p key={s.id}><span><i style={{background:s.color}}/>{s.name}</span><b>{selectedBucket[metric][s.id]===null?'Indisponible':format(selectedBucket[metric][s.id]??0)}</b></p>)}
      {metric==='cost'&&selectedBucket.totals.average_price_per_kwh!=null&&<p><span>Prix moyen</span><b>{number(selectedBucket.totals.average_price_per_kwh,4)} €/kWh</b></p>}
      {metric==='cost'&&selectedBucket.totals.cost_missing_count>0&&<small>Tarif incomplet pour {selectedBucket.totals.cost_missing_count} session(s).</small>}
    </div>}
  </div><div className="sessions-legends">{series.map(s=><div key={s.id}><span><i style={{background:s.color}}/>{s.name}</span><strong>{format(buckets.reduce((sum,b)=>sum+(b[metric][s.id]||0),0))}</strong></div>)}{metric==='cost'&&pricedEnergy>0&&<div><span><i style={{background:'var(--amber)'}}/>Prix moyen au kWh</span><strong>{number(pricedCost/pricedEnergy,4)} €/kWh</strong></div>}</div></>
}
