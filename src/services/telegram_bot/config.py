# tele_bot/config.py
import os

# ========== PRIVACY SETTINGS ==========
# Method 1: Whitelist specific user IDs (MOST SECURE)
# To get your user ID, message @userinfobot on Telegram

AUTHORIZED_USERS = [
    785564995,  # Replace with actual user IDs
]
ADMIN_USER_ID = 785564995 # The user ID of the main administrator. This user has elevated permissions.

# Method 2: Whitelist usernames (less secure - usernames can change)
AUTHORIZED_USERNAMES = [
    # "your_username",  # Replace with your Telegram username (without @)
    # "friend_username",  # Add more if needed
]

# Method 3: Use a secret password for initial access
# It is highly recommended to set this via an environment variable for security.
# Example: SECRET_PASSWORD = os.getenv("BOT_SECRET_PASSWORD", "a_default_fallback_password")
SECRET_PASSWORD = os.getenv("BOT_SECRET_PASSWORD", "MySecretPass123")
authenticated_users = set()  # Will store user IDs after they authenticate

# Choose your privacy mode:
# "USER_ID"  - Only specific user IDs (most secure, defined in AUTHORIZED_USERS)
# "USERNAME" - Only specific usernames (less secure, defined in AUTHORIZED_USERNAMES)
# "PASSWORD" - Anyone with the correct password can access (password set in SECRET_PASSWORD)
# "HYBRID"   - Requires both a whitelisted User ID and the correct password (extra security)
PRIVACY_MODE = "USER_ID" # Set your desired privacy mode here
