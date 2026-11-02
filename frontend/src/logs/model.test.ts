import {describe,it,expect} from 'vitest'
import {mergeEntries,logQuery} from './model'

describe('journal incremental updates',()=>{
  it('keeps chronological order without duplicating retried entries and bounds the view',()=>{
    const row=(id:number)=>({id,at:'2026-10-30T20:00:00Z',level:'INFO' as const,area:'ha',message:String(id)})
    expect(mergeEntries([row(2),row(3)],[row(1),row(2)],3).map(r=>r.id)).toEqual([1,2,3])
    expect(mergeEntries([row(1),row(2)],[row(3),row(4)],3).map(r=>r.id)).toEqual([2,3,4])
  })
  it('encodes every selected zone and literal search without treating it as a query',()=>{
    expect(logQuery('ERROR',['ocpp:wallbox','ha'],'timeout & 401')).toBe('level=ERROR&search=timeout+%26+401&area=ha&area=ocpp%3Awallbox')
  })
  it('evicts the newest end when paging backwards through a full window',()=>{
    const row=(id:number)=>({id,at:'2026-10-30T20:00:00Z',level:'INFO' as const,area:'ha',message:String(id)})
    expect(mergeEntries([row(3),row(4),row(5)],[row(1),row(2)],3,'oldest').map(r=>r.id)).toEqual([1,2,3])
  })
})
