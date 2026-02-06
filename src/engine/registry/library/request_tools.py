from datetime import datetime
import json
from typing import Any

from pydantic import Field

from engine.registry.base_tool import BaseTool

class RequestApprovalTool(BaseTool):
    """
    Tool for sub-agent to request user approval before making changes.
    """
    name: str = "request_approval"
    description: str = "Request user permission before executing potentially destructive operations."
    action_type: str = Field(..., description="Type of action: 'file_write', 'file_delete', 'command_exec', 'api_call'")
    action_details: dict = Field(..., description="Details of the proposed action")
    risk_level: str = Field(default="medium", description="Risk level: 'low', 'medium', 'high'")
    
    def execute(self, **kwargs) -> Any:
        action_type = kwargs.get("action_type", self.action_type)
        action_details = kwargs.get("action_details", self.action_details)
        risk_level = kwargs.get("risk_level", self.risk_level)
        
        # Format the approval request
        request_message = self._format_request(action_type, action_details, risk_level)
        
        print("\n" + "="*60)
        print("🤖 SUB-AGENT APPROVAL REQUEST")
        print("="*60)
        print(request_message)
        print("="*60)
        
        # Get user input
        while True:
            response = input("\nApprove this action? (yes/no/details): ").strip().lower()
            
            if response in ['yes', 'y']:
                return {
                    "status": "approved",
                    "message": "User approved the action",
                    "timestamp": str(datetime.now())
                }
            elif response in ['no', 'n']:
                return {
                    "status": "rejected",
                    "message": "User rejected the action",
                    "timestamp": str(datetime.now())
                }
            elif response in ['details', 'd']:
                print("\nDetailed Information:")
                print(json.dumps(action_details, indent=2))
            else:
                print("Please respond with 'yes', 'no', or 'details'")
    
    def _format_request(self, action_type: str, details: dict, risk_level: str) -> str:
        risk_emoji = {"low": "✅", "medium": "⚠️", "high": "🚨"}
        
        message = f"""
Action Type: {action_type.upper()}
Risk Level: {risk_emoji.get(risk_level, '⚠️')} {risk_level.upper()}

Proposed Changes:
"""
        
        if action_type == "file_write":
            message += f"  • Create/Modify: {details.get('file_path', 'N/A')}\n"
            message += f"  • Size: {details.get('size', 'N/A')} bytes\n"
            if details.get('overwrite'):
                message += f"  • ⚠️ Will OVERWRITE existing file\n"
                
        elif action_type == "file_delete":
            message += f"  • Delete: {details.get('file_path', 'N/A')}\n"
            message += f"  • ⚠️ This action is IRREVERSIBLE\n"
            
        elif action_type == "command_exec":
            message += f"  • Command: {details.get('command', 'N/A')}\n"
            message += f"  • Working Dir: {details.get('cwd', 'N/A')}\n"
            
        elif action_type == "api_call":
            message += f"  • Endpoint: {details.get('endpoint', 'N/A')}\n"
            message += f"  • Method: {details.get('method', 'N/A')}\n"
        
        if details.get('reason'):
            message += f"\nReason: {details['reason']}\n"
            
        return message