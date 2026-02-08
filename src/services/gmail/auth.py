# src/services/gmail/auth.py

import os
from pathlib import Path
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# SCOPES define the level of access you are requesting from the user's account.
# For this project, we only need to read emails.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]

# Load environment variables from .env file
load_dotenv()

# Define the paths for credentials and token files.
SECRETS_DIR = Path(os.getenv("GMAIL_SECRETS_DIR", "config/secrets"))
SECRETS_DIR.mkdir(exist_ok=True)  # Ensure the directory exists

CREDENTIALS_PATH = SECRETS_DIR / "credentials.json"
TOKEN_PATH = SECRETS_DIR / "token.json"


def get_gmail_credentials():
    """
    Authenticates the user with the Gmail API using OAuth 2.0.
    """
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                # If refresh fails, we'll fall through to re-authentication
                print(f"Failed to refresh token: {e}. Re-authenticating...")
                creds = None  # Force re-authentication

        if not creds:  # This block runs if creds are None or after a failed refresh
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"'{CREDENTIALS_PATH.name}' not found in the project root directory: {PROJECT_ROOT}. "
                    "Please follow the instructions in the docstring to obtain and "
                    "place this file."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            # port=0 makes it find a free port automatically
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
            print(f"Credentials saved to {TOKEN_PATH}")

    return creds


if __name__ == "__main__":
    # This allows running the script directly to test and perform the initial auth.
    print("--- Gmail Authentication Helper ---")
    print("This script will guide you through the Google authentication process.")
    try:
        credentials = get_gmail_credentials()
        if credentials:
            print("\nAuthentication successful!")
            print(f"Token file is valid and stored at: {TOKEN_PATH}")
        else:
            print("\nAuthentication failed.")
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
    except Exception as e:
        # Catch other potential errors during the flow (e.g., network issues)
        print(f"\nAn unexpected error occurred during authentication: {e}")