# src/services/gmail/service.py

import base64
import os
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.services.gmail.auth import get_gmail_credentials


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
        return service
    except Exception as e:
        print(f"Error building Gmail service: {e}")
        return None


def search_emails(service, query: str, limit: int = 5):
    """
    Searches for emails based on a query and returns a list of simplified objects.
    """
    try:
        response = service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
        messages = response.get('messages', [])
        
        results = []
        if not messages:
            return []

        for msg in messages:
            try:
                msg_detail = service.users().messages().get(
                    userId='me', 
                    id=msg['id'], 
                    format='metadata', 
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()
                
                headers = msg_detail.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '(Unknown Sender)')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                snippet = msg_detail.get('snippet', '')

                results.append({
                    'id': msg.get('id'),
                    'threadId': msg.get('threadId'),
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': snippet
                })
            except Exception as e:
                print(f"Error fetching detail for message {msg['id']}: {e}")
                continue
            
        return results
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def get_email_details(service, msg_id: str):
    """
    Retrieves details for a specific email by ID, including attachment metadata.
    """
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])

        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')

        body_text = ""
        body_html = ""
        attachments = []

        def parse_parts(parts):
            nonlocal body_text, body_html
            for part in parts:
                mimeType = part.get('mimeType')
                filename = part.get('filename')
                
                # Check for attachment
                if filename:
                    attachment_id = part.get('body', {}).get('attachmentId')
                    if attachment_id:
                        attachments.append({
                            'filename': filename,
                            'mimeType': mimeType,
                            'attachmentId': attachment_id,
                            'size': part.get('body', {}).get('size')
                        })
                
                # Check for nested parts
                if part.get('parts'):
                    parse_parts(part.get('parts'))
                
                # Extract Text Bodies (only if not an attachment, though sometimes they overlap)
                if mimeType == 'text/plain' and not filename:
                    data = part.get('body', {}).get('data')
                    if data:
                        body_text += base64.urlsafe_b64decode(data).decode('utf-8')
                elif mimeType == 'text/html' and not filename:
                    data = part.get('body', {}).get('data')
                    if data:
                        body_html += base64.urlsafe_b64decode(data).decode('utf-8')

        if 'parts' in payload:
            parse_parts(payload['parts'])
        else:
            # Single part message
            data = payload.get('body', {}).get('data')
            if data:
                text = base64.urlsafe_b64decode(data).decode('utf-8')
                if payload.get('mimeType') == 'text/html':
                    body_html = text
                else:
                    body_text = text

        return {
            'id': msg_id,
            'from': sender,
            'date': date,
            'subject': subject,
            'body': body_text if body_text else body_html, 
            'body_html': body_html,
            'attachments': attachments
        }

    except Exception as e:
        print(f"Error parsing email details for {msg_id}: {e}")
        return None

def download_attachment(service, message_id, attachment_id):
    """
    Downloads an attachment by ID and returns the raw bytes.
    """
    try:
        attachment = service.users().messages().attachments().get(
            userId='me', messageId=message_id, id=attachment_id
        ).execute()
        
        file_data = base64.urlsafe_b64decode(attachment['data'])
        return file_data
    except Exception as e:
        print(f"Error downloading attachment: {e}")
        return None

def send_email(service, to: str, subject: str, message_text: str, attachments: list = None):
    """
    Sends an email, optionally with attachments.
    """
    try:
        message = MIMEMultipart()
        message['to'] = to
        message['from'] = 'me'
        message['subject'] = subject

        msg = MIMEText(message_text)
        message.attach(msg)

        if attachments:
            for filename in attachments:
                if not os.path.exists(filename):
                    print(f"Warning: Attachment file not found: {filename}")
                    continue
                
                content_type, encoding = mimetypes.guess_type(filename)
                if content_type is None or encoding is not None:
                    content_type = 'application/octet-stream'
                
                main_type, sub_type = content_type.split('/', 1)

                try:
                    with open(filename, 'rb') as f:
                        file_data = f.read()
                    
                    if main_type == 'text':
                        msg = MIMEBase(main_type, sub_type)
                        msg.set_payload(file_data)
                    else:
                        msg = MIMEBase(main_type, sub_type)
                        msg.set_payload(file_data)
                    
                    encoders.encode_base64(msg)
                    
                    filename_base = os.path.basename(filename)
                    msg.add_header('Content-Disposition', 'attachment', filename=filename_base)
                    message.attach(msg)
                except Exception as e:
                    print(f"Error attaching file {filename}: {e}")

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw_message}
        
        sent_message = service.users().messages().send(userId="me", body=body).execute()
        return sent_message
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None
