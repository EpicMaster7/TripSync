"""Idempotently seed fake Seattle trip; DEMO_PASSWORD is required (never committed)."""
import os
from datetime import date,datetime,timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import User,Trip,TripMember,ItineraryItem
from .auth import hash_password

TRAVELERS=[('Alex Rivera','alex@tripsync.example.test'),('Morgan Chen','morgan@tripsync.example.test'),('Jamie Lee','jamie@tripsync.example.test')]
ACTIVITIES=[
  ('Arrive at Sea-Tac','2026-11-01T19:00:00Z','2026-11-01T20:00:00Z','Seattle–Tacoma International Airport','Meet at baggage claim'),
  ('Pike Place Market','2026-11-02T17:00:00Z','2026-11-02T18:30:00Z','Pike Place Market','Grab lunch and explore stalls'),
  ('Olympic Sculpture Park','2026-11-02T20:00:00Z','2026-11-02T21:00:00Z','Olympic Sculpture Park','Sunset photo walk'),
  ('Museum of Pop Culture','2026-11-03T21:00:00Z','2026-11-03T23:00:00Z','Seattle Center','Explore exhibits'),
  ('Ferry to Bainbridge Island','2026-11-04T18:00:00Z','2026-11-04T19:00:00Z','Colman Dock','Check ferry times separately'),
  ('Farewell brunch','2026-11-05T18:00:00Z','2026-11-05T19:30:00Z','Capitol Hill','Review photos'),
]
RESERVATIONS=[
  ('seattle-hotel-001@tripsync.example.test','Hotel check-in','2026-11-02T23:00:00Z','2026-11-02T23:30:00Z','Downtown Seattle'),
  ('seattle-tour-002@tripsync.example.test','Waterfront guided tour','2026-11-03T18:00:00Z','2026-11-03T19:30:00Z','Seattle waterfront'),
]

def main():
    password=os.environ.get('DEMO_PASSWORD','')
    if len(password)<10: raise SystemExit('Set DEMO_PASSWORD (at least 10 characters) to seed fictional accounts')
    with SessionLocal() as db:
        users=[]
        for name,email in TRAVELERS:
            user=db.scalar(select(User).where(User.email==email))
            if not user:
                user=User(name=name,email=email,password_hash=hash_password(password));db.add(user);db.flush()
            users.append(user)
        trip=db.scalar(select(Trip).where(Trip.name=='Seattle Explorer (demo)',Trip.owner_id==users[0].id))
        if not trip:
            trip=Trip(name='Seattle Explorer (demo)',destination='Seattle',timezone='America/Los_Angeles',start_date=date(2026,11,1),end_date=date(2026,11,5),owner_id=users[0].id)
            db.add(trip);db.flush()
            for idx,user in enumerate(users): db.add(TripMember(trip_id=trip.id,user_id=user.id,role='owner' if idx==0 else 'member'))
            for position,(title,start,end,location,notes) in enumerate(ACTIVITIES):
                db.add(ItineraryItem(trip_id=trip.id,title=title,starts_at=datetime.fromisoformat(start.replace('Z','+00:00')),ends_at=datetime.fromisoformat(end.replace('Z','+00:00')),location=location,notes=notes,position=position,created_by_id=users[position%3].id,owner_id=users[position%3].id,source='manual'))
            for uid,title,start,end,location in RESERVATIONS:
                # Fixture records reflect demo/seattle.ics; no remote calendar is fetched.
                db.add(ItineraryItem(trip_id=trip.id,title=title,starts_at=datetime.fromisoformat(start.replace('Z','+00:00')),ends_at=datetime.fromisoformat(end.replace('Z','+00:00')),location=location,source='ics',external_uid=uid))
            db.commit()
        print(f'Seeded fictional trip {trip.id} for {", ".join(u.email for u in users)}')

if __name__=='__main__':main()
