import subprocess
from typing import Any, List, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool

# Define constant for defaults
DEFAULT_SAFE_COMMANDS = ["ls", "pwd", "cat", "echo", "mkdir", "python", "pip", "mv", "cp", "touch", "grep", "find", "head", "tail", "sh", "git", "rm", "uv"]

class RunCommandTool(BaseTool):
    name: str = "run_command"
    description: str = "Execute a shell command on the local system. Returns stdout, stderr, and exit code."
    command: Optional[str] = Field(default=None, description="The shell command to execute.")
    allowed_commands: Optional[List[str]] = Field(
        default=None,
        description="Optional list of whitelisted commands. If not provided, uses default safe commands."
        # This is the key part for Google's schema
        # json_schema_extra={
        #     "type": "array",
        #     "items": {"type": "string"},
        #     "default": DEFAULT_SAFE_COMMANDS
        # }
    )

    def execute(self, **kwargs) -> Any:
        command = kwargs.get("command", self.command)
        
        # 1. Check kwargs for override
        # 2. Check self.allowed_commands (instance config)
        # 3. Fallback to global defaults
        runtime_allowed = kwargs.get("allowed_commands")
        if runtime_allowed is not None:
            allowed = runtime_allowed
        elif self.allowed_commands is not None:
            allowed = self.allowed_commands
        else:
            allowed = DEFAULT_SAFE_COMMANDS
        
        # Ensure command is not None or empty
        if not command:
            return {"error": "No command provided."}

        # Validate command against whitelist
        cmd_parts = command.split()
        if not cmd_parts:
             return {"error": "Empty command provided."}

        cmd_base = cmd_parts[0]
        
        if cmd_base not in allowed:
            return {"error": f"Command '{cmd_base}' not allowed. Allowed: {allowed}"}
        
        try:
            # Use shell=False with list for better security
            result = subprocess.run(
                cmd_parts,  # Split into list
                shell=False,  # More secure
                capture_output=True,
                text=True,
                timeout=30
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