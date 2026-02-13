from typing import Any, Optional
from pydantic import Field
import requests
from engine.registry.base_tool import BaseTool

class WebScraperTool(BaseTool):
    """
    Scrapes a website using Jina Reader API and returns clean Markdown content.
    """
    name: str = "web_scraper"
    description: str = "Extracts clean textual content (Markdown) from a given URL using Jina Reader."
    url: Optional[str] = Field(None, description="The URL of the website to scrape.")

    def execute(self, **kwargs: Any) -> Any:
        url = kwargs.get("url", self.url)
        if not url:
            return {"status": "error", "message": "No URL provided for scraping."}
        
        # Using Jina Reader API (No API key required for basic usage)
        jina_url = f"https://r.jina.ai/{url}"
        
        try:
            headers = {
                "Accept": "text/event-stream" if kwargs.get("stream") else "text/plain"
            }
            response = requests.get(jina_url, headers=headers, timeout=20)
            response.raise_for_status()
            
            return {
                "status": "success",
                "url": url,
                "content": response.text[:5000] + "..." if len(response.text) > 5000 else response.text,
                "length": len(response.text)
            }
        except Exception as e:
            return {"status": "error", "message": f"Scraping failed: {str(e)}"}
