# ========== PRIVACY SETTINGS ==========
# Method 1: Whitelist specific user IDs (MOST SECURE)
# To get your user ID, message @userinfobot on Telegram

AUTHORIZED_USERS = [
    785564995,  
]

# Method 2: Whitelist usernames (less secure - usernames can change)
AUTHORIZED_USERNAMES = [
    "your_username",  # Replace with your Telegram username (without @)
    # "friend_username",  # Add more if needed
]

# Method 3: Use a secret password for initial access
SECRET_PASSWORD = "MySecretPass123"  # Change this to your secret password
authenticated_users = set()  # Will store user IDs after they authenticate

# Choose your privacy mode:
# "USER_ID" - Only specific user IDs (most secure)
# "USERNAME" - Only specific usernames
# "PASSWORD" - Anyone with the password can access
# "HYBRID" - User ID + Password (extra security)
PRIVACY_MODE = "USER_ID"

