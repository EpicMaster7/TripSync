"""Only the separate scheduler container runs this module."""
import asyncio, os
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select
from .db import SessionLocal
from .models import CalendarSubscription
from .services.trip_sync import sync_subscription

async def tick():
    with SessionLocal() as db:
        ids=db.scalars(select(CalendarSubscription.id).where(CalendarSubscription.url.like('https://%'))).all()
    for id_ in ids:
        with SessionLocal() as db:
            sub=db.get(CalendarSubscription,id_)
            if sub: await sync_subscription(db,sub)

def main():
    scheduler=BlockingScheduler(timezone='UTC')
    scheduler.add_job(lambda: asyncio.run(tick()),'interval',minutes=int(os.getenv('SYNC_INTERVAL_MINUTES','30')),
                      id='calendar-sync',max_instances=1,coalesce=True,misfire_grace_time=120,next_run_time=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    scheduler.start()

if __name__=='__main__': main()
