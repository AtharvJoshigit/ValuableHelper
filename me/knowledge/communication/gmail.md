# Gmail Integration Guide

## 1. Setup & Authentication

Before you can use the Gmail tools, you must configure your Google Cloud project.

### Step 1: Google Cloud Console
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., "My Assistant").
3. Search for **"Gmail API"** and enable it.

### Step 2: OAuth Consent Screen
1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** (unless you have a Google Workspace organization).
3. Fill in the required fields (App name, support email).
4. Add your email address to the **Test Users** list. This is crucial for "External" apps to work without verification.

### Step 3: Credentials
1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Application type: **Desktop app**.
4. Download the JSON file.
5. **Rename** it to `credentials.json`.
6. **Move** it to the root directory of this project (`ValuableHelper/credentials.json`).

### Step 4: First Run
1. When you first use a Gmail tool, the system will look for `credentials.json`.
2. It will open a browser window (or give you a link) to log in.
3. Grant permissions.
4. A `token.json` file will be created automatically. Future runs will use this token.

## 2. Tools & Usage

### GmailSearchTool
**Description:** Search for emails in your inbox.
**Usage:**
```python
# Search for unread emails
tool.execute(query="is:unread", limit=5)
```

### GmailReadTool
**Description:** Read the full content of an email.
**Usage:**
```python
# Read a specific email
tool.execute(message_id="12345abcde")
```

### GmailSendTool
**Description:** Send an email.
**Usage:**
```python
# Send an email
tool.execute(to="friend@example.com", subject="Hi", body="How are you?")
```