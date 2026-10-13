from datetime import timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import CalendarSubscription, ItineraryItem, SyncRun, utcnow
from .calendar_feed import fetch_feed, parse_calendar


def apply_events(db: Session, sub: CalendarSubscription, events: dict, run: SyncRun):
    """Merge one *complete* parsed feed in the caller's transaction."""
    existing = {item.external_uid: item for item in db.scalars(
        select(ItineraryItem).where(ItineraryItem.subscription_id == sub.id)
    ).all()}
    for uid, fields in events.items():
        item = existing.pop(uid, None)
        if item:
            def equal(field, expected):
                previous = getattr(item, field)
                if field in ('starts_at', 'ends_at') and previous.tzinfo is None:
                    previous = previous.replace(tzinfo=timezone.utc)
                return previous == expected
            if not all(equal(field, expected) for field, expected in fields.items()):
                for field, value in fields.items():
                    setattr(item, field, value)
                item.version += 1
                run.updated += 1
        else:
            db.add(ItineraryItem(trip_id=sub.trip_id, subscription_id=sub.id,
                                 external_uid=uid, source='ics', version=1, **fields))
            run.created += 1
    for item in existing.values():
        db.delete(item)
        run.deleted += 1


async def sync_subscription(db: Session, sub: CalendarSubscription):
    """Fetch, validate and atomically merge a remote feed; failures never erase old rows."""
    run = SyncRun(trip_id=sub.trip_id, subscription_id=sub.id, status='running')
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        body, etag, modified = await fetch_feed(sub.url, sub.etag, sub.last_modified)
        if body is not None:
            events = parse_calendar(body)
            apply_events(db, sub, events, run)
            sub.etag = etag
            sub.last_modified = modified
        sub.last_fetched_at = utcnow()
        sub.status = 'healthy'
        sub.error = None
        run.status = 'success'
        db.commit()
    except Exception as exc:
        db.rollback()
        sub = db.get(CalendarSubscription, sub.id)
        run = db.get(SyncRun, run.id)
        sub.status = 'error'
        sub.error = str(exc)[:500]
        run.status = 'failed'
        run.error = str(exc)[:500]
        db.commit()
    finally:
        run.finished_at = utcnow()
        db.commit()
        db.refresh(run)
    return run
