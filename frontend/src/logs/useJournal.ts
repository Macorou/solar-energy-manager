import {useEffect,useRef,useState} from 'react'
import {mergeEntries,type LogPage} from './model'

type View=LogPage&{key:string}
export function useJournal(query:string,running:boolean){
  const [view,setView]=useState<View|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true)
  const [revision,setRevision]=useState(0)
  const enabled=useRef(running),poll=useRef<()=>void>(()=>{}),older=useRef<()=>void>(()=>{}),pause=useRef<()=>void>(()=>{})
  enabled.current=running
  useEffect(()=>{
    let active=true,cursor:number|undefined,oldest:number|undefined,archived=false
    let request:{controller:AbortController;mode:string}|undefined
    let catchup:ReturnType<typeof setTimeout>|undefined
    setLoading(true);setError('')
    function cancelPoll(){
      if(request?.mode==='poll'){request.controller.abort();request=undefined;setLoading(false)}
      clearTimeout(catchup)
    }
    async function load(mode:'initial'|'poll'|'older'='poll'){
      if(!active)return
      if(mode==='older')cancelPoll()
      if(request)return
      if(mode==='poll'&&archived){mode='initial';archived=false}
      const current={controller:new AbortController(),mode}
      request=current;setLoading(true)
      const initial=cursor===undefined||mode==='initial',paging=mode==='older'
      const params=new URLSearchParams(query)
      if(paging&&oldest)params.set('before',String(oldest))
      else if(!initial&&cursor!==undefined)params.set('after',String(cursor))
      try{
        const response=await fetch('/api/v1/logs?'+params,{credentials:'same-origin',signal:current.controller.signal,cache:'no-store'})
        if(!response.ok)throw new Error(response.status===401?'Reconnectez-vous pour consulter les journaux.':'Journaux indisponibles. Les lignes déjà reçues sont conservées.')
        const data=await response.json() as LogPage
        if(!active||request!==current||current.controller.signal.aborted||mode==='poll'&&!enabled.current)return
        if(!paging)cursor=data.cursor
        else archived=true
        setView(previous=>{
          const same=previous?.key===query
          const prior=same?previous.entries:[]
          const entries=initial&&!paging?data.entries:mergeEntries(prior,data.entries,2000,paging?'oldest':'latest')
          const evicted=!paging&&!!prior.length&&!!entries.length&&entries[0].id>prior[0].id
          oldest=entries[0]?.id
          return {...data,key:query,entries,cursor:cursor??data.cursor,has_older:initial||paging?data.has_older:evicted||!!(same&&previous.has_older),
            gap:data.gap||!!(same&&previous.gap)}
        })
        setError('')
        if(data.has_more&&!paging&&enabled.current)catchup=setTimeout(()=>void load(),0)
      }catch(e){if(active&&request===current&&(e as Error).name!=='AbortError')setError((e as Error).message)}
      finally{if(request===current){request=undefined;if(active)setLoading(false)}}
    }
    pause.current=cancelPoll
    poll.current=()=>void load()
    older.current=()=>{if(oldest)void load('older')}
    void load('initial')
    const timer=setInterval(()=>{if(enabled.current&&document.visibilityState==='visible')void load()},3000)
    const visible=()=>{if(enabled.current&&document.visibilityState==='visible')void load()}
    document.addEventListener('visibilitychange',visible)
    return()=>{active=false;request?.controller.abort();clearInterval(timer);clearTimeout(catchup);document.removeEventListener('visibilitychange',visible)}
  },[query,revision])
  useEffect(()=>{if(running)poll.current();else pause.current()},[running])
  return {data:view?.key===query?view:null,areas:view?.areas??[],error,loading,
    retry:()=>poll.current(),loadOlder:()=>older.current(),reset:()=>setRevision(n=>n+1)}
}
