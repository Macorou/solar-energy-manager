import {afterEach,expect,it,vi} from 'vitest'
import {api} from './client'
const reply=(ok:boolean,body:unknown)=>vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok,json:async()=>body}))
afterEach(()=>vi.unstubAllGlobals())
it('returns the parsed body on success',async()=>{reply(true,{ok:true});expect(await api('/x')).toEqual({ok:true})})
it('throws a string detail unchanged',async()=>{reply(false,{detail:'Sujet invalide'});await expect(api('/x','PUT',{})).rejects.toThrow('Sujet invalide')})
it('uses the first validation message without its pydantic prefix',async()=>{
  reply(false,{detail:[{msg:'Value error, Sujet invalide : #',loc:['body']},{msg:'autre'}]})
  await expect(api('/x','PUT',{})).rejects.toThrow(/^Sujet invalide : #$/)
})
it('falls back to the generic message for other detail shapes',async()=>{
  reply(false,{detail:[{loc:['body']}]})
  await expect(api('/x','PUT',{})).rejects.toThrow('Configuration non valide')
  reply(false,{detail:{a:1}})
  await expect(api('/x','PUT',{})).rejects.toThrow('Configuration non valide')
})
it('does not surface English built-in validation messages',async()=>{
  reply(false,{detail:[{msg:'Field required',loc:['body','broker']}]})
  await expect(api('/x','PUT',{})).rejects.toThrow('Configuration non valide. Vérifiez les champs et les associations.')
})
