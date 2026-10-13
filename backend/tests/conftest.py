import os
os.environ['SESSION_SECRET']='test-secret-string-that-is-over-thirty-two-characters'
os.environ['APP_ORIGIN']='http://localhost:5173'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.main import app

@pytest.fixture
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as session: yield session
    engine.dispose()

@pytest.fixture
def client(db):
    def db_override(): yield db
    app.dependency_overrides[get_db]=db_override
    with TestClient(app, base_url='http://localhost:5173') as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def users(client):
    alice=TestClient(client.app,base_url='http://localhost:5173')
    bob=TestClient(client.app,base_url='http://localhost:5173')
    for c,name in [(alice,'alice'),(bob,'bob')]:
        assert c.post('/auth/register',json={'name':name,'email':f'{name}@example.test','password':'long-password-123'}).status_code==201
        c.headers['x-csrf-token']=c.get('/me').json()['csrf_token']
    yield alice,bob
    alice.close(); bob.close()

@pytest.fixture
def trip(users):
    alice,bob=users
    r=alice.post('/trips',json={'name':'Seattle','destination':'Seattle','timezone':'America/Los_Angeles','start_date':'2026-11-01','end_date':'2026-11-05'})
    assert r.status_code==201, r.text
    return r.json()

@pytest.fixture
def item_data():
    return {'title':'Coffee','starts_at':'2026-11-01T08:30:00-08:00','ends_at':'2026-11-01T09:30:00-08:00','location':'Cafe'}
