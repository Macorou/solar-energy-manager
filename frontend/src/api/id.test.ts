import {expect,it,vi} from 'vitest'
import {createId} from './id'
it('creates unique valid identifiers without secure-context randomUUID',()=>{
  const cryptoBefore=globalThis.crypto
  vi.stubGlobal('crypto',{getRandomValues:cryptoBefore.getRandomValues.bind(cryptoBefore)})
  try {
    const one=createId(),two=createId()
    expect(one).toMatch(/^[a-f0-9-]{36}$/)
    expect(one).not.toBe(two)
  } finally {vi.unstubAllGlobals()}
})
