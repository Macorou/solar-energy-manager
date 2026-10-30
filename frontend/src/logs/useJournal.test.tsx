import {renderHook,act,waitFor,cleanup} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {useJournal} from './useJournal'

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.useRealTimers()})
const row=(id:number)=>({id,at:'2026-10-30T20:00:00Z',level:'INFO',area:'ha',message:String(id)})
const data=(ids:number[],extra={})=>({entries:ids.map(row),cursor:ids.at(-1)??0,has_more:false,has_older:false,areas:['ha'],gap:false,retention_days:7,max_entries:10000,dropped:0,...extra})
const response=(value:unknown)=>({ok:true,json:async()=>value} as Response)

it('freezes an in-flight poll when paused, then resumes without dropping that response range',async()=>{
  let resolve!:(r:Response)=>void
  let count=0
  vi.stubGlobal('fetch',async()=>++count===2?new Promise<Response>(r=>{resolve=r}):response(data(count===1?[1]:[2])))
  const hook=renderHook(({running})=>useJournal('level=DEBUG',running),{initialProps:{running:true}})
  await waitFor(()=>expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([1]))
  act(()=>hook.result.current.retry())
  hook.rerender({running:false})
  await act(async()=>resolve(response(data([2]))))
  expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([1])
  hook.rerender({running:true})
  await waitFor(()=>expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([1,2]))
})

it('older-page clicks supersede a slow auto poll instead of being discarded',async()=>{
  let resolve!:(r:Response)=>void
  vi.stubGlobal('fetch',async(input:string)=>{
    if(input.includes('before='))return response(data([1],{has_older:false}))
    if(input.includes('after='))return new Promise<Response>(r=>{resolve=r})
    return response(data([2],{has_older:true}))
  })
  const hook=renderHook(()=>useJournal('level=DEBUG',true))
  await waitFor(()=>expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([2]))
  act(()=>hook.result.current.retry())
  act(()=>hook.result.current.loadOlder())
  await waitFor(()=>expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([1,2]))
  await act(async()=>resolve(response(data([3]))))
  expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([1,2])
})

it('discards superseded filter results and keeps previously received rows on error',async()=>{
  let resolve!:(r:Response)=>void
  vi.stubGlobal('fetch',async(input:string)=>input.includes('level=TRACE')?new Promise<Response>(r=>{resolve=r}):response(data([2])))
  const hook=renderHook(({query})=>useJournal(query,true),{initialProps:{query:'level=TRACE'}})
  hook.rerender({query:'level=ERROR'})
  await waitFor(()=>expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([2]))
  await act(async()=>resolve(response(data([1]))))
  expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([2])
  vi.stubGlobal('fetch',async()=>({ok:false,status:503} as Response))
  act(()=>hook.result.current.retry())
  await waitFor(()=>expect(hook.result.current.error).toContain('indisponibles'))
  expect(hook.result.current.data?.entries.map(r=>r.id)).toEqual([2])
})

it('pages past a full 2000-line display window and returns to a coherent live tail',async()=>{
  let live=0
  vi.stubGlobal('fetch',async(input:string)=>{
    const query=new URL(input,'http://local').searchParams
    const before=Number(query.get('before'))
    if(before)return response(data(Array.from({length:500},(_,i)=>before-500+i),{has_older:before>501}))
    if(query.has('after')){live+=500;return response(data(Array.from({length:500},(_,i)=>1001+live+i)))}
    return response(data(Array.from({length:500},(_,i)=>1001+live+i),{has_older:true}))
  })
  const hook=renderHook(({running})=>useJournal('level=DEBUG',running),{initialProps:{running:true}})
  await waitFor(()=>expect(hook.result.current.data?.entries[0].id).toBe(1001))
  for(let i=0;i<4;i++){
    act(()=>hook.result.current.retry())
    await waitFor(()=>expect(hook.result.current.data?.entries.at(-1)?.id).toBe(2000+500*i))
  }
  expect(hook.result.current.data?.entries.length).toBe(2000)
  expect(hook.result.current.data?.has_older).toBe(true)
  hook.rerender({running:false})
  const start=hook.result.current.data!.entries[0].id
  act(()=>hook.result.current.loadOlder())
  await waitFor(()=>expect(hook.result.current.data?.entries[0].id).toBe(start-500))
  act(()=>hook.result.current.loadOlder())
  await waitFor(()=>expect(hook.result.current.data?.entries[0].id).toBe(start-1000))
  hook.rerender({running:true})
  await waitFor(()=>expect(hook.result.current.data?.entries[0].id).toBe(3001))
  expect(hook.result.current.data?.entries.length).toBe(500)
})
