import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import logging
from src.infrastructure.websocket_manager import get_websocket_manager

# Initialize FastAPI
app = FastAPI()
logger = logging.getLogger("Server")

# Get absolute path to 'src' directory where index.html lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static files (css, js, images)
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")

@app.get("/")
async def get():
    # Explicitly use utf-8 to handle emojis/special chars
    with open(os.path.join(BASE_DIR, "index.html"), 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    manager = get_websocket_manager()
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe handle incoming pings later
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def run_server(host="0.0.0.0", port=8000):
    """Entry point to run the server programmatically."""
    uvicorn.run(app, host=host, port=port, log_level="info")
