from typing import Any, List, Optional
from pydantic import Field
from duckduckgo_search import DDGS
from engine.registry.base_tool import BaseTool

class WebSearchTool(BaseTool):
    """
    Searches the web with DuckDuckGo and returns the results.
    """
    name: str = "web_search"
    description: str = "Searches the web for a given query and returns the top results."
    query: Optional[str] = Field("N/A", description="The search query.")
    num_results: int = Field(default=5, description="The number of results to return.")

    def execute(self, **kwargs: Any) -> Any:
        query = kwargs.get("query", self.query)
        num_results = kwargs.get("num_results", self.num_results)
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        
        return {"status": "success", "results": results}
