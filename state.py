from config import CHARACTER_FILE, CATEGORY_FILE, INACTIVITY_TRACKER_FILE, TRACK_FILE
from utils_helper import load_json, save_json
from datetime import datetime, timezone
import json
from collections import deque
characters_data = load_json(CHARACTER_FILE, {})

# Asegura que los campos existen
characters_data.setdefault("owners", {})
characters_data.setdefault("aliases", {})
characters_data.setdefault("activity", {})
characters_data.setdefault("_meta", {})

if "last_weekly_reset" not in characters_data["_meta"]:
    characters_data["_meta"]["last_weekly_reset"] = datetime.now(timezone.utc).isoformat()
    save_json(CHARACTER_FILE, characters_data)

character_aliases = characters_data["aliases"]
character_owners = characters_data["owners"]
inactivity_tracker = load_json(INACTIVITY_TRACKER_FILE, {})

# List of forum category IDs
category_data = [int(x) for x in load_json(CATEGORY_FILE, [])]
notified_users = load_json(INACTIVITY_TRACKER_FILE, {}).get("notified_users", {})
tracking_data = {}
recent_dms = {}  # Format: {user_id: deque of (message_id, content)}
pause_activity = False


# Global variable to control activity check status
def pause_activity_function():
    """Pause activity checks for everyone."""
    global pause_activity
    pause_activity = True

def resume_activity_function():
    """Resume activity checks."""
    global pause_activity
    pause_activity = False

def load_state():
    """Load the saved state from the JSON file."""
    global pause_activity
    try:
        with open(TRACK_FILE, "r") as f:
            state_data = json.load(f)
            pause_activity = state_data.get("pause_activity", False)
    except FileNotFoundError:
        # If the file doesn't exist, assume the state is not paused
        pause_activity = False

# Ensure the state is loaded when the module is imported
load_state()

def save_state():
    """Save the current state to the JSON file."""
    state_data = {"pause_activity": pause_activity}
    with open(TRACK_FILE, "w") as f:
        json.dump(state_data, f, indent=4)

def pause_activity_function():
    """Pause activity checks for everyone."""
    global pause_activity
    pause_activity = True
    save_state()  # Save the state after pausing

def resume_activity_function():
    """Resume activity checks."""
    global pause_activity
    pause_activity = False
    save_state()  # Save the state after resuming
    update_last_seen_for_all()  # Update last_seen for all characters

def update_last_seen_for_all():
    """Update the last_seen field for all characters to the last_weekly_reset time."""
    last_reset_time = characters_data["_meta"].get("last_weekly_reset", datetime.utcnow().isoformat())
    for character, activity in characters_data["activity"].items():
        activity["last_seen"] = last_reset_time
    save_json(CHARACTER_FILE, characters_data)