import hashlib, secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..auth import current_user
from ..db import get_db
from ..models import Trip, TripInvite, TripMember, User, utcnow
from ..schemas import TripFields, TripOut, TripPatch
from ..services.broadcast import hub

router=APIRouter()

def membership(db: Session, trip_id: int, user: User, owner=False):
    trip = db.get(Trip, trip_id)
    if not trip or not db.get(TripMember, (trip_id, user.id)):
        raise HTTPException(404, 'Trip not found')
    if owner and trip.owner_id != user.id: raise HTTPException(403, 'Only the trip owner can do this')
    return trip

@router.get('/trips', response_model=list[TripOut])
def list_trips(user: User=Depends(current_user), db: Session=Depends(get_db)):
    return db.scalars(select(Trip).join(TripMember).where(TripMember.user_id == user.id).order_by(Trip.id.desc())).all()

@router.post('/trips', response_model=TripOut, status_code=201)
def create_trip(data: TripFields, user: User=Depends(current_user), db: Session=Depends(get_db)):
    trip = Trip(**data.model_dump(), owner_id=user.id)
    db.add(trip); db.flush(); db.add(TripMember(trip_id=trip.id, user_id=user.id, role='owner')); db.commit(); db.refresh(trip)
    return trip

@router.get('/trips/{trip_id}', response_model=TripOut)
def get_trip(trip_id: int, user: User=Depends(current_user), db: Session=Depends(get_db)):
    return membership(db,trip_id,user)

@router.patch('/trips/{trip_id}', response_model=TripOut)
async def patch_trip(trip_id: int, data: TripPatch, user: User=Depends(current_user), db: Session=Depends(get_db)):
    trip = membership(db,trip_id,user,owner=True)
    changes={k:v for k,v in data.model_dump(exclude_unset=True).items() if v is not None}
    if changes.get('end_date',trip.end_date) < changes.get('start_date',trip.start_date):
        raise HTTPException(422,'End date precedes start date')
    for key,value in changes.items(): setattr(trip,key,value)
    db.commit(); db.refresh(trip)
    await hub.emit(trip_id,{'type':'trip.updated','trip_id':trip_id,'fields':data.model_dump(exclude_unset=True, mode='json')})
    return trip

@router.delete('/trips/{trip_id}', status_code=204)
def delete_trip(trip_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    trip=membership(db,trip_id,user,owner=True)
    db.delete(trip); db.commit()

@router.post('/trips/{trip_id}/invites',status_code=201)
def create_invite(trip_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user,owner=True)
    token=secrets.token_urlsafe(32)
    db.add(TripInvite(trip_id=trip_id,token_hash=hashlib.sha256(token.encode()).hexdigest(),
                      expires_at=utcnow()+timedelta(days=3)))
    db.commit()
    return {'token':token,'expires_in_seconds':259200}

@router.post('/invites/{token}/accept',response_model=TripOut)
def accept_invite(token:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    hashed=hashlib.sha256(token.encode()).hexdigest()
    invite=db.scalar(select(TripInvite).where(TripInvite.token_hash==hashed).with_for_update())
    # SQLite returns naive datetimes; normalize comparisons to UTC.
    if not invite or invite.used_at is not None or invite.expires_at.replace(tzinfo=timezone.utc) < utcnow():
        raise HTTPException(410,'Invitation expired, already used, or invalid')
    if db.get(TripMember,(invite.trip_id,user.id)):
        raise HTTPException(409,'You are already a member')
    invite.used_by=user.id; invite.used_at=utcnow()
    db.add(TripMember(trip_id=invite.trip_id,user_id=user.id,role='member'))
    db.commit(); return db.get(Trip,invite.trip_id)
