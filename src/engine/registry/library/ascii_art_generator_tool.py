
from engine.registry.base_tool import BaseTool
import pyfiglet

class AsciiArtTool(BaseTool):
    """
    Generates ASCII art text banners using the pyfiglet library.
    Useful for making announcements or adding style to logs.
    """
    def __init__(self):
        super().__init__(
            name="ascii_art_generator",
            description="Generates ASCII art text banners from input string."
        )

    def execute(self, text: str, font: str = "standard") -> str:
        try:
            # We must import inside execute to ensure the library is loaded
            # after dynamic installation if needed, though here it's already installed.
            import pyfiglet
            result = pyfiglet.figlet_format(text, font=font)
            return f"\n{result}\n"
        except Exception as e:
            return f"Error generating ASCII art: {str(e)}"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to convert to ASCII art."
                },
                "font": {
                    "type": "string",
                    "description": "The font style to use (default: 'standard'). Other options: 'slant', '3-d', '5lineoblique', 'banner3-D'.",
                    "default": "standard"
                }
            },
            "required": ["text"]
        }
