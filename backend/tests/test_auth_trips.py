from datetime import datetime, timezone, timedelta
from app.models import TripInvite

def test_auth_signup_csrf_and_logout(client):
    assert client.get('/me').status_code==401
    assert client.post('/auth/register',json={'name':'Sam','email':'sam@example.test','password':'short'}).status_code==422
    body={'name':'Sam','email':'sam@example.test','password':'some-long-password'}
    assert client.post('/auth/register',json=body).status_code==201
    assert client.post('/auth/register',json=body).status_code==409
    assert client.post('/trips',json={}).status_code==403
    csrf=client.get('/me').json()['csrf_token'];client.headers['x-csrf-token']=csrf
    assert client.post('/auth/logout').status_code==200
    assert client.get('/me').status_code==401
    assert client.post('/auth/login',json={'email':body['email'],'password':'wrong-password'}).status_code==401
    assert client.post('/auth/login',json=body).status_code==200

def test_membership_invite_one_time_and_expiry(users,trip,db):
    alice,bob=users
    trip_id=trip['id']
    assert bob.get(f'/trips/{trip_id}').status_code==404
    assert bob.get(f'/trips/{trip_id}/items').status_code==404
    invite=alice.post(f'/trips/{trip_id}/invites').json()['token']
    accepted=bob.post(f'/invites/{invite}/accept')
    assert accepted.status_code==200,accepted.text
    assert bob.get(f'/trips/{trip_id}').status_code==200
    assert bob.post(f'/invites/{invite}/accept').status_code==410
    assert bob.post(f'/trips/{trip_id}/invites').status_code==403
    expired=alice.post(f'/trips/{trip_id}/invites').json()['token']
    record=db.query(TripInvite).order_by(TripInvite.id.desc()).first()
    record.expires_at=datetime.now(timezone.utc)-timedelta(days=1); db.commit()
    assert bob.post(f'/invites/{expired}/accept').status_code==410

def test_cross_trip_owner_only(users,trip):
    alice,bob=users
    assert bob.patch(f"/trips/{trip['id']}",json={'name':'Hijacked'}).status_code==404
    assert alice.patch(f"/trips/{trip['id']}",json={'start_date':'2027-01-01'}).status_code==422
    assert alice.patch(f"/trips/{trip['id']}",json={'name':'Seattle revised'}).status_code==200
