from typing import List, Dict, Any, Mapping
from rag.stores.base import BaseVectorStore
from rag.schema import ToolSchema, VectorDocument
from rag.config import settings
import json
import logging

logger = logging.getLogger(__name__)

class ToolVectorStore(BaseVectorStore):
    def __init__(self):
        super().__init__(settings.COLLECTION_TOOLS)
    
    def add_tool(self, tool: Mapping[str, Any]) -> None:
        """
        Index a tool for semantic retrieval.
        """
        try:
            # Normalize at the boundary
            schema = ToolSchema.model_validate(tool)

            # Semantic text ONLY (what embeddings should see)
            text_representation = (
                f"Tool: {schema.name}\n"
                f"Purpose: {schema.purpose}\n"
                f"Description: {schema.description}"
            )
            print(f"Storing Tool : {schema.name}")
            # Metadata = identifiers + location info (for dynamic loading)
            doc = VectorDocument(
                content=text_representation.strip(),
                metadata={
                    "tool_id": schema.id or schema.name,
                    "name": schema.name,
                    "description": schema.description,
                    "purpose": schema.purpose,
                    "tool_version": schema.version,
                    "module_path": schema.module_path,
                    "class_name": schema.class_name
                },
            )

            self.add_documents([doc])
        except Exception as e:
            logger.error(f"Error adding tool to vector store: {e}")
            raise

    def find_tools(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Finds tools relevant to a user query."""
        results = self.search(query, n_results=limit)
        
        tools = []
        for res in results:
            tools.append({
                "name": res.metadata.get("name"),
                "description": res.metadata.get("description"),
                "module_path": res.metadata.get("module_path"),
                "class_name": res.metadata.get("class_name"),
                "score": res.score
            })
        return tools
