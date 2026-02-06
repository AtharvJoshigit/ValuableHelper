import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from universal_agent_framework.core.agent import Agent
from universal_agent_framework.providers.google.provider import GoogleProvider
from universal_agent_framework.registry.tool_registry import ToolRegistry
from universal_agent_framework.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # 1. Load Environment Variables (Ensure GOOGLE_API_KEY is set)
    load_dotenv()
    
    # 2. Initialize the Provider (Gemini)
    provider = GoogleProvider(model_id="gemini-3-flash-preview")
    
    # 3. Initialize the Registry and Tools
    registry = ToolRegistry()
    registry.register(ListDirectoryTool())
    registry.register(ReadFileTool())
    
    def _load_system_prompt() -> Optional[str]:
        """Load system prompt from file."""
        try:
            prompt_path = Path.cwd() / "me" / "whoami.md"
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"⚠️  Could not load system prompt: {e}")
        return None

    # 4. Initialize the Agent
    agent = Agent(
        provider=provider,
        registry=registry,
        system_prompt=_load_system_prompt()
    )
    
    # 5. Run the Agent
    # print("--- Starting Agent (Standard Run) ---")
    # question = "List the files in the current directory"
    # response = await agent.run(question)
    
    # print("\nFinal Response:")
    # print(response)
    # print("-" * 40)
    print("\n--- Starting Agent (Streaming Run) ---")
    user_input = ''
    while user_input != 'q': 
    # 6. Test Streaming
        user_input = input("Write 'q' to quit. or chat here: ")
        if user_input == 'q': 
            break
        async for chunk in agent.stream(user_input):
            if chunk.content:
                print(chunk.content, end="", flush=True)
        print("\n" + "-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
