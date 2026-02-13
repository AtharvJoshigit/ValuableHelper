from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import os
import asyncio
from typing import List, Dict

from infrastructure.websocket_manager import get_websocket_manager
from infrastructure.command_bus import CommandBus
from app.app_context import get_app_context
from domain.event import Event, EventType

# Setup Logging
logger = logging.getLogger("ValH_Server")

app = FastAPI(title="ValH Interface")

# --- WEBSOCKET ENDPOINT ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    manager = get_websocket_manager()
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        manager.disconnect(websocket)

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_index():
    file_path = os.path.join(os.path.dirname(__file__), 'index.html')
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("index.html not found", status_code=404)

@app.get("/style.css")
async def read_css():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'style.css'))

@app.get("/script.js")
async def read_js():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'script.js'))

# API: Chat Endpoint
@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message")
    
    if not message:
        return JSONResponse({"status": "error", "message": "No message provided"}, status_code=400)

    # Push to Command Bus
    bus = get_app_context().command_bus
    event = Event(
        type=EventType.USER_MESSAGE,
        payload={
            "chat_id": 0, # UI Chat ID
            "text": message
        },
        source="web_ui"
    )
    await bus.send(event)
    
    return {"status": "sent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
