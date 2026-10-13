# Engineering decisions (October 2026)

## WebSockets instead of polling for collaboration
Each authorized browser opens one WebSocket per trip. After a committed mutation, FastAPI broadcasts an event carrying its resource ID, version, and changed fields; React Query invalidates cached REST responses, treating the database as the source of truth. This is responsive and simpler than maintaining a client-side replicated data model. An in-memory hub only reaches clients connected to the same API process. The Docker configuration deliberately uses one web worker. Scale-out or cross-process scheduler notifications require a shared event bus such as Redis or PostgreSQL LISTEN/NOTIFY.

## Optimistic activity versions instead of last-write-wins
Every manual activity starts at version 1. Updates and deletions include the version last displayed to the user; a conditional SQL UPDATE/DELETE only succeeds if that version remains current. A losing editor receives HTTP 409 and must reload and reapply changes. This prevents silent lost updates without holding a database lock during human editing. Field-level merges, offline edits, and automatic conflict reconciliation are out of scope.

## Separate scheduler instead of scheduling inside FastAPI
The scheduler process runs APScheduler every 30 minutes by default, while the API only runs interactive requests and WebSockets. This prevents every Uvicorn worker from starting a duplicate timer and keeps timed jobs independent of request traffic. For production scale, add a cross-instance job lock, a queue, and a shared notifications transport; this demo assumes exactly one scheduler and one API instance. Failed calendar reads retain the last successful imported items and write an error SyncRun rather than clearing the itinerary.

## Feed safety and bounded imports
Feed fetching accepts HTTPS DNS names only, requires every resolved address to be globally routable, pins a validated IP to the TLS connection using the hostname for SNI, avoids proxy environment variables, rejects redirects and limits bodies to 1 MiB. Parsing occurs before any writes. Recurring event expansion is deliberately rejected rather than silently importing a partial series. Hostile feeds may still contain misleading human-readable text; content is displayed as text, not HTML.
