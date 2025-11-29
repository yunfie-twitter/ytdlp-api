from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Register new WebSocket connection"""
        await websocket.accept()
        
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        
        self.active_connections[task_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove WebSocket connection"""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
    
    async def send_progress(self, task_id: str, data: dict):
        """Send progress update to all connected clients"""
        if task_id in self.active_connections:
            message = json.dumps(data)
            
            # Send to all connections
            disconnected = set()
            for websocket in self.active_connections[task_id]:
                try:
                    await websocket.send_text(message)
                except Exception:
                    disconnected.add(websocket)
            
            # Clean up disconnected
            for websocket in disconnected:
                self.disconnect(websocket, task_id)
    
    async def broadcast_to_task(self, task_id: str, message: str):
        """Broadcast message to all connections for a task"""
        if task_id in self.active_connections:
            for websocket in list(self.active_connections[task_id]):
                try:
                    await websocket.send_text(message)
                except Exception:
                    self.disconnect(websocket, task_id)

ws_manager = WebSocketManager()