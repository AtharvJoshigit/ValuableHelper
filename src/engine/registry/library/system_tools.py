import subprocess
from typing import Any, List, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool

class RunCommandTool(BaseTool):
    name: str = "run_command"
    description: str = "Execute a shell command on the local system. Returns stdout, stderr, and exit code."
    command: Optional[str] = Field(default=None, description="The shell command to execute.")
    allowed_commands: Optional[List[str]] = Field(
        default=None,
        description="Optional list of whitelisted commands. If not provided, uses default safe commands.",
        # This is the key part for Google's schema
        json_schema_extra={
            "type": "array",
            "items": {"type": "string"},
            "default": ["ls", "pwd", "cat", "echo", "mkdir"]
        }
    )

    
    
    def execute(self, **kwargs) -> Any:
        command = kwargs.get("command", self.command)
        # Validate command against whitelist
        cmd_base = command.split()[0] if command else ""
        if cmd_base not in self.allowed_commands:
            return {"error": f"Command '{cmd_base}' not allowed. Allowed: {self.allowed_commands}"}
        
        try:
            # Use shell=False with list for better security
            result = subprocess.run(
                command.split(),  # Split into list
                shell=False,  # More secure
                capture_output=True,
                text=True,
                timeout=30  # 5 min seems too long, consider 30s
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out"}
        except Exception as e:
            return {"error": str(e)}