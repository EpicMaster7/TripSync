from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from ..auth import current_user
from ..db import get_db
from ..models import ItineraryItem, TripMember, User
from ..schemas import ItemBase, ItemPatch, ItemOut
from ..services.broadcast import hub
from .trips import membership

router=APIRouter()

def _owner_allowed(db, trip_id, uid):
    if uid is not None and not db.get(TripMember,(trip_id,uid)):
        raise HTTPException(422,'Owner must belong to trip')

def _utc(value): return value.astimezone(timezone.utc)

def _validate_dates(start,end):
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise HTTPException(422,'Timestamps need offsets and end must follow start')

@router.get('/trips/{trip_id}/items',response_model=list[ItemOut])
def items(trip_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user)
    return db.scalars(select(ItineraryItem).where(ItineraryItem.trip_id==trip_id).order_by(ItineraryItem.starts_at,ItineraryItem.position,ItineraryItem.id)).all()

@router.post('/trips/{trip_id}/items',response_model=ItemOut,status_code=201)
async def create_item(trip_id:int,data:ItemBase,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user); _owner_allowed(db,trip_id,data.owner_id)
    fields=data.model_dump(mode='python'); fields['link']=str(data.link) if data.link else None
    fields['starts_at']=_utc(data.starts_at); fields['ends_at']=_utc(data.ends_at)
    item=ItineraryItem(trip_id=trip_id,created_by_id=user.id,source='manual',version=1,**fields)
    db.add(item); db.commit(); db.refresh(item)
    await hub.emit(trip_id,{'type':'item.created','trip_id':trip_id,'item_id':item.id,'version':item.version,'fields':ItemOut.model_validate(item).model_dump(mode='json')})
    return item

@router.patch('/trips/{trip_id}/items/{item_id}',response_model=ItemOut)
async def patch_item(trip_id:int,item_id:int,data:ItemPatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user)
    item=db.scalar(select(ItineraryItem).where(ItineraryItem.id==item_id,ItineraryItem.trip_id==trip_id))
    if not item: raise HTTPException(404,'Item not found')
    if item.source!='manual': raise HTTPException(403,'Imported items are read-only; edit calendar source')
    if item.version!=data.version: raise HTTPException(409,'Item changed elsewhere. Reload latest item and try again')
    change=data.model_dump(exclude_unset=True,exclude={'version'})
    if 'owner_id' in change: _owner_allowed(db,trip_id,change['owner_id'])
    for field in ('starts_at','ends_at'):
        if field in change and change[field] is not None:
            if change[field].tzinfo is None: raise HTTPException(422,'Timestamp needs timezone offset')
            change[field]=_utc(change[field])
    start=change.get('starts_at') or item.starts_at
    end=change.get('ends_at') or item.ends_at
    # SQLite date/time columns drop tzinfo; compare as UTC for both backends.
    if start.tzinfo is None: start=start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None: end=end.replace(tzinfo=timezone.utc)
    _validate_dates(start,end)
    if 'link' in change and change['link'] is not None: change['link']=str(change['link'])
    change={k:v for k,v in change.items() if v is not None or k in ('link','owner_id')}
    result=db.execute(update(ItineraryItem).where(ItineraryItem.id==item_id,ItineraryItem.trip_id==trip_id,ItineraryItem.version==data.version).values(**change,version=ItineraryItem.version+1))
    if not result.rowcount:
        db.rollback(); raise HTTPException(409,'Item changed elsewhere. Reload latest item and try again')
    db.commit(); db.expire_all(); item=db.get(ItineraryItem,item_id)
    await hub.emit(trip_id,{'type':'item.updated','trip_id':trip_id,'item_id':item.id,'version':item.version,'fields':ItemOut.model_validate(item).model_dump(mode='json')})
    return item

@router.delete('/trips/{trip_id}/items/{item_id}',status_code=204)
async def delete_item(trip_id:int,item_id:int,version:int=Query(ge=1),user:User=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,trip_id,user)
    item=db.scalar(select(ItineraryItem).where(ItineraryItem.id==item_id,ItineraryItem.trip_id==trip_id))
    if not item: raise HTTPException(404,'Item not found')
    if item.source!='manual': raise HTTPException(403,'Imported items are read-only')
    result=db.execute(delete(ItineraryItem).where(ItineraryItem.id==item_id,ItineraryItem.trip_id==trip_id,ItineraryItem.version==version))
    if not result.rowcount: db.rollback(); raise HTTPException(409,'Item changed elsewhere. Reload before deleting')
    db.commit(); await hub.emit(trip_id,{'type':'item.deleted','trip_id':trip_id,'item_id':item_id,'version':version})
