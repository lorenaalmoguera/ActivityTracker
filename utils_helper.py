import json
import os
import discord
from datetime import datetime
from discord.ui import View, Button


# -----------------------------------
# Funciones JSON (carga / guardado)
# -----------------------------------
def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return default if default is not None else {}

def save_json(path, data):
    print(f"💾 Writing to {path}...")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ Done writing.")



# -------------------------------------------------------
# Verifica si el setup de un usuario ha caducado
# -------------------------------------------------------
async def check_user_setup_timers(user_data, timer_threshold=48):
    current_time = datetime.utcnow()
    expired_users = []

    for user_id, data in user_data.items():
        setup_time = data.get('setup_time')
        if setup_time:
            try:
                setup_time = datetime.fromisoformat(setup_time)
                time_diff = (current_time - setup_time).total_seconds()
                if time_diff > timer_threshold * 3600:
                    expired_users.append(user_id)
            except ValueError:
                continue
    return expired_users




# -------------------------------------------------------
# Obtener canal de foro a partir del link guardado
# -------------------------------------------------------
async def get_forum_channel_from_link(user_id, forum_key, guild, users_data):
    forum_data = users_data.get(str(user_id), {}).get(forum_key, {})
    forum_link = forum_data.get("link", "")
    
    if forum_link.startswith("<#") and forum_link.endswith(">"):
        forum_channel_id = int(forum_link.strip("<#>"))
    else:
        forum_channel_id = int(forum_link.split("/")[-1])

    forum_channel = await guild.fetch_channel(forum_channel_id)
    return forum_channel


# -------------------------------------------------------
# Da el rol MUN a un usuario
# -------------------------------------------------------
async def give_mun_role(member):
    from config import MUN_ROLE_ID
    role = discord.utils.get(member.guild.roles, id=MUN_ROLE_ID)
    if role and role not in member.roles:
        await member.add_roles(role, reason="Given MUN role")


# -------------------------------------------------------
# Devuelve el nombre de usuario
# -------------------------------------------------------
def resolve_user_display_name(guild, user_id):
    member = guild.get_member(user_id)
    return member.display_name if member else str(user_id)


import unicodedata
import re

def normalize_alias(text):
    """
    Normalize unicode text to remove stylized fonts, accents, symbols, etc.
    Converts to plain lowercase ASCII.
    """
    # Convert full-width and stylized characters to standard
    text = unicodedata.normalize('NFKD', text)
    
    # Remove diacritics (accents)
    text = ''.join(c for c in text if not unicodedata.combining(c))

    # Remove emojis and symbols
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'[\u2600-\u26FF\u2700-\u27BF]+', '', text)  # Remove misc symbols
    text = re.sub(r'[^\x00-\x7F]', '', text)  # Keep only ASCII

    # Remove extra spaces and convert to lowercase
    return text.lower().strip()


from storage import load_users
from storage import users_data
def save_users_warnings(data=None):
    from config import USERS_FILE  # or hardcode "users.json" if preferred
    if data is None:
        data = users_data
    save_json(USERS_FILE, data)


async def reset_warnings_for_user(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    users = load_users()

    user_id_str = str(user.id)
    if user_id_str not in users:
        await interaction.response.send_message(f"⚠️ User {user.mention} is not found in the system.", ephemeral=True)
        return

    users[user_id_str]["warnings"] = 0
    save_users_warnings(users)

    await interaction.response.send_message(f"✅ {user.mention}'s warnings have been reset to 0.", ephemeral=True)


# Command to reset warnings for all users

async def reset_warnings_for_all(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    users = load_users()

    for uid, data in users.items():
        data["warnings"] = 0

    save_users_warnings(users)

    await interaction.response.send_message("✅ All users' warnings have been reset to 0.", ephemeral=True)