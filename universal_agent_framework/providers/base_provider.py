from abc import ABC, abstractmethod
from typing import List, Iterator
from universal_agent_framework.core.types import Message, AgentResponse, StreamChunk
from universal_agent_framework.registry.base_tool import BaseTool

class BaseProvider(ABC):
    """
    Abstract base class for LLM providers.
    """
    
    @abstractmethod
    async def generate(self, history: List[Message], tools: List[BaseTool]) -> AgentResponse:
        """
        Generate a complete response from the model.
        
        Args:
            history: List of conversation messages
            tools: List of available tools
            
        Returns:
            AgentResponse object containing content and/or tool calls
        """
        pass

    @abstractmethod
    async def stream(self, history: List[Message], tools: List[BaseTool]) -> Iterator[StreamChunk]:
        """
        Stream the response from the model.
        
        Args:
            history: List of conversation messages
            tools: List of available tools
            
        Returns:
            Iterator of StreamChunk objects
        """
        pass
