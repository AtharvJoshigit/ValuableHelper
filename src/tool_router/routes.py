from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from .manager import manager
from .models import ToolRegisterRequest, ToolQueryRequest, ToolResponse, ToolHealthStatus

router = APIRouter(prefix="/tools", tags=["tools"])

@router.on_event("startup")
async def startup_event():
    """Start the Vector Store connection on boot."""
    await manager.initialize()

@router.get("/health", response_model=ToolHealthStatus)
async def system_health():
    """Check if the router itself is healthy."""
    return ToolHealthStatus(tool_name="tool_router", status="active", message="System Online")

@router.post("/register", response_model=str)
async def register_tool(payload: ToolRegisterRequest):
    """Registers a new tool in the vector database."""
    try:
        tool_name = manager.register_tool(payload)
        return tool_name
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=List[ToolResponse])
async def search_tools(
    q: str, 
    limit: int = 5,
    permission_level: int = 0,
    tags: Optional[List[str]] = Query(None)
):
    """
    Semantic search for tools based on intent.
    Example: GET /tools/search?q="calculate date"&tags=utility
    """
    try:
        query = ToolQueryRequest(
            query=q, 
            limit=limit, 
            min_permission_level=permission_level,
            required_tags=tags or []
        )
        tools = manager.search_tools(query)
        return tools
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{name}", response_model=ToolResponse)
async def get_tool(name: str):
    """Retrieve a specific tool by name."""
    tool = manager.get_tool(name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@router.get("/{name}/health", response_model=ToolHealthStatus)
async def check_tool_health(name: str):
    """Check if a specific tool's code is importable/executable."""
    tool = manager.get_tool(name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    # Check the actual Python function path
    status = manager.check_tool_health(tool.function_call)
    return status
