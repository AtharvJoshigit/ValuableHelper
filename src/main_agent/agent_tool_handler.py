"""
Enhanced Agent Handler - V2

NEW FEATURES:
1. Supports both agents AND tools
2. Parallel execution capability
3. Dynamic registration
4. Better error handling
5. Type safety
"""

from typing import Dict, Any, List, Optional, Callable, Union
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from enum import Enum


class ExecutableType(Enum):
    """Type of executable (agent or tool)."""
    AGENT = "agent"
    TOOL = "tool"


@dataclass
class ExecutionResult:
    """Result from executing an agent or tool."""
    status: str  # "success" or "error"
    name: str  # Agent/tool name
    result: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ExecutableConfig:
    """Configuration for an agent or tool."""
    name: str
    executable_type: ExecutableType
    instance: Any  # The actual agent/tool instance or function
    description: str
    parameters_schema: Dict[str, Any]
    parallel_safe: bool = True  # Can this be run in parallel?
    metadata: Optional[Dict[str, Any]] = None


class AgentToolHandler:
    """
    Enhanced handler that manages both agents and tools.
    
    Features:
    - Register agents and tools dynamically
    - Execute sequentially or in parallel
    - Type-safe execution
    - Better error handling
    """
    
    def __init__(self, max_parallel_workers: int = 5):
        self.executables: Dict[str, ExecutableConfig] = {}
        self.max_parallel_workers = max_parallel_workers
        self.execution_history: List[ExecutionResult] = []
    
    def register_agent(
        self,
        name: str,
        instance: Any,
        description: str,
        parameters_schema: Dict[str, Any],
        parallel_safe: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register an agent.
        
        Args:
            name: Agent name (will be used as function name by LLM)
            instance: Agent instance (must have .chat() method)
            description: Description for LLM
            parameters_schema: JSON schema for parameters
            parallel_safe: Whether this agent can run in parallel
            metadata: Additional metadata
        """
        config = ExecutableConfig(
            name=name,
            executable_type=ExecutableType.AGENT,
            instance=instance,
            description=description,
            parameters_schema=parameters_schema,
            parallel_safe=parallel_safe,
            metadata=metadata or {}
        )
        
        self.executables[name] = config
        print(f"✅ Registered agent: {name}")
    
    def register_tool(
        self,
        name: str,
        function: Callable,
        description: str,
        parameters_schema: Dict[str, Any],
        parallel_safe: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register a tool (simple function).
        
        Args:
            name: Tool name
            function: Callable function
            description: Description for LLM
            parameters_schema: JSON schema for parameters
            parallel_safe: Whether this tool can run in parallel
            metadata: Additional metadata
        """
        config = ExecutableConfig(
            name=name,
            executable_type=ExecutableType.TOOL,
            instance=function,
            description=description,
            parameters_schema=parameters_schema,
            parallel_safe=parallel_safe,
            metadata=metadata or {}
        )
        
        self.executables[name] = config
        print(f"✅ Registered tool: {name}")
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get OpenAI-compatible tools schema for all executables.
        
        Returns:
            List of tool definitions for LLM
        """
        tools = []
        for name, config in self.executables.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": config.description,
                    "parameters": config.parameters_schema
                }
            })
        return tools
    
    def execute(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute a single agent or tool.
        
        Args:
            name: Name of agent/tool to execute
            arguments: Arguments to pass
            
        Returns:
            ExecutionResult
        """
        import time
        start_time = time.time()
        
        if name not in self.executables:
            return ExecutionResult(
                status="error",
                name=name,
                result=None,
                error=f"'{name}' not found. Available: {list(self.executables.keys())}"
            )
        
        config = self.executables[name]
        
        try:
            # Execute based on type
            if config.executable_type == ExecutableType.AGENT:
                # Agent execution (has .chat() method)
                if hasattr(config.instance, 'chat'):
                    result = config.instance.chat(**arguments)
                else:
                    return ExecutionResult(
                        status="error",
                        name=name,
                        result=None,
                        error=f"Agent '{name}' does not have a chat() method"
                    )
            
            else:  # TOOL
                # Tool execution (is a callable)
                if callable(config.instance):
                    result = config.instance(**arguments)
                else:
                    return ExecutionResult(
                        status="error",
                        name=name,
                        result=None,
                        error=f"Tool '{name}' is not callable"
                    )
            
            execution_time = time.time() - start_time
            
            exec_result = ExecutionResult(
                status="success",
                name=name,
                result=result,
                metadata={"arguments": arguments, "type": config.executable_type.value},
                execution_time=execution_time
            )
            
            self.execution_history.append(exec_result)
            return exec_result
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            exec_result = ExecutionResult(
                status="error",
                name=name,
                result=None,
                error=str(e),
                metadata={"arguments": arguments, "type": config.executable_type.value},
                execution_time=execution_time
            )
            
            self.execution_history.append(exec_result)
            return exec_result
    
    def execute_multiple(
        self,
        calls: List[Dict[str, Any]],
        parallel: bool = False
    ) -> List[ExecutionResult]:
        """
        Execute multiple agents/tools.
        
        Args:
            calls: List of calls, each with 'name' and 'arguments'
            parallel: Whether to execute in parallel
            
        Returns:
            List of ExecutionResults
            
        Example:
            >>> results = handler.execute_multiple([
            ...     {"name": "research_general", "arguments": {"topic": "AI"}},
            ...     {"name": "filesystem_operations", "arguments": {"message": "list files"}}
            ... ], parallel=True)
        """
        if not parallel:
            # Sequential execution
            return [self.execute(call["name"], call["arguments"]) for call in calls]
        
        # Parallel execution
        return self._execute_parallel(calls)
    
    def _execute_parallel(self, calls: List[Dict[str, Any]]) -> List[ExecutionResult]:
        """
        Execute calls in parallel using ThreadPoolExecutor.
        
        Only executes parallel_safe executables in parallel.
        Others are executed sequentially.
        """
        parallel_calls = []
        sequential_calls = []
        
        # Separate parallel-safe from sequential
        for call in calls:
            name = call["name"]
            if name in self.executables and self.executables[name].parallel_safe:
                parallel_calls.append(call)
            else:
                sequential_calls.append(call)
        
        results = []
        
        # Execute parallel-safe calls
        if parallel_calls:
            with ThreadPoolExecutor(max_workers=self.max_parallel_workers) as executor:
                future_to_call = {
                    executor.submit(self.execute, call["name"], call["arguments"]): call
                    for call in parallel_calls
                }
                
                for future in as_completed(future_to_call):
                    results.append(future.result())
        
        # Execute sequential calls
        for call in sequential_calls:
            results.append(self.execute(call["name"], call["arguments"]))
        
        return results
    
    def list_agents(self) -> List[str]:
        """Get list of registered agents."""
        return [
            name for name, config in self.executables.items()
            if config.executable_type == ExecutableType.AGENT
        ]
    
    def list_tools(self) -> List[str]:
        """Get list of registered tools."""
        return [
            name for name, config in self.executables.items()
            if config.executable_type == ExecutableType.TOOL
        ]
    
    def get_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about an agent or tool."""
        if name not in self.executables:
            return None
        
        config = self.executables[name]
        return {
            "name": config.name,
            "type": config.executable_type.value,
            "description": config.description,
            "parameters": config.parameters_schema,
            "parallel_safe": config.parallel_safe,
            "metadata": config.metadata
        }
    
    def unregister(self, name: str) -> bool:
        """Unregister an agent or tool."""
        if name in self.executables:
            del self.executables[name]
            print(f"✅ Unregistered: {name}")
            return True
        return False
    
    def clear_history(self):
        """Clear execution history."""
        self.execution_history = []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total_executions = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.status == "success")
        failed = total_executions - successful
        
        avg_time = (
            sum(r.execution_time for r in self.execution_history if r.execution_time)
            / total_executions
            if total_executions > 0 else 0
        )
        
        return {
            "total_executions": total_executions,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_executions if total_executions > 0 else 0,
            "average_execution_time": avg_time,
            "registered_agents": len(self.list_agents()),
            "registered_tools": len(self.list_tools())
        }