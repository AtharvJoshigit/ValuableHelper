import logging
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manages active WebSocket connections and broadcasts status updates
    to the frontend face.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
            cls._instance.active_connections: List[WebSocket] = []
        return cls._instance

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast_status(self, status: str, details: str = None):
        """
        Send a status update to all connected clients.
        Status: 'idle', 'thinking', 'tool_use', 'speaking'
        """
        await self.broadcast({"type": "status", "status": status, "details": details})

    async def broadcast_mode(self, mode: str):
        """
        Send a mode change command (e.g., 'heavy', 'lazy') to all clients.
        """
        await self.broadcast({"type": "mode", "mode": mode})

    async def broadcast(self, message: Dict[str, Any]):
        """
        Base broadcast method to send any JSON message.
        """
        disconnected_sockets = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected_sockets.append(connection)

        # Cleanup dead connections
        for dead_socket in disconnected_sockets:
            self.disconnect(dead_socket)

# Global accessor
def get_websocket_manager():
    return WebSocketManager()
