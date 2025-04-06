# config.py
import os
from dotenv import load_dotenv
from discord_client import client
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


INACTIVITY_TRACKER_FILE = os.path.join(BASE_DIR, "data", "inactivity_dm_tracker.json")
TRACK_FILE = os.path.join(BASE_DIR, "data", "tracking_data.json")
CHARACTER_FILE = os.path.join(BASE_DIR, "data", "character_data.json")
CATEGORY_FILE = os.path.join(BASE_DIR, "data", "category_data.json")
USERS_FILE = os.path.join(BASE_DIR, "data", "users.json")

# other env-based values
GUILD_ID = int(os.getenv("GUILD_ID"))
ADMIN_ALERT_CHANNEL_ID = int(os.getenv("ADMIN_ALERT_CHANNEL_ID"))
MUN_ROLE_ID = int(os.getenv("MUN_ROLE_ID"))
MODERATOR_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
ARCHIVE_CATEGORY_ID = int(os.getenv("ARCHIVE_CATEGORY_ID"))

print(f"Tracking file path: {TRACK_FILE}")
print(f"Users file path: {USERS_FILE}")
print(f"Categories file path: {CATEGORY_FILE}")
print(f"Characters file path: {CHARACTER_FILE}")           
print(f"Inactivity tracker file path: {INACTIVITY_TRACKER_FILE}")
print(f"Admin alert channel ID: {ADMIN_ALERT_CHANNEL_ID}")
print(f"Mun role ID: {MUN_ROLE_ID}")
print(f"Archive category ID: {ARCHIVE_CATEGORY_ID}")