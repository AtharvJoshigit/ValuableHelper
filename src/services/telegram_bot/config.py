import os
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========== TELEGRAM BOT CONFIGURATION ==========

# 1. Load Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

def _parse_int_list(env_var_name: str) -> List[int]:
    """Parses a comma-separated string of integers from an environment variable."""
    raw_str = os.getenv(env_var_name, "")
    if not raw_str:
        return []
    
    valid_ids = []
    for item in raw_str.split(","):
        cleaned = item.strip()
        if cleaned.isdigit():
            valid_ids.append(int(cleaned))
        else:
            print(f"Warning: Skipped non-numeric value '{cleaned}' in {env_var_name}")
    return valid_ids

# 2. Load Authorized Users (Whitelist)
AUTHORIZED_USERS: List[int] = _parse_int_list("AUTHORIZED_USERS")

# 3. Define Admin Users
# Tries to load specific admins, otherwise defaults to the first authorized user.
ADMIN_USER_IDS: List[int] = _parse_int_list("ADMIN_USER_IDS")

# Fallback: If no admins defined, the first authorized user becomes admin
if not ADMIN_USER_IDS and AUTHORIZED_USERS:
    ADMIN_USER_IDS = [AUTHORIZED_USERS[0]]

# Validation Warning
if not TELEGRAM_BOT_TOKEN:
    print("CRITICAL WARNING: TELEGRAM_BOT_TOKEN is missing from environment variables.")
if not AUTHORIZED_USERS:
    print("WARNING: AUTHORIZED_USERS is empty. Bot will be inaccessible until users are added.")