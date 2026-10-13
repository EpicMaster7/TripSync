from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import current_user
from ..db import get_db
from ..models import CalendarSubscription,SyncRun,User,Trip,utcnow
from ..schemas import Subscribe,SubscriptionOut,RunOut
from ..services.calendar_feed import checked_url, FeedError, MAX_BYTES, parse_calendar
from ..services.trip_sync import sync_subscription,apply_events
from ..services.broadcast import hub
from .trips import membership

router=APIRouter()

@router.get('/trips/{trip_id}/calendar-subscriptions',response_model=list[SubscriptionOut])
def subscriptions(trip_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user)
    rows=db.scalars(select(CalendarSubscription).where(CalendarSubscription.trip_id==trip_id)).all()
    if user.id == db.get(Trip,trip_id).owner_id:
        return rows
    # An ICS URL can itself be a bearer token; members see status, not the URL.
    return [{**SubscriptionOut.model_validate(row).model_dump(), 'url':'(hidden: owner only)'} for row in rows]

@router.post('/trips/{trip_id}/calendar-subscriptions',response_model=SubscriptionOut,status_code=201)
async def subscribe(trip_id:int,data:Subscribe,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user,owner=True)
    try: await checked_url(data.url)
    except FeedError as exc: raise HTTPException(422,str(exc))
    if db.scalar(select(CalendarSubscription.id).where(CalendarSubscription.trip_id==trip_id,CalendarSubscription.url==data.url)):
        raise HTTPException(409,'Feed already subscribed')
    sub=CalendarSubscription(trip_id=trip_id,owner_id=user.id,url=data.url,status='pending')
    db.add(sub);db.commit();db.refresh(sub)
    return sub

@router.post('/trips/{trip_id}/sync',response_model=list[RunOut])
async def sync(trip_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user,owner=True)
    subs=db.scalars(select(CalendarSubscription).where(CalendarSubscription.trip_id==trip_id,CalendarSubscription.url.like('https://%'))).all()
    runs=[]
    for sub in subs:
        run=await sync_subscription(db,sub);runs.append(run)
        await hub.emit(trip_id,{'type':'sync.completed','trip_id':trip_id,'subscription_id':sub.id,'run_id':run.id,'status':run.status,'created':run.created,'updated':run.updated,'deleted':run.deleted})
    return runs

@router.get('/trips/{trip_id}/sync-runs',response_model=list[RunOut])
def runs(trip_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user)
    return db.scalars(select(SyncRun).where(SyncRun.trip_id==trip_id).order_by(SyncRun.id.desc()).limit(100)).all()

@router.put('/trips/{trip_id}/calendar-import/{feed_name}',response_model=RunOut)
async def manual_ics_import(trip_id:int,feed_name:str,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Upload a public/non-secret ICS fixture without a remote calendar account."""
    membership(db,trip_id,user,owner=True)
    if not (1 <= len(feed_name) <= 60 and feed_name.isascii() and all(c.isalnum() or c in '-_' for c in feed_name)):
        raise HTTPException(422,'Feed name must contain 1-60 alphanumeric, dash or underscore characters')
    if request.headers.get('content-type','').split(';')[0] != 'text/calendar':
        raise HTTPException(415,'Use Content-Type: text/calendar')
    pieces=[]; total=0
    async for part in request.stream():
        total+=len(part)
        if total>MAX_BYTES: raise HTTPException(413,'Calendar exceeds 1 MiB limit')
        pieces.append(part)
    body=b''.join(pieces)
    try: events=parse_calendar(body)
    except FeedError as exc: raise HTTPException(422,str(exc))
    url=f'manual://{feed_name}'
    sub=db.scalar(select(CalendarSubscription).where(CalendarSubscription.trip_id==trip_id,CalendarSubscription.url==url))
    if not sub:
        sub=CalendarSubscription(trip_id=trip_id,owner_id=user.id,url=url)
        db.add(sub);db.flush()
    run=SyncRun(trip_id=trip_id,subscription_id=sub.id,status='success')
    db.add(run);db.flush()
    apply_events(db,sub,events,run)
    sub.status='healthy';sub.error=None;sub.last_fetched_at=utcnow()
    run.finished_at=utcnow()
    db.commit();db.refresh(run)
    await hub.emit(trip_id,{'type':'sync.completed','trip_id':trip_id,'subscription_id':sub.id,
                            'run_id':run.id,'status':run.status,'created':run.created,
                            'updated':run.updated,'deleted':run.deleted})
    return run
