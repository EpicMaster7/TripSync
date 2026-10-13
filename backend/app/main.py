from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, Request
from sqlalchemy.orm import Session
from .db import get_db
from .auth import ws_user
from .api import auth, trips, items, calendar
from .api.trips import membership
from .services.broadcast import hub

app=FastAPI(title='TripSync API', version='0.1.0')

@app.middleware('http')
async def origin_guard(request:Request,call_next):
    # Mitigates CSRF for unauthenticated session-setting endpoints, too.
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        import os
        if origin and origin != os.getenv('APP_ORIGIN','http://localhost:5173'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Origin not allowed'},status_code=403)
    return await call_next(request)

app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(items.router)
app.include_router(calendar.router)

@app.get('/health')
def health(): return {'ok':True}

@app.websocket('/ws/trips/{trip_id}')
async def ws_trip(ws:WebSocket,trip_id:int,db:Session=Depends(get_db)):
    user=ws_user(ws,db)
    if not user:
        await ws.close(code=1008);return
    try: membership(db,trip_id,user)
    except HTTPException:
        await ws.close(code=1008);return
    await hub.join(trip_id,ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: pass
    finally: hub.leave(trip_id,ws)
