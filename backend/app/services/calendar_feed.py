"""HTTPS-only ICS transport. The resolved public IP is pinned for the TLS connection.

No redirects or proxies, maximum 1 MiB, public DNS answers only, HTTPS port 443.
"""
import asyncio, ipaddress, socket
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx

MAX_BYTES=1024*1024

class FeedError(ValueError): pass
class TemporaryFeedError(FeedError): pass

def _safe_address(value):
    ip=ipaddress.ip_address(value)
    return ip.is_global and not ip.is_multicast and not ip.is_reserved

async def checked_url(url: str):
    try: parts=urlsplit(url)
    except ValueError: raise FeedError('Invalid feed URL')
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise FeedError('Use an HTTPS URL without credentials or fragments')
    try: port=parts.port
    except ValueError: raise FeedError('Invalid HTTPS port')
    if port not in (None,443) or len(url)>2048:
        raise FeedError('Only HTTPS port 443 is permitted; maximum URL length 2048')
    host=parts.hostname
    try:
        ipaddress.ip_address(host)
        raise FeedError('IP-address URLs are not allowed')
    except ValueError as exc:
        if isinstance(exc,FeedError): raise
    try:
        answers=await asyncio.to_thread(socket.getaddrinfo,host,443,type=socket.SOCK_STREAM)
    except OSError: raise FeedError('Cannot resolve calendar host')
    addresses=sorted({answer[4][0] for answer in answers})
    if not addresses or not all(_safe_address(address) for address in addresses):
        raise FeedError('Calendar host resolves to a non-public address')
    return parts, addresses[0]

async def fetch_feed(url: str, etag=None, last_modified=None):
    """Retry transient network/server errors at most twice with bounded backoff."""
    for attempt in range(3):
        try:
            return await _fetch_once(url, etag, last_modified)
        except TemporaryFeedError:
            if attempt == 2: raise
            await asyncio.sleep(0.5 * 2**attempt)

async def _fetch_once(url: str, etag=None, last_modified=None):
    parts,ip=await checked_url(url)
    # Direct IP TLS connection with original hostname as SNI and Host.
    # Prevents DNS rebinding between validation and connection.
    ip_host=f'[{ip}]' if ':' in ip else ip
    target=f'https://{ip_host}{parts.path or "/"}'
    if parts.query: target+='?'+parts.query
    headers={'Host':parts.hostname,'Accept':'text/calendar'}
    if etag: headers['If-None-Match']=etag
    if last_modified: headers['If-Modified-Since']=last_modified
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=5),trust_env=False,follow_redirects=False) as client:
            async with client.stream('GET',target,headers=headers,extensions={'sni_hostname':parts.hostname}) as response:
                if response.status_code==304: return None,etag,last_modified
                if 300<=response.status_code<400: raise FeedError('Calendar redirects are blocked')
                response.raise_for_status()
                chunks=[]; count=0
                async for chunk in response.aiter_bytes():
                    count+=len(chunk)
                    if count>MAX_BYTES: raise FeedError('Calendar exceeds 1 MiB limit')
                    chunks.append(chunk)
                return b''.join(chunks), response.headers.get('etag'),response.headers.get('last-modified')
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (429, 502, 503, 504):
            raise TemporaryFeedError(f'Temporary calendar HTTP {exc.response.status_code}') from exc
        raise FeedError(f'Calendar HTTP {exc.response.status_code}') from exc
    except httpx.RequestError as exc:
        raise TemporaryFeedError(f'Temporary calendar network error: {type(exc).__name__}') from exc

def parse_calendar(body: bytes):
    """Parse complete, non-recurring VEVENTs via maintained icalendar library.

    All-or-nothing validation protects existing rows against malformed feeds.
    """
    try:
        from icalendar import Calendar
    except ImportError as exc:
        raise FeedError('icalendar dependency is unavailable') from exc
    try:
        calendar=Calendar.from_ical(body)
        if calendar.name != 'VCALENDAR': raise ValueError('Not a VCALENDAR')
        events={}
        for component in calendar.walk('VEVENT'):
            if component.get('RECURRENCE-ID') or component.get('RRULE'):
                raise ValueError('Recurring events are unsupported (no partial import)')
            uid=str(component.get('UID','')).strip()
            title=str(component.get('SUMMARY','')).strip()
            start=component.decoded('DTSTART')
            end=component.decoded('DTEND')
            if not uid or len(uid)>255 or not title or not isinstance(start,datetime) or not isinstance(end,datetime):
                raise ValueError('Every event needs UID, SUMMARY, DTSTART and DTEND with times')
            if start.tzinfo is None or end.tzinfo is None or end<=start or uid in events:
                raise ValueError('Invalid/duplicate UID or event timestamps')
            events[uid]={'title':title[:200], 'starts_at':start.astimezone(timezone.utc),
                         'ends_at':end.astimezone(timezone.utc),'location':str(component.get('LOCATION',''))[:255],
                         'notes':str(component.get('DESCRIPTION',''))[:5000]}
        return events
    except Exception as exc:
        raise FeedError(f'Invalid or unsupported ICS feed: {str(exc)[:180]}') from exc
