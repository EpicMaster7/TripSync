import asyncio
from datetime import datetime,timezone
import pytest
from app.models import CalendarSubscription,ItineraryItem
from app.services.calendar_feed import checked_url,FeedError
from app.services.trip_sync import sync_subscription

@pytest.mark.parametrize('url',[
  'http://example.org/events.ics','https://localhost/file.ics','https://127.0.0.1/a.ics',
  'https://169.254.169.254/latest/meta-data','https://user:pass@example.com/a.ics',
  'https://example.com:8443/a.ics'
])
def test_ssrf_schemes_rejected(url):
    with pytest.raises(FeedError): asyncio.run(checked_url(url))

def test_dns_private_address_blocked(monkeypatch):
    import socket
    def fake_getaddrinfo(*a,**kw): return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.10',443))]
    monkeypatch.setattr(socket,'getaddrinfo',fake_getaddrinfo)
    with pytest.raises(FeedError,match='non-public'):
        asyncio.run(checked_url('https://calendar.example.test/events.ics'))

def test_subscribe_ssrf_error(users,trip):
    alice,bob=users
    r=alice.post(f"/trips/{trip['id']}/calendar-subscriptions",json={'url':'https://127.0.0.1/a.ics'})
    assert r.status_code==422 and 'IP-address' in r.json()['detail']

def test_upsert_retry_and_no_data_loss(users,trip,db,monkeypatch,item_data):
    from app.services import trip_sync
    alice,bob=users;tid=trip['id']
    user=alice.get('/me').json()['user']
    manual=alice.post(f'/trips/{tid}/items',json=item_data).json()
    sub=CalendarSubscription(trip_id=tid,owner_id=user['id'],url='https://calendar.example.test/events.ics')
    db.add(sub);db.commit();db.refresh(sub)
    payload={'uid-1':{'title':'Reservation','starts_at':datetime(2026,11,2,9,tzinfo=timezone.utc),
                      'ends_at':datetime(2026,11,2,10,tzinfo=timezone.utc),'location':'Hotel','notes':''}}
    async def fetch(*args,**kwargs): return b'calendar',None,None
    monkeypatch.setattr(trip_sync,'fetch_feed',fetch)
    monkeypatch.setattr(trip_sync,'parse_calendar',lambda data:payload)
    one=asyncio.run(sync_subscription(db,sub))
    assert one.status=='success' and one.created==1
    two=asyncio.run(sync_subscription(db,sub))
    assert two.status=='success' and two.created==0 and two.updated==0
    assert db.query(ItineraryItem).filter_by(subscription_id=sub.id).count()==1
    payload['uid-1']={**payload['uid-1'],'title':'Reservation revised'}
    three=asyncio.run(sync_subscription(db,sub))
    assert three.updated==1
    async def timeout(*args,**kwargs): raise FeedError('timeout')
    monkeypatch.setattr(trip_sync,'fetch_feed',timeout)
    four=asyncio.run(sync_subscription(db,sub))
    assert four.status=='failed'
    assert db.query(ItineraryItem).filter_by(subscription_id=sub.id).count()==1
    assert db.get(ItineraryItem,manual['id']).source=='manual'

def test_successful_complete_feed_can_remove_obsolete_imports(users,trip,db,monkeypatch):
    from app.services import trip_sync
    alice,_=users;tid=trip['id']
    uid=alice.get('/me').json()['user']['id']
    sub=CalendarSubscription(trip_id=tid,owner_id=uid,url='https://calendar.example.test/events.ics')
    db.add(sub);db.commit();db.refresh(sub)
    data={
      'a':{'title':'A','starts_at':datetime(2026,11,3,9,tzinfo=timezone.utc), 'ends_at':datetime(2026,11,3,10,tzinfo=timezone.utc),'location':'','notes':''},
      'b':{'title':'B','starts_at':datetime(2026,11,3,11,tzinfo=timezone.utc), 'ends_at':datetime(2026,11,3,12,tzinfo=timezone.utc),'location':'','notes':''},
    }
    async def feed(*args,**kw): return b'fixture', '"etag-1"', None
    monkeypatch.setattr(trip_sync,'fetch_feed',feed)
    monkeypatch.setattr(trip_sync,'parse_calendar',lambda _:data)
    assert asyncio.run(sync_subscription(db,sub)).created==2
    del data['b']
    assert asyncio.run(sync_subscription(db,sub)).deleted==1
    assert db.query(ItineraryItem).filter_by(subscription_id=sub.id).count()==1
    async def not_modified(*args,**kw): return None,'"etag-1"',None
    monkeypatch.setattr(trip_sync,'fetch_feed',not_modified)
    assert asyncio.run(sync_subscription(db,sub)).deleted==0
    assert db.query(ItineraryItem).filter_by(subscription_id=sub.id).count()==1

def test_manual_import_replaces_previous_complete_feed(users,trip,db,monkeypatch):
    from app.api import calendar
    alice,bob=users;tid=trip['id']
    details={'a':{'title':'One','starts_at':datetime(2026,11,2,11,tzinfo=timezone.utc),
                  'ends_at':datetime(2026,11,2,12,tzinfo=timezone.utc),'location':'','notes':''}}
    monkeypatch.setattr(calendar,'parse_calendar',lambda _:details)
    route=f'/trips/{tid}/calendar-import/demo'
    r=alice.put(route,content='BEGIN:VCALENDAR',headers={'content-type':'text/calendar'})
    assert r.status_code==200,r.text
    assert r.json()['created']==1
    again=alice.put(route,content='BEGIN:VCALENDAR',headers={'content-type':'text/calendar'})
    assert again.json()['created']==0 and again.json()['updated']==0
    details['a']={**details['a'],'title':'Two'}
    newer=alice.put(route,content='BEGIN:VCALENDAR',headers={'content-type':'text/calendar'})
    assert newer.json()['updated']==1
    details.clear()
    removed=alice.put(route,content='BEGIN:VCALENDAR',headers={'content-type':'text/calendar'})
    assert removed.json()['deleted']==1
    assert db.query(ItineraryItem).filter_by(trip_id=tid,source='ics').count()==0
    assert alice.put(route,content='nothing',headers={'content-type':'application/json'}).status_code==415
    assert bob.put(route,content='data',headers={'content-type':'text/calendar'}).status_code==404

def test_manual_import_invalid_feed_keeps_previous_rows(users,trip,db,monkeypatch):
    from app.api import calendar
    alice,bob=users;tid=trip['id']
    route=f'/trips/{tid}/calendar-import/demo'
    first={'uid':{'title':'Reservation','starts_at':datetime(2026,11,3,9,tzinfo=timezone.utc),
                  'ends_at':datetime(2026,11,3,10,tzinfo=timezone.utc),'location':'','notes':''}}
    monkeypatch.setattr(calendar,'parse_calendar',lambda _:first)
    assert alice.put(route,content='a',headers={'content-type':'text/calendar'}).status_code==200
    def broken(_): raise FeedError('Invalid calendar')
    monkeypatch.setattr(calendar,'parse_calendar',broken)
    assert alice.put(route,content='bad',headers={'content-type':'text/calendar'}).status_code==422
    assert db.query(ItineraryItem).filter_by(trip_id=tid,source='ics').count()==1
    assert alice.put(route,content=b'a'*(1024*1024+1),headers={'content-type':'text/calendar'}).status_code==413
