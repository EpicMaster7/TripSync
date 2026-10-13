import pytest
from starlette.websockets import WebSocketDisconnect

def test_items_conflict_authorization_and_ws(users,trip,item_data):
    alice,bob=users; tid=trip['id']
    invite=alice.post(f'/trips/{tid}/invites').json()['token']
    assert bob.post(f'/invites/{invite}/accept').status_code==200
    assert alice.post(f'/trips/{tid}/items',json={**item_data,'ends_at':item_data['starts_at']}).status_code==422
    with bob.websocket_connect(f'/ws/trips/{tid}',headers={'origin':'http://localhost:5173','cookie':f'tripsync_session={bob.cookies.get("tripsync_session")}' }) as ws:
        response=alice.post(f'/trips/{tid}/items',json=item_data)
        assert response.status_code==201,response.text
        item=response.json()
        event=ws.receive_json();assert event['type']=='item.created' and event['version']==1
        updated=alice.patch(f'/trips/{tid}/items/{item["id"]}',json={'version':1,'title':'Tea'})
        assert updated.status_code==200, updated.text
        assert ws.receive_json()['type']=='item.updated'
        stale=bob.patch(f'/trips/{tid}/items/{item["id"]}',json={'version':1,'title':'Overwrite'})
        assert stale.status_code==409
        assert bob.get(f'/trips/{tid}/items').json()[0]['title']=='Tea'
        assert bob.delete(f'/trips/{tid}/items/{item["id"]}?version=1').status_code==409
        assert alice.delete(f'/trips/{tid}/items/{item["id"]}?version=2').status_code==204
        assert ws.receive_json()['type']=='item.deleted'

def test_ws_rejects_origin_and_nonmember(users,trip):
    alice,bob=users; tid=trip['id']
    with pytest.raises(WebSocketDisconnect):
        with bob.websocket_connect(f'/ws/trips/{tid}',headers={'origin':'http://localhost:5173','cookie':f'tripsync_session={bob.cookies.get("tripsync_session")}' }): pass
    with pytest.raises(WebSocketDisconnect):
        with alice.websocket_connect(f'/ws/trips/{tid}',headers={'origin':'https://attacker.test','cookie':f'tripsync_session={alice.cookies.get("tripsync_session")}' }): pass

def test_invalid_owner_and_offset(users,trip,item_data):
    alice,bob=users; tid=trip['id']
    assert alice.post(f'/trips/{tid}/items',json={**item_data,'owner_id':98765}).status_code==422
    assert alice.post(f'/trips/{tid}/items',json={**item_data,'starts_at':'2026-11-01T08:30:00'}).status_code==422

def test_dst_offsets(users,trip,item_data):
    alice,bob=users; tid=trip['id']
    first=alice.post(f'/trips/{tid}/items',json={**item_data,'title':'First 1:30','starts_at':'2026-11-01T01:30:00-07:00','ends_at':'2026-11-01T01:45:00-07:00'})
    second=alice.post(f'/trips/{tid}/items',json={**item_data,'title':'Second 1:30','starts_at':'2026-11-01T01:30:00-08:00','ends_at':'2026-11-01T01:45:00-08:00'})
    assert first.status_code==201 and second.status_code==201
    items=alice.get(f'/trips/{tid}/items').json()
    assert [i['title'] for i in items]==['First 1:30','Second 1:30']
