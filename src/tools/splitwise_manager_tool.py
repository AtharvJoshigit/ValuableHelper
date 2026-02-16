import os
import requests
from typing import Optional, Dict, List, Any

class SplitwiseManager:
    """
    A tool to interact with the Splitwise API for managing expenses and balances.
    It uses the SPLITWISE_API_KEY from the environment.
    """
    
    BASE_URL = "https://secure.splitwise.com/api/v3.0"
    
    def __init__(self):
        self.name = "splitwise_manager"
        self.api_key = os.getenv("SPLITWISE_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        if not self.api_key:
            return {"error": "SPLITWISE_API_KEY not found in environment."}
        try:
            response = requests.get(f"{self.BASE_URL}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, endpoint: str, data: Dict) -> Dict:
        if not self.api_key:
            return {"error": "SPLITWISE_API_KEY not found in environment."}
        try:
            response = requests.post(f"{self.BASE_URL}/{endpoint}", headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_balances(self) -> str:
        """Retrieves a summary of who owes you money or who you owe."""
        data = self._get("get_friends")
        friends = data.get("friends", [])
        if not friends:
            return f"No friends found or error: {data.get('error', 'Unknown error')}"
        
        summary = []
        for friend in friends:
            balances = friend.get("balance", [])
            for bal in balances:
                amount = float(bal.get("amount", 0))
                currency = bal.get("currency_code", "???")
                if amount > 0:
                    summary.append(f"💰 {friend.get('first_name')} owes you {amount} {currency}")
                elif amount < 0:
                    summary.append(f"💸 You owe {friend.get('first_name')} {abs(amount)} {currency}")
        
        return "\n".join(summary) if summary else "All settled up! No outstanding balances."

    def list_groups(self) -> str:
        """Lists all Splitwise groups you are part of."""
        data = self._get("get_groups")
        groups = data.get("groups", [])
        if not groups:
            return f"No groups found or error: {data.get('error', 'Unknown error')}"
        
        result = ["**Your Splitwise Groups:**"]
        for g in groups:
            result.append(f"- {g.get('name')} (ID: {g.get('id')})")
        return "\n".join(result)

    def add_expense(self, cost: str, description: str, group_id: int) -> str:
        """
        Adds a simple expense to a group, split equally among all members.
        :param cost: The total cost (e.g., '50.00')
        :param description: Description of the expense.
        :param group_id: The ID of the group.
        """
        data = {
            "cost": cost,
            "description": description,
            "group_id": group_id,
            "split_equally": True
        }
        res = self._post("create_expense", data)
        if "errors" in res:
            return f"❌ Failed to add expense: {res['errors']}"
        return f"✅ Expense '{description}' of {cost} added to group!"

    def run(self, action: str, cost: str = None, description: str = None, group_id: int = None) -> Any:
        """Entry point for the tool."""
        if action == "get_balances":
            return self.get_balances()
        elif action == "list_groups":
            return self.list_groups()
        elif action == "add_expense":
            return self.add_expense(cost, description, group_id)
        else:
            return "Invalid action. Choose 'get_balances', 'list_groups', or 'add_expense'."
