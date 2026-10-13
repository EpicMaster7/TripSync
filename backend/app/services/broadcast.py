import asyncio
from collections import defaultdict
from fastapi import WebSocket

class Hub:
    def __init__(self):
        self.clients: dict[int, set[WebSocket]] = defaultdict(set)
    async def join(self, trip_id: int, socket: WebSocket):
        await socket.accept()
        self.clients[trip_id].add(socket)
    def leave(self, trip_id: int, socket: WebSocket):
        self.clients[trip_id].discard(socket)
    async def emit(self, trip_id: int, payload: dict):
        sockets = list(self.clients.get(trip_id, ()))
        if not sockets: return
        results = await asyncio.gather(*(ws.send_json(payload) for ws in sockets), return_exceptions=True)
        for ws, result in zip(sockets, results):
            if isinstance(result, Exception): self.leave(trip_id, ws)

hub = Hub()
