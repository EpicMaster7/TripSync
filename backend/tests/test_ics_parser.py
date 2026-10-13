from pathlib import Path
import pytest

icalendar=pytest.importorskip('icalendar')
from app.services.calendar_feed import parse_calendar,FeedError

def test_demo_ics_complete_and_idempotent_fixture():
    data=Path(__file__).parents[2].joinpath('demo/seattle.ics').read_bytes()
    events=parse_calendar(data)
    assert len(events)==2
    assert events['seattle-hotel-001@tripsync.example.test']['title']=='Hotel check-in'
    assert len(parse_calendar(data))==2

def test_corrupted_ics_never_partially_accepted():
    data=b'BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:u1\nSUMMARY:broken\nDTSTART:20261101T150000Z\nEND:VEVENT\nEND:VCALENDAR'
    with pytest.raises(FeedError): parse_calendar(data)
