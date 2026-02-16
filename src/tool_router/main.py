from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .config import SERVICE_HOST, SERVICE_PORT

def create_app() -> FastAPI:
    app = FastAPI(
        title="Tool Router Service",
        description="Semantic Search and Discovery for Agent Tools",
        version="1.0.0"
    )

    # Allow Agents from anywhere (or restrict to specific subnets in prod)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app

app = create_app()

def start():
    """Entry point for poetry scripts or direct execution."""
    load_dotenv(override=True)
    uvicorn.run(
        "src.tool_router.main:app", 
        host=SERVICE_HOST, 
        port=SERVICE_PORT, 
        reload=True
    )

if __name__ == "__main__":
    start()
