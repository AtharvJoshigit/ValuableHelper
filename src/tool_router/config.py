import os

# Service Settings
SERVICE_HOST = os.getenv("TOOL_ROUTER_HOST", "127.0.0.1")
SERVICE_PORT = int(os.getenv("TOOL_ROUTER_PORT", "8000"))
