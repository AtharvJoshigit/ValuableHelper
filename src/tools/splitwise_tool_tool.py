import os
import requests
from typing import Any, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool

class SplitwiseTool(BaseTool):
    """
    Interface for interacting with the Splitwise API to manage groups and expenses.
    """
    name: str = "splitwise_tool"
    description: str = "List groups, get balances, or add expenses to Splitwise."
    
    # Provide default for fields so instantiation doesn't fail if they aren't in kwargs immediately
    action: str = Field(default="list_groups", description="Action to perform: 'list_groups', 'get_group_details', or 'add_expense'")
    group_id: Optional[int] = Field(None, description="The Splitwise Group ID.")
    description_text: Optional[str] = Field(None, description="Description for the expense.")
    amount: Optional[float] = Field(None, description="Amount for the expense.")

    def execute(self, **kwargs: Any) -> Any:
        api_key = os.getenv('SPLITWISE_API_KEY')
        if not api_key:
            return {"status": "error", "message": "SPLITWISE_API_KEY not found in environment."}
            
        headers = {"Authorization": f"Bearer {api_key}"}
        action = kwargs.get("action", self.action)
        
        if action == "list_groups":
            url = "https://secure.splitwise.com/api/v3.0/get_groups"
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                groups = [{"id": g["id"], "name": g["name"]} for g in res.json().get("groups", [])]
                return {"status": "success", "groups": groups}
            return {"status": "error", "message": res.text}
            
        elif action == "get_group_details":
            group_id = kwargs.get("group_id", self.group_id)
            if not group_id: return {"status": "error", "message": "group_id required"}
            url = f"https://secure.splitwise.com/api/v3.0/get_group/{group_id}"
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                group = res.json().get("group", {})
                balances = []
                for member in group.get("members", []):
                    bal = member.get("balance", [])
                    if bal:
                        amount = ", ".join([f"{b['amount']} {b['currency_code']}" for b in bal])
                    else:
                        amount = "0.00"
                    first = member.get('first_name') or ''
                    last = member.get('last_name') or ''
                    name = f"{first} {last}".strip()
                    balances.append({"name": name, "balance": amount})
                return {"status": "success", "group_name": group.get("name"), "balances": balances}
            return {"status": "error", "message": res.text}

        elif action == "add_expense":
            url = "https://secure.splitwise.com/api/v3.0/create_expense"
            payload = {
                "group_id": kwargs.get("group_id"),
                "description": kwargs.get("description_text"),
                "cost": str(kwargs.get("amount")),
                "currency_code": "INR",
                "split_equally": True
            }
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return {"status": "success", "expense": res.json()}
            return {"status": "error", "message": res.text}
            
        return {"status": "error", "message": f"Unknown action: {action}"}
