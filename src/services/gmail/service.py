# src/services/gmail/service.py

import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services.gmail.auth import get_gmail_credentials


def get_gmail_service():
    """
    Returns an authenticated Gmail API service object.
    """
    creds = get_gmail_credentials()
    if not creds:
        print("Error: Could not obtain Gmail credentials.")
        return None
    try:
        service = build('gmail', 'v1', credentials=creds)
        print("Gmail service initialized successfully.")
        return service
    except Exception as e:
        print(f"Error building Gmail service: {e}")
        return None


def search_emails(service, query: str, limit: int = 5):
    """
    Searches for emails based on a query and returns a list of simplified objects.
    """
    try:
        # Call the Gmail API to fetch messages
        response = service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
        messages = response.get('messages', [])
        
        results = []
        for msg in messages:
            # Get metadata (headers and snippet) for the message
            # format='metadata' with metadataHeaders filters payload to just what we need
            msg_detail = service.users().messages().get(
                userId='me', 
                id=msg['id'], 
                format='metadata', 
                metadataHeaders=['Subject', 'From']
            ).execute()
            
            headers = msg_detail.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '(Unknown Sender)')
            snippet = msg_detail.get('snippet', '')

            results.append({
                'id': msg.get('id'),
                'threadId': msg.get('threadId'),
                'subject': subject,
                'from': sender,
                'snippet': snippet
            })
            
        return results
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def get_email_details(service, msg_id: str):
    """
    Retrieves details for a specific email by ID.
    """
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # Extract headers
        headers = msg['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
        
        # Extract body (handling multipart messages)
        body = ""
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                    # You might want to parse HTML or convert to plain text here
                    # For simplicity, we'll just decode it. Be aware it will contain HTML tags.
                    body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        elif 'data' in msg['payload']['body']:
            body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')

        return {
            'id': msg_id,
            'from': sender,
            'date': date,
            'subject': subject,
            'body': body.strip()
        }
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None
    except Exception as e:
        print(f"Error parsing email details for {msg_id}: {e}")
        return None

def send_email(service, to: str, subject: str, message_text: str):
    """
    Sends an email.
    """
    try:
        message = MIMEText(message_text)
        message['to'] = to
        message['from'] = 'me'
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw_message}
        
        sent_message = service.users().messages().send(userId="me", body=body).execute()
        print(f"Message Id: {sent_message.get('id')}")
        return sent_message
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None
