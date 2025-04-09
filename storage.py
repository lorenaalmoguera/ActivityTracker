import json
from discord_client import client
import os
from utils_helper import load_json, save_json
from state import characters_data
from config import (
    INACTIVITY_TRACKER_FILE,
    TRACK_FILE,
    CATEGORY_FILE,
    CHARACTER_FILE,
    USERS_FILE
)

# Define global variables and function placeholders
tracking_data = {}


# Load functions for various files
def load_inactivity_tracker():
    print(f"Debugging: Loading inactivity tracker data from {INACTIVITY_TRACKER_FILE}...")
    return load_json(INACTIVITY_TRACKER_FILE, {})

def load_users():
    return load_json(USERS_FILE, {})

# Add get_json function if missing
def get_json(path, default):
    """Get JSON data from a file or return default if file doesn't exist or is invalid."""
    return load_json(path, default)

# Define your load/save functions for other data
def load_data():
    print(f"Debugging: Loading tracking data from {TRACK_FILE}...")
    try:
        with open(TRACK_FILE, "r") as f:
            data = json.load(f)
            print(f"Debugging: Data loaded: {data}")  # Debug print
            return data
    except FileNotFoundError:
        print("Debugging: File not found, returning empty data.")
        return {}
    
def save_data(data=None):
    from state import tracking_data
    if data is None:
        data = tracking_data
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        print("🧠 Saving tracking_data:", json.dumps(tracking_data, indent=2))

    print("✅ tracking_data saved.")

def save_inactivity_tracker():
    # 💡 Force access to the global inactivity_tracker from state
    import state
    print("🔁 Grabbing global inactivity_tracker from state...")
    print(json.dumps(state.inactivity_tracker, indent=2, ensure_ascii=False))

    save_json(INACTIVITY_TRACKER_FILE, state.inactivity_tracker)
    print("✅ Inactivity tracker saved.")
def save_users():
    print(f"Debugging: Saving users data to {USERS_FILE}...")
    save_json(USERS_FILE, users_data)
    print("Debugging: Users data saved.")


def save_user_last_active(character_name, forum_name, timestamp):
    if character_name not in characters_data:
        characters_data[character_name] = {}

    if "activity" not in characters_data[character_name]:
        characters_data[character_name]["activity"] = {}

    characters_data[character_name]["activity"][forum_name] = timestamp
    save_json(CHARACTER_FILE, characters_data)


def get_thread_info(thread_id):
    # Example logic to fetch thread info based on a thread ID.
    if thread_id in tracking_data:
        return tracking_data[thread_id]
    return None

def get_user_last_active(user_id):
    # This is just an example. Modify it to fit your data structure.
    if user_id in tracking_data:
        return tracking_data[user_id].get("last_active_time", None)
    return None

def save_thread_info(thread_id, thread_info):
    # Example logic to save thread information
    tracking_data[thread_id] = thread_info
    save_data(tracking_data)  # Make sure to save it back to the file


def save_tracking():
    from state import tracking_data
    with open(TRACK_FILE, "w") as f:
        json.dump(tracking_data, f, indent=2)


# --------------------------------------------------
# Obtener el owner de un personaje por su nombre
# --------------------------------------------------
def get_character_owner(character_name):
    for user_id, user_data in users_data.items():
        if "characters" in user_data:
            for character in user_data["characters"]:
                if character["name"].lower() == character_name.lower():
                    return user_id
    return None


# --------------------------------------------------
# Eliminar un personaje por nombre para un usuario
# --------------------------------------------------
async def remove_character(ctx, character_name):
    user_id = str(ctx.author.id)
    if user_id in users_data:
        user_data = users_data[user_id]
        if "characters" in user_data:
            original_count = len(user_data["characters"])
            user_data["characters"] = [
                char for char in user_data["characters"]
                if char["name"].lower() != character_name.lower()
            ]
            if len(user_data["characters"]) < original_count:
                save_users()
                await ctx.send(f"Character '{character_name}' removed.")
            else:
                await ctx.send(f"Character '{character_name}' not found.")
    else:
        await ctx.send("You have no characters registered.")


# ----------------------------------------
# Verifica si un usuario aún tiene personajes
# ----------------------------------------
def still_has_characters(users_data, user_id):
    user_id_str = str(user_id)
    return (
        user_id_str in users_data and
        "characters" in users_data[user_id_str] and
        len(users_data[user_id_str]["characters"]) > 0
    )


def load_characters():
    return load_json(CHARACTER_FILE, {"owners": {}, "aliases": {}, "activity": {}})

def save_characters():
    from state import characters_data
    with open(CHARACTER_FILE, "w", encoding="utf-8") as f:
        json.dump(characters_data, f, indent=2, ensure_ascii=False)
        print("🧠 Saving characters_data:", json.dumps(characters_data, indent=2, ensure_ascii=False))
    print("✅ character_data saved.")



def load_categories():
    return load_json(CATEGORY_FILE, [])

def save_categories():
    save_json(CATEGORY_FILE, admin_tracked_categories)

# Load once at startup (move this after the functions)
character_owners = characters_data.get("owners", {})
character_aliases = characters_data.get("aliases", {})
admin_tracked_categories = load_categories()

# This should happen after functions are defined.
inactivity_tracker = load_inactivity_tracker()
users_data = load_users()

if isinstance(admin_tracked_categories, dict):
    admin_tracked_categories = list(admin_tracked_categories.values())

# Character tracking
registered_characters = set(character_owners.keys())

def extract_thread_id(link):
    try:
        parts = link.strip().split("/")
        return parts[-1] if parts else None
    except:
        return None

async def delete_character_by_name(base_name: str):
    from storage import characters_data, character_aliases, character_owners, tracking_data
    from storage import save_characters, save_data

    names_to_remove = {base_name}
    for alias, target in character_aliases.items():
        if target == base_name:
            names_to_remove.add(alias)

    for name in list(characters_data.get("activity", {}).keys()):
        if character_aliases.get(name, name) == base_name:
            names_to_remove.add(name)

    for alias in list(character_aliases.keys()):
        if alias in names_to_remove or character_aliases[alias] == base_name:
            del character_aliases[alias]

    for name in list(characters_data.get("activity", {}).keys()):
        if name in names_to_remove:
            del characters_data["activity"][name]

    for user_data in tracking_data.values():
        for thread_info in user_data.get("tracked_threads", {}).values():
            for char in list(thread_info.get("activity_log", {}).keys()):
                if char in names_to_remove:
                    del thread_info["activity_log"][char]
            if thread_info.get("last_active_tupper") in names_to_remove:
                thread_info["last_active_tupper"] = None

    for name in list(character_owners.keys()):
        if name in names_to_remove:
            del character_owners[name]

    save_characters()
    save_data(tracking_data)

    return bool(names_to_remove)

