export function watchTrip(id:number, changed:()=>void):()=>void{
  let ws:WebSocket | null=null, disposed=false, handle:number|undefined, attempt=0
  function connect(){
    if(disposed)return
    const scheme=location.protocol==='https:'?'wss:':'ws:'
    ws=new WebSocket(`${scheme}//${location.host}/ws/trips/${id}`)
    ws.onopen=()=>{attempt=0}
    ws.onmessage=(event)=>{
      try{const data=JSON.parse(event.data) as {type:string};
        if(['item.created','item.updated','item.deleted','trip.updated','sync.completed'].includes(data.type))changed()
      }catch{ /* invalid server event ignored */ }
    }
    ws.onclose=()=>{if(!disposed){handle=window.setTimeout(connect,Math.min(15000,1000*2**attempt));attempt=Math.min(attempt+1,4)}}
  }
  connect()
  return ()=>{disposed=true;window.clearTimeout(handle);ws?.close()}
