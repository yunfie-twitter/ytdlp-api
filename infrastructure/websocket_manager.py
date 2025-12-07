"""WebSocket connection management"""
import logging
from fastapi import WebSocket
from typing import Dict, List

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for tasks"""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Connect a WebSocket for a task"""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"WebSocket connected for task {task_id}")
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Disconnect a WebSocket"""
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if len(self.active_connections[task_id]) == 0:
                del self.active_connections[task_id]
            logger.info(f"WebSocket disconnected for task {task_id}")
    
    async def broadcast(self, task_id: str, message: dict):
        """Broadcast message to all connections for a task"""
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to task {task_id}: {e}")

ws_manager = WebSocketManager()
