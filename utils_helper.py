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
