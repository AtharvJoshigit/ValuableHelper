
from engine.registry.base_tool import BaseTool

class HelloTool(BaseTool):
    """A simple tool to verify injection works."""
    def __init__(self):
        super().__init__(
            name="hello_world",
            description="Returns a friendly greeting to verify tool injection."
        )

    async def execute(self, name: str = "Boss") -> str:
        return f"Hello {name}! Tool injection is officially working. (Rocket Emoji here)"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string", 
                    "description": "The name of the person to greet."
                }
            },
            "required": ["name"]
        }
