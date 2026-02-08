from typing import Any, Optional, List
from pydantic import Field
from engine.registry.base_tool import BaseTool
from services.gmail.service import get_gmail_service, search_emails, get_email_details, send_email

class GmailSearchTool(BaseTool):
    """
    Search for emails in Gmail. Returns a list of message summaries.
    """
    name: str = "gmail_search"
    description: str = "Search for emails using a query string (e.g., 'is:unread', 'from:boss@example.com'). Returns a list of message snippets."
    query: Optional[str] = Field(default=None, description="The search query.")
    limit: int = Field(default=5, description="Maximum number of results to return.")

    def execute(self, **kwargs) -> Any:
        query = kwargs.get("query")
        limit = kwargs.get("limit", 5)
        
        service = get_gmail_service()
        if not service:
            return {"status": "error", "error": "Could not initialize Gmail service. Check authentication."}
            
        results = search_emails(service, query, limit)
        return {"status": "success", "results": results}

class GmailReadTool(BaseTool):
    """
    Read the full content of a specific email.
    """
    name: str = "gmail_read"
    description: str = "Read the full content (headers and body) of an email using its ID."
    message_id: Optional[str] = Field(default=None, description="The unique ID of the message to read.")

    def execute(self, **kwargs) -> Any:
        message_id = kwargs.get("message_id")
        
        service = get_gmail_service()
        if not service:
            return {"status": "error", "error": "Could not initialize Gmail service."}
            
        details = get_email_details(service, message_id)
        if details:
            return {"status": "success", "email": details}
        else:
            return {"status": "error", "error": "Email not found or could not be read."}

class GmailSendTool(BaseTool):
    """
    Send an email via Gmail.
    """
    name: str = "gmail_send"
    description: str = "Send an email to a recipient."
    to: Optional[str] = Field(default=None, description="Recipient email address.")
    subject: Optional[str] = Field(default=None, description="Email subject.")
    body: Optional[str] = Field(default=None, description="Email body content.")

    def execute(self, **kwargs) -> Any:
        to = kwargs.get("to")
        subject = kwargs.get("subject")
        body = kwargs.get("body")
        
        service = get_gmail_service()
        if not service:
            return {"status": "error", "error": "Could not initialize Gmail service."}
            
        result = send_email(service, to, subject, body)
        if result:
            return {"status": "success", "message_id": result.get("id")}
        else:
            return {"status": "error", "error": "Failed to send email."}
