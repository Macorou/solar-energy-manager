import {describe,it,expect} from 'vitest'
import {movePeriod,periodLabel,seriesFor,chartBounds,colorFor,equipmentColors} from './model'
import type {SessionPage} from './types'

describe('session period navigation',()=>{
  it('crosses December and leap years by calendar month',()=>{
    expect(movePeriod('month',2026,12,1)).toEqual({year:2027,month:1})
    expect(movePeriod('month',2024,3,-1)).toEqual({year:2024,month:2})
    expect(movePeriod('year',2026,7,-1)).toEqual({year:2025,month:7})
    expect(periodLabel('month',2026,10)).toBe('octobre 2026')
    expect(periodLabel('total',2026,10)).toBe('Tout l’historique')
  })
})
describe('session chart series',()=>{
  const data={groups:[{id:'wallbox',name:'Wallbox'}],buckets:[{energy:{solar:2,grid:3,unknown:5},cost:{cost:-2}}]} as unknown as SessionPage
  it('keeps unknown origin distinct and shows negative prices',()=>{
    expect(seriesFor(data,'solar','energy').map(s=>s.id)).toEqual(['grid','solar','unknown'])
    expect(seriesFor(data,'solar','cost').map(s=>s.id)).toEqual(['cost'])
    expect(chartBounds(data.buckets,'cost')).toEqual({min:-2,max:0})
  })
  it('uses stable equipment identifiers for colors across filters and periods',()=>{
    expect(seriesFor(data,'charger','energy')[0].color).toBe(colorFor('wallbox'))
    expect(colorFor('wallbox')).not.toBe(colorFor('garage'))
    expect(seriesFor({...data,buckets:[]},'solar','energy').some(s=>s.id==='unknown')).toBe(false)
  })
  it('omits equipment with no reliable price from financial series',()=>{
    const values={...data,groups:[{id:'unpriced',name:'Sans tarif',totals:{priced_count:0}},{id:'priced',name:'Tarifée',totals:{priced_count:1}}]} as unknown as SessionPage
    expect(seriesFor(values,'charger','cost').map(s=>s.id)).toEqual(['priced'])
  })
  it('includes equipment with a known partial cost in financial series',()=>{
    const values={...data,groups:[{id:'partial',name:'Peugeot',totals:{priced_count:0,known_cost_count:1,known_cost_eur:1.9}}]} as unknown as SessionPage
    expect(seriesFor(values,'vehicle','cost').map(s=>s.id)).toEqual(['partial'])
  })
  it('resolves palette collisions using all equipment so filters do not change colors',()=>{
    const sample={...data,vehicles:[{id:'session-peugeot',name:'Peugeot'},{id:'session-other',name:'Autre'}]} as unknown as SessionPage
    const colors=equipmentColors(sample,'vehicle')
    expect(colors['session-peugeot']).not.toBe(colors['session-other'])
    expect(equipmentColors({...sample,groups:[]},'vehicle')).toEqual(colors)
  })
})
