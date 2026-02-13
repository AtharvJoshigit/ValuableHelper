from typing import Any
from engine.registry.base_tool import BaseTool
import random

class RandomExcuseTool(BaseTool):
    """
    Generates a standard developer excuse for broken code.
    Useful when you need to deflect blame immediately.
    """
    name: str = "generate_dev_excuse"
    description: str = "Generates a standard developer excuse for broken code."

    def execute(self, **kwargs: Any) -> str:
        excuses = [
            "It works on my machine.",
            "It's a known issue with the legacy codebase.",
            "I think that's a hardware problem.",
            "The third-party API is returning garbage.",
            "It was working 5 minutes ago.",
            "Must be a caching issue.",
            "The Wi-Fi in here is interfering with the logic gates.",
            "That's not a bug, it's an undocumented feature.",
            "Solar flares are flipping bits in memory."
        ]
        return random.choice(excuses)
