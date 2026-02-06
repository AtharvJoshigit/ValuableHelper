import logging
from typing import Any, Optional
from pydantic import Field, PrivateAttr
from engine.registry.base_tool import BaseTool
from engine.core.types import Message, Role

logger = logging.getLogger(__name__)

class AgentWrapper(BaseTool):
    """
    Wraps an Agent instance as a Tool, allowing for nested multi-agent systems.
    """
    # Schema field: The input for the sub-agent
    task_input: str = Field(..., description="The specific task or question for the sub-agent to handle.")
    
    # Private attribute to store the agent instance (not included in JSON schema)
    _agent: Any = PrivateAttr()
    _clear_memory: bool = PrivateAttr(default=True)
    def __init__(self, agent: Any, name: str, description: str, clear_memory: bool = True):
        """
        Initialize the wrapper.
        
        Args:
            agent: The Agent instance to wrap.
            name: The name the parent agent will use to call this sub-agent.
            description: Description for the parent agent to know when to use this sub-agent.
        """
        super().__init__(name=name, description=description, task_input="")
        self._agent = agent
        self._clear_memory = clear_memory

    def execute(self, **kwargs) -> Any:
        """
        Synchronous execution is not supported as Agents are inherently asynchronous.
        """
        raise NotImplementedError("AgentWrapper requires async execution. Use execute_async.")

    async def execute_async(self, **kwargs) -> Any:
        """
        Execute the sub-agent's run loop.
        """
        # Extract the input from kwargs (sent by the LLM)
        input_text = kwargs.get("task_input")
        if not input_text:
            return {"status": "error", "error": "No 'task_input' provided to the sub-agent."}
        
        try:
            # Optionally clear sub-agent memory for isolation
            if self._clear_memory:
                self._agent.memory.clear()
                # Re-add system prompt if it exists
                
                if self._agent.system_prompt: 
                    self._agent.memory.add_message(
                        Message(role=Role.SYSTEM, content=self._agent.system_prompt)
                    )
                result = await self._agent.run(input_text)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Error in sub-agent execution: {e}")
            return {"status": "error", "error": str(e)}
