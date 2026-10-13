import React, {useEffect, useState} from 'react'
import {Link, Routes, Route, useNavigate, useParams} from 'react-router-dom'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {api,json,setCsrf} from '../lib/api'
import {watchTrip} from '../lib/websocket'
import type {Session,Trip,Item,Subscription,SyncRun} from '../types'
import {ErrorText, Loading} from '../components/Feedback'
function SessionGate(){
  const query=useQuery({queryKey:['session'],queryFn:async()=>{const s=await api<Session>('/me');setCsrf(s.csrf_token);return s},retry:false})
  if(query.isLoading)return <main><Loading/></main>
  if(!query.data)return <Auth onSuccess={()=>query.refetch()}/>
  return <Shell session={query.data}/>
}
function Auth({onSuccess}:{onSuccess:()=>void}){
  const [signup,setSignup]=useState(false),[name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState('')
  const [error,setError]=useState<unknown>(null),[pending,setPending]=useState(false)
  async function submit(e:React.FormEvent){
    e.preventDefault();setPending(true);setError(null)
    try{await api(signup?'/auth/register':'/auth/login',{method:'POST',body:json({name,email,password})});onSuccess()}
    catch(e){setError(e)}finally{setPending(false)}
  }
  return <main className="auth-layout"><div className="hero"><span className="eyebrow">COLLABORATIVE TRAVEL PLANNING</span><h1>Make room for<br/><em>every adventure.</em></h1><p>One itinerary. Every traveler in sync.</p><div className="hero-orbit">✦ <span>Seattle / Tokyo / Anywhere</span></div></div><section className="panel auth-panel"><h2>{signup?'Create an account':'Welcome back'}</h2><p className="muted">{signup?'Start planning together.':'Sign in to see your trips.'}</p><form onSubmit={submit}>{signup&&<label>Name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>}<label>Email<input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label>Password<input type="password" required minLength={10} value={password} onChange={e=>setPassword(e.target.value)}/></label><ErrorText error={error}/><button disabled={pending} type="submit">{pending?'Working…':signup?'Create account':'Sign in'}</button></form><button className="text-button" onClick={()=>{setSignup(!signup);setError(null)}}>{signup?'Already have an account? Sign in':'New here? Create account'}</button></section></main>
}
function Shell({session}:{session:Session}){
  const qc=useQueryClient(),navigate=useNavigate()
  async function logout(){await api('/auth/logout',{method:'POST'});setCsrf('');qc.clear();navigate('/')}
  return <><header className="header"><Link to="/" className="logo">✳ TripSync</Link><span className="header-right">{session.user.name}<button className="text-button" onClick={logout}>Sign out</button></span></header><Routes><Route path="/" element={<Dashboard/>}/><Route path="/trips/:id" element={<TripPage session={session}/>}/><Route path="/invite/:token" element={<AcceptInvite/>}/><Route path="*" element={<p>Page not found. <Link to="/">Go home</Link></p>}/></Routes></>
}
function Dashboard(){
  const qc=useQueryClient(),nav=useNavigate()
  const q=useQuery({queryKey:['trips'],queryFn:()=>api<Trip[]>('/trips')})
  const [name,setName]=useState(''),[destination,setDestination]=useState(''),[timezone,setTimezone]=useState('America/Los_Angeles'),[start,setStart]=useState(''),[end,setEnd]=useState(''),[error,setError]=useState<unknown>(null)
  async function create(e:React.FormEvent){e.preventDefault();setError(null);try{const t=await api<Trip>('/trips',{method:'POST',body:json({name,destination,timezone,start_date:start,end_date:end})});await qc.invalidateQueries({queryKey:['trips']});nav(`/trips/${t.id}`)}catch(e){setError(e)}}
  return <main className="container"><div className="page-heading"><div><p className="eyebrow">YOUR TRIPS</p><h1>Where to next?</h1><p className="muted">Keep everyone's plans in one place.</p></div><span className="round-icon">✈</span></div><div className="columns"><section><h2>Upcoming plans</h2>{q.isPending?<Loading/>:q.error?<ErrorText error={q.error}/>:!q.data?.length?<p className="empty">No trips yet. Create your first one.</p>:<div className="trip-list">{q.data.map(t=><Link key={t.id} to={`/trips/${t.id}`} className="trip-card"><span className="trip-art">✦</span><div><h3>{t.name}</h3><p>{t.destination} · {t.start_date} to {t.end_date}</p></div><b>↗</b></Link>)}</div>}</section><section className="panel"><h2>Create a trip</h2><form onSubmit={create}><label>Trip name<input required value={name} onChange={e=>setName(e.target.value)} placeholder="Pacific Northwest getaway"/></label><label>Destination<input required value={destination} onChange={e=>setDestination(e.target.value)} placeholder="Seattle"/></label><label>IANA timezone<input required value={timezone} onChange={e=>setTimezone(e.target.value)} placeholder="America/Los_Angeles"/></label><div className="form-row"><label>Start date<input required type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>End date<input required type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label></div><ErrorText error={error}/><button>Create trip →</button></form></section></div></main>
}
function AcceptInvite(){const {token}=useParams(),nav=useNavigate(),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false)
  async function accept(){setBusy(true);try{const t=await api<Trip>(`/invites/${encodeURIComponent(token||'')}/accept`,{method:'POST'});nav(`/trips/${t.id}`)}catch(e){setError(e)}finally{setBusy(false)}}
  return <main className="container panel standalone"><h2>Join this trip?</h2><p>Accept the invitation to collaborate on a shared itinerary.</p><ErrorText error={error}/><button disabled={busy} onClick={accept}>{busy?'Joining…':'Accept invitation'}</button></main>
}
function isoDay(value:string,zone:string){
  const parts=new Intl.DateTimeFormat('en-US',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value))
  const get=(type:string)=>parts.find(p=>p.type===type)?.value||''
  return `${get('year')}-${get('month')}-${get('day')}`
}
function localTime(value:string,zone:string){return new Intl.DateTimeFormat('en-US',{timeZone:zone,weekday:'short',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value))}
function TripPage({session}:{session:Session}){
  const {id}=useParams(),tid=Number(id),qc=useQueryClient()
  const t=useQuery({queryKey:['trip',tid],queryFn:()=>api<Trip>(`/trips/${tid}`)})
  const items=useQuery({queryKey:['items',tid],queryFn:()=>api<Item[]>(`/trips/${tid}/items`),refetchInterval:60000})
  const subs=useQuery({queryKey:['subs',tid],queryFn:()=>api<Subscription[]>(`/trips/${tid}/calendar-subscriptions`)})
  const runs=useQuery({queryKey:['runs',tid],queryFn:()=>api<SyncRun[]>(`/trips/${tid}/sync-runs`)})
  const [invite,setInvite]=useState(''),[url,setUrl]=useState(''),[error,setError]=useState<unknown>(null),[syncing,setSyncing]=useState(false)
  const [editing,setEditing]=useState<Item|null>(null),[createOpen,setCreateOpen]=useState(false)
  useEffect(()=>{if(!tid)return;return watchTrip(tid,()=>{void qc.invalidateQueries({queryKey:['items',tid]});void qc.invalidateQueries({queryKey:['trip',tid]});void qc.invalidateQueries({queryKey:['runs',tid]});void qc.invalidateQueries({queryKey:['subs',tid]})})},[tid,qc])
  const trip=t.data,owner=trip?.owner_id===session.user.id
  async function createInvite(){setError(null);try{const data=await api<{token:string}>(`/trips/${tid}/invites`,{method:'POST'});setInvite(`${location.origin}/invite/${data.token}`)}catch(e){setError(e)}}
  async function subscribe(e:React.FormEvent){e.preventDefault();setError(null);try{await api(`/trips/${tid}/calendar-subscriptions`,{method:'POST',body:json({url})});setUrl('');await qc.invalidateQueries({queryKey:['subs',tid]})}catch(e){setError(e)}}
  async function importFile(e:React.ChangeEvent<HTMLInputElement>){
    const file=e.target.files?.[0];if(!file)return;setError(null)
    try{if(file.size>1024*1024)throw new Error('ICS file must be at most 1 MiB')
      await api(`/trips/${tid}/calendar-import/manual-upload`,{method:'PUT',body:await file.text(),headers:{'Content-Type':'text/calendar'}})
      await Promise.all([qc.invalidateQueries({queryKey:['items',tid]}),qc.invalidateQueries({queryKey:['subs',tid]}),qc.invalidateQueries({queryKey:['runs',tid]})])
    }catch(e){setError(e)}finally{e.target.value=''}
  }
  async function sync(){setSyncing(true);setError(null);try{await api(`/trips/${tid}/sync`,{method:'POST'});await Promise.all([qc.invalidateQueries({queryKey:['items',tid]}),qc.invalidateQueries({queryKey:['subs',tid]}),qc.invalidateQueries({queryKey:['runs',tid]})])}catch(e){setError(e)}finally{setSyncing(false)}}
  async function erase(item:Item){if(!confirm(`Delete "${item.title}"?`))return;try{await api(`/trips/${tid}/items/${item.id}?version=${item.version}`,{method:'DELETE'});await qc.invalidateQueries({queryKey:['items',tid]})}catch(e){setError(e)}}
  const grouped=items.data?.reduce<Record<string,Item[]>>((acc,item)=>{const key=isoDay(item.starts_at,trip?.timezone||'UTC');(acc[key]??=[]).push(item);return acc},{})||{}
  if(t.isPending)return <main className="container"><Loading/></main>
  if(!trip)return <main className="container"><ErrorText error={t.error||'Trip not found'}/></main>
  return <main className="container"><Link to="/" className="back">← All trips</Link><div className="page-heading"><div><p className="eyebrow">{trip.destination.toUpperCase()} · {trip.timezone}</p><h1>{trip.name}</h1><p className="muted">{trip.start_date} → {trip.end_date}</p></div><button onClick={()=>{setEditing(null);setCreateOpen(true)}}>+ Add activity</button></div><div className="columns itinerary-layout"><section><h2>Itinerary</h2>{items.isPending?<Loading/>:items.error?<ErrorText error={items.error}/>:Object.keys(grouped).length===0?<p className="empty">No activities. Start building your itinerary.</p>:Object.entries(grouped).sort(([a],[b])=>a.localeCompare(b)).map(([day,dayItems])=><div key={day} className="day-section"><div className="day-heading"><span className="day-dot"/><h3>{new Date(`${day}T12:00:00Z`).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric',timeZone:'UTC'})}</h3><span>{dayItems.length} stops</span></div><div className="activity-list">{dayItems.map(item=><article className="activity" key={item.id}><div className="time">{localTime(item.starts_at,trip.timezone)}<span>to {localTime(item.ends_at,trip.timezone)}</span></div><div className="activity-main"><div className="activity-title"><h4>{item.title}</h4>{item.source==='ics'&&<span className="tag">Calendar</span>}</div>{item.location&&<p>📍 {item.location}</p>}{item.notes&&<p>{item.notes}</p>}{item.link&&<p><a href={item.link} target="_blank" rel="noreferrer">Open link ↗</a></p>}<div className="actions">{item.source==='manual'?<><button className="text-button" onClick={()=>{setCreateOpen(false);setEditing(item)}}>Edit</button><button className="text-button destructive" onClick={()=>erase(item)}>Delete</button></>:<small className="muted">Managed by calendar feed</small>}</div></div></article>)}</div></div>)}<ErrorText error={error}/></section><aside className="sidebar"><section className="panel"><h3>Plan together</h3><p className="muted">Invite another traveler. Invitations expire in 3 days and can be used once.</p>{owner?<><button onClick={createInvite} className="secondary">Generate invite link</button>{invite&&<div className="invite"><input readOnly aria-label="Invite link" value={invite} onFocus={e=>e.target.select()}/><button onClick={()=>navigator.clipboard.writeText(invite)}>Copy</button></div>}</>:<p className="muted">Ask the trip owner for an invite link.</p>}</section><section className="panel"><h3>Calendar sync</h3><p className="muted">Subscribe to an HTTPS .ics feed. The scheduler checks every 30 minutes.</p>{subs.data?.map(s=><div key={s.id} className="feed"><div className="feed-url" title={s.url}>{s.url}</div><small>{s.status} {s.last_fetched_at?`· ${new Date(s.last_fetched_at).toLocaleString()}`:''}</small>{s.error&&<p role="alert" className="error">{s.error}</p>}</div>)}{owner&&<><form onSubmit={subscribe}><label>Feed URL<input type="url" required placeholder="https://…/calendar.ics" value={url} onChange={e=>setUrl(e.target.value)}/></label><button className="secondary">Add calendar</button></form><button onClick={sync} disabled={syncing} className="text-button">{syncing?'Synchronizing…':'Sync now ↻'}</button><label className="upload-label">Or import a local .ics file<input type="file" accept=".ics,text/calendar" onChange={importFile}/></label></>}{runs.data?.[0]&&<p className="muted tiny">Last sync: {runs.data[0].status} · {runs.data[0].created} new, {runs.data[0].updated} updated, {runs.data[0].deleted} removed</p>}</section></aside></div>{(createOpen||editing)&&<ItemEditor key={editing?.id||'new'} trip={trip} item={editing} close={()=>{setEditing(null);setCreateOpen(false)}} saved={()=>{void qc.invalidateQueries({queryKey:['items',tid]});setEditing(null);setCreateOpen(false)}}/>}</main>
}
function ItemEditor({trip,item,close,saved}:{trip:Trip;item:Item|null;close:()=>void;saved:()=>void}){
  const [title,setTitle]=useState(item?.title||''),[start,setStart]=useState(item?.starts_at||''),[end,setEnd]=useState(item?.ends_at||''),[location,setLocation]=useState(item?.location||''),[notes,setNotes]=useState(item?.notes||''),[link,setLink]=useState(item?.link||''),[error,setError]=useState<unknown>(null),[saving,setSaving]=useState(false)
  async function submit(e:React.FormEvent){e.preventDefault();setSaving(true);setError(null)
    try{await api(`/trips/${trip.id}/items${item?`/${item.id}`:''}`,{method:item?'PATCH':'POST',body:json({...(item?{version:item.version}:{}),title,starts_at:start,ends_at:end,location,notes,link:link||null})});saved()}
    catch(e){setError(e)}finally{setSaving(false)}
  }
  return <div className="modal-backdrop" role="presentation"><section className="modal panel" role="dialog" aria-modal="true" aria-label={item?'Edit activity':'Add activity'}><div className="modal-heading"><h2>{item?'Edit activity':'New activity'}</h2><button className="text-button" onClick={close} aria-label="Close">✕</button></div><p className="muted">Include a UTC offset in times (e.g. <code>2026-11-01T09:00:00-08:00</code>). Trip timezone: {trip.timezone}.</p><form onSubmit={submit}><label>Title<input required value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Start (ISO 8601 with offset)<input required placeholder="2026-11-01T09:00:00-08:00" value={start} onChange={e=>setStart(e.target.value)}/></label><label>End (ISO 8601 with offset)<input required placeholder="2026-11-01T10:00:00-08:00" value={end} onChange={e=>setEnd(e.target.value)}/></label><label>Location<input value={location} onChange={e=>setLocation(e.target.value)}/></label><label>Notes<textarea rows={3} value={notes} onChange={e=>setNotes(e.target.value)}/></label><label>Link (optional)<input type="url" value={link} onChange={e=>setLink(e.target.value)}/></label><ErrorText error={error}/>{error instanceof Error&&error.message.toLowerCase().includes('reload')&&<p className="muted">Close this editor to load the latest version, then retry your edit.</p>}<button disabled={saving}>{saving?'Saving…':item?'Save changes':'Add to itinerary'}</button></form></section></div>
}
export default function App(){return <Routes><Route path="/*" element={<SessionGate/>}/></Routes>}
