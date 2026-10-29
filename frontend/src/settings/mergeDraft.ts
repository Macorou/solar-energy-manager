const record=(value:unknown):value is Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)
/** Apply only deliberate edits, retaining newer fields and nested mappings. */
export function mergeDraft<T>(current:T,base:T,draft:T):T{
  if(JSON.stringify(base)===JSON.stringify(draft))return current
  if(!record(base)||!record(draft))return draft
  const latest:Record<string,unknown>=record(current)?current:{},next:Record<string,unknown>={...latest}
  for(const key of new Set([...Object.keys(base),...Object.keys(draft)])){
    if(!Object.hasOwn(draft,key))delete next[key]
    else next[key]=mergeDraft(latest[key],base[key],draft[key])
  }
  return next as T
}
