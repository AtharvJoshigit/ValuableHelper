import importlib
import logging
from typing import List, Dict, Optional, Any
from .models import ToolRegisterRequest, ToolQueryRequest, ToolResponse, ToolHealthStatus, ToolMetadata
from src.rag.stores.tools import ToolVectorStore
from src.rag.schema import ToolSchema

logger = logging.getLogger(__name__)

class ToolManager:
    """Manages tool lifecycle, registration, and discovery."""

    def __init__(self):
        self.vector_store: Optional[ToolVectorStore] = None
        self._tool_cache: Dict[str, ToolResponse] = {}

    async def initialize(self):
        """Loads the vector store (heavy operation). Call on startup."""
        logger.info("Initializing Tool Vector Store...")
        self.vector_store = ToolVectorStore()
        # Optionally populate cache from DB here if needed
        logger.info("Tool Manager Ready.")

    def register_tool(self, tool: ToolRegisterRequest) -> str:
        """Adds a tool to the RAG index and local cache."""
        if not self.vector_store:
            raise RuntimeError("ToolManager not initialized. Call initialize() first.")

        # 1. Update Vector DB (for semantic search)
        self.vector_store.add_tool(ToolSchema(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            function_call=tool.function_call,
            metadata=tool.metadata.dict()
        ))

        # 2. Update Cache (for fast lookup by name)
        self._tool_cache[tool.name] = ToolResponse(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            metadata=tool.metadata,
            health=self.check_tool_health(tool.function_call)
        )
        logger.info(f"Registered tool: {tool.name}")
        return tool.name

    def search_tools(self, query: ToolQueryRequest) -> List[ToolResponse]:
        """Semantically search for tools, filtering by permission and tags."""
        if not self.vector_store:
            raise RuntimeError("ToolManager not initialized.")

        # 1. Semantic Search from RAG
        raw_results = self.vector_store.find_tools(query.query, limit=query.limit * 2) # Fetch extra for filtering

        filtered_tools = []
        for res in raw_results:
            tool_name = res.get("name")
            tool_meta = res.get("metadata", {})
            
            # 2. Re-construct Metadata Object safely
            metadata = ToolMetadata(**tool_meta) if tool_meta else ToolMetadata()

            # 3. Apply Filters
            # Permission Check
            if metadata.min_permission_level > query.min_permission_level:
                continue
            
            # Tag Check (Must contain ALL required tags)
            if query.required_tags and not all(tag in metadata.tags for tag in query.required_tags):
                continue
            
            # 4. Construct Response
            response = ToolResponse(
                name=tool_name,
                description=res.get("description", ""),
                args_schema=res.get("args_schema", {}),
                metadata=metadata,
                health=self.check_tool_health(res.get("function_call", ""))
            )
            filtered_tools.append(response)

            if len(filtered_tools) >= query.limit:
                break
        
        return filtered_tools

    def get_tool(self, name: str) -> Optional[ToolResponse]:
        """Direct lookup by name."""
        return self._tool_cache.get(name)

    def check_tool_health(self, function_path: str) -> ToolHealthStatus:
        """Verifies if the python function is importable."""
        status = "active"
        msg = "Ready"
        
        try:
            if not function_path:
                raise ValueError("No function path provided")
            
            module_name, func_name = function_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            if not hasattr(module, func_name):
                status = "degraded"
                msg = f"Function {func_name} not found in {module_name}"
        except Exception as e:
            status = "offline"
            msg = str(e)

        return ToolHealthStatus(
            tool_name=function_path,
            status=status,
            message=msg
        )

# Singleton Instance
manager = ToolManager()
