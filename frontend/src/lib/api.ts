let csrf = ''
export function setCsrf(token: string){ csrf = token }
export class ApiError extends Error {
  constructor(public status: number, message: string){super(message)}
}
export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const method=options.method || 'GET'
  const response=await fetch(path,{
    ...options,credentials:'same-origin',
    headers:{...(options.body?{'Content-Type':'application/json'}:{}),
      ...(method!=='GET'&&csrf?{'X-CSRF-Token':csrf}:{}), ...options.headers}
  })
  if(!response.ok){
    const error: {detail?: string | {msg:string}[]} = await response.json().catch(()=>({detail:'Request failed'}))
    const message=Array.isArray(error.detail)?error.detail.map(e=>e.msg).join('; '):(error.detail || response.statusText)
    throw new ApiError(response.status,message)
  }
  if(response.status===204) return undefined as T
  return await response.json() as T
}
export const json=(value:unknown)=>JSON.stringify(value)
