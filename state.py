from config import CHARACTER_FILE, CATEGORY_FILE, INACTIVITY_TRACKER_FILE, TRACK_FILE
from utils_helper import load_json, save_json
from datetime import datetime
import json
from collections import deque
characters_data = load_json(CHARACTER_FILE, {})

# Asegura que los campos existen
characters_data.setdefault("owners", {})
characters_data.setdefault("aliases", {})
characters_data.setdefault("activity", {})
characters_data.setdefault("_meta", {})

if "last_weekly_reset" not in characters_data["_meta"]:
    characters_data["_meta"]["last_weekly_reset"] = datetime.utcnow().isoformat()
    save_json(CHARACTER_FILE, characters_data)

character_aliases = characters_data["aliases"]
character_owners = characters_data["owners"]
inactivity_tracker = load_json(INACTIVITY_TRACKER_FILE, {})

# List of forum category IDs
category_data = [int(x) for x in load_json(CATEGORY_FILE, [])]
notified_users = load_json(INACTIVITY_TRACKER_FILE, {}).get("notified_users", {})
tracking_data = {}
recent_dms = {}  # Format: {user_id: deque of (message_id, content)}
# Tracking data
try:
    with open(TRACK_FILE, "r") as f:
        tracking_data = json.load(f)
except FileNotFoundError:
    tracking_data = {}
