import discord
from discord import Embed
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta
from discord.ext import commands, tasks
from discord_client import client
from config import ADMIN_ALERT_CHANNEL_ID, GUILD_ID
from utils_helper import save_json, load_json
from storage import (
    save_users,
    get_thread_info,
    save_thread_info,
    get_user_last_active,
    save_user_last_active,
    get_json,
    save_inactivity_tracker,
    save_characters,
    load_users
)
from state import characters_data, inactivity_tracker, character_aliases, category_data



from discord.ui import View, Button

def resolve_owner(char_name, owners, aliases):
    # Try direct match (original name)
    if char_name in owners:
        return owners[char_name]

    # Try to resolve alias to original name
    for original, alias in aliases.items():
        if alias == char_name and original in owners:
            return owners[original]

    return None

async def track_inactivity_response(message):
    from datetime import datetime, timezone
    from config import ADMIN_ALERT_CHANNEL_ID
    from state import inactivity_tracker
    from storage import save_inactivity_tracker
    from discord_client import client

    user_id = str(message.author.id)
    now = datetime.now(timezone.utc).isoformat()

    for char_name, data in inactivity_tracker.items():
        if str(data.get("owner")) == user_id:
            print(f"✅ DM matched character {char_name}")

            # Always append the message with timestamp
            response_entry = {
                "content": message.content,
                "timestamp": now
            }
            data.setdefault("responses", []).append(response_entry)

            # Only set 'responded' flag on the first reply
            if not data.get("responded"):
                data["responded"] = True
                data["responded_at"] = now

            save_inactivity_tracker()

            # ✅ Always forward to the admin channel
            admin_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
            if admin_channel:
                await admin_channel.send(
                    f"📨 **{char_name}**’s mun <@{user_id}> replied:\n> {message.content}"
                )
            else:
                print("⚠️ Could not find admin channel.")

            print(f"💬 {char_name} — new reply saved and forwarded.")
            break

async def track_inactivity_response_edit(message_before, message_after):
    from datetime import datetime, timezone
    from config import ADMIN_ALERT_CHANNEL_ID
    from state import inactivity_tracker
    from storage import save_inactivity_tracker
    from discord_client import client

    user_id = str(message_after.author.id)
    now = datetime.now(timezone.utc).isoformat()

    for char_name, data in inactivity_tracker.items():
        if str(data.get("owner")) == user_id:
            # Log the edited response
            data.setdefault("responses", []).append({
                "content": f"[EDITED] {message_after.content}",
                "timestamp": now
            })

            save_inactivity_tracker()

            admin_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
            if admin_channel:
                await admin_channel.send(
                    f"✏️ **{char_name}**’s mun <@{user_id}> edited a DM reply:\n"
                    f"**Before:** {message_before.content}\n"
                    f"**After:** {message_after.content}"
                )

            print(f"✏️ {char_name} — DM edited and logged.")
            break

from collections import deque
from state import recent_dms
async def track_inactivity_response_delete(message):
    from datetime import datetime, timezone
    from config import ADMIN_ALERT_CHANNEL_ID
    from state import inactivity_tracker
    from storage import save_inactivity_tracker
    from discord_client import client

    user_id = str(message.author.id)
    now = datetime.now(timezone.utc).isoformat()

    # Try to retrieve original content from recent_dms
    deleted_text = "[unknown]"
    if user_id in recent_dms:
        for msg_id, content in recent_dms[user_id]:
            if msg_id == message.id:
                deleted_text = content
                break

    for char_name, data in inactivity_tracker.items():
        if str(data.get("owner")) == user_id:
            # Log the deleted message
            data.setdefault("responses", []).append({
                "content": f"[DELETED] {deleted_text}",
                "timestamp": now
            })

            save_inactivity_tracker()

            admin_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
            if admin_channel:
                await admin_channel.send(
                    f"🗑️ **{char_name}**’s mun <@{user_id}> deleted a DM reply:\n"
                    f"**Deleted message:** {deleted_text}"
                )

            print(f"🗑️ {char_name} — DM deletion logged.")
            break


from storage import load_users, save_users, users_data
from admin import delchar_logic
from config import USERS_FILE, MODERATOR_ROLE_ID
from state import pause_activity
#checks inacrtive characters every hour... and sends messages
async def check_inactive_characters(bot):
    await bot.wait_until_ready()

    while not bot.is_closed():
        # Ensure state is properly loaded before checking if activity is paused
        from state import pause_activity  # Load the state variable from the state file/module

        # Debug print to show the current state of pause_activity
        print(f"pause_activity: {pause_activity}")

        if pause_activity:  # Skip the loop if activity checks are paused
            print("⚠️ Activity checks are paused. Skipping inactivity checks.")
            await asyncio.sleep(60)  # Just wait a little and keep checking for commands
            continue  # Skip the rest of the function if activity is paused

        # Rest of your function continues as normal if pause_activity is False
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=3)

        owners = characters_data.get("owners", {})
        aliases = characters_data.get("aliases", {})
        activity = characters_data.get("activity", {})
        users = load_users()

        print("🔎 Validating user data...")
        for uid, data in users.items():
            if not isinstance(data, dict):
                print(f"⚠️ Auto-fixing corrupted entry for user {uid}: {type(data)}")
                users[uid] = {}

        save_users()
        users_data.update(users)

        for char_name, info in activity.items():
            last_seen_str = info.get("last_seen")
            if not last_seen_str:
                continue

            try:
                last_seen_time = datetime.fromisoformat(last_seen_str)
            except ValueError:
                continue

            if last_seen_time >= threshold:
                continue  # Still active

            base_name = aliases.get(char_name, char_name)
            owner_id = resolve_owner(base_name, owners, aliases)
            if not owner_id:
                print(f"⚠️ No owner found for {base_name}, skipping...")
                continue

            user_entry = users.get(str(owner_id), {})
            hiatus_until = user_entry.get("hiatus_until")
            if hiatus_until:
                try:
                    hiatus_dt = datetime.fromisoformat(hiatus_until)
                    if hiatus_dt > now:
                        print(f"⏸️ {base_name} is on hiatus until {hiatus_dt}, skipping inactivity check.")
                        continue

                    elif now - hiatus_dt < timedelta(hours=24):
                        print(f"🕐 {base_name} just came off hiatus, giving 24h grace period.")

                        # Track this per-character
                        char_data = characters_data.get("activity", {}).get(char_name, {})
                        if not char_data.get("hiatus_notified"):
                            try:
                                user = await bot.fetch_user(owner_id)
                                await user.send(
                                    f"👋 Hey! Your hiatus for **{base_name}** has ended.\n"
                                    f"You now have **24 hours** to post as this character before you may receive an inactivity warning."
                                )
                                print(f"✅ Sent post-hiatus DM for {base_name}.")
                            except Exception as e:
                                print(f"⚠️ Could not DM {owner_id} after hiatus: {e}")

                            # Mark character as notified
                            char_data["hiatus_notified"] = True
                            characters_data["activity"][char_name] = char_data
                            save_characters()

                        continue  # still in grace window
                except Exception as e:
                    print(f"⚠️ Error parsing hiatus_until for {base_name}: {e}")


            if base_name in inactivity_tracker:
                tracked = inactivity_tracker[base_name]
                responded_at = tracked.get("responded_at")
                if tracked.get("responded") and responded_at and not tracked.get("followed_up"):
                    try:
                        responded_time = datetime.fromisoformat(responded_at)
                        if (now - responded_time) > timedelta(hours=24):
                            if not last_seen_str or datetime.fromisoformat(last_seen_str) < responded_time:
                                alert_channel = bot.get_channel(ADMIN_ALERT_CHANNEL_ID)
                                if alert_channel:
                                    await alert_channel.send(
                                        f"⏳ **{base_name}**'s mun <@{owner_id}> replied to the inactivity DM **over 24h ago**, "
                                        f"but hasn't posted as the character since.\nConsider following up or archiving."
                                    )
                                inactivity_tracker[base_name]["followed_up"] = True
                                save_inactivity_tracker()
                    except Exception as e:
                        print(f"⚠️ Error parsing responded_at for {base_name}: {e}")

                print(f"🕒 Already notified about inactivity: {base_name}")
                continue

            days_inactive = (now - last_seen_time).days
            print(f"🚨 {base_name} ({char_name}) inactive for {days_inactive} days.")

            # ⚠️ Add warning BEFORE checking if it reached 4
            existing_warnings = user_entry.get("warnings", 0)
            current_warnings = existing_warnings + 1

            user_entry["warnings"] = current_warnings
            users[str(owner_id)] = user_entry
            users_data.update(users)
            save_users()

            # 📣 Notify admin channel (only if activity is not paused)
            if not pause_activity:
                admin_channel = bot.get_channel(ADMIN_ALERT_CHANNEL_ID)
                if admin_channel:
                    await admin_channel.send(
                        f"📣 Messaged <@{owner_id}> about inactivity for **{base_name}** ({days_inactive} days)"
                    )

            try:
                user = await bot.fetch_user(owner_id)

                if not pause_activity:  # Ensure no message is sent if activity is paused
                    if current_warnings >= 4:
                        await user.send(
                            f"🚨 Your character **{base_name}** has been marked inactive for {days_inactive} days, "
                            f"and you’ve reached the maximum number of inactivity warnings.\n\n"
                            f"⚠️ Your case is now under review by the moderators.\n"
                            f"If you’d like to stay, please reply to this message immediately to explain or request a hiatus."
                        )
                    else:
                        await user.send(
                            f"👋 Hi! Your character **{base_name}** has been inactive for {days_inactive} days.\n"
                            f"Please reply to this message within 24 hours to remain in the roleplay or request a hiatus.\n"
                            f"Your reply will be forwarded to the moderators."
                        )

                    print(f"✅ Successfully DM'd <@{owner_id}> about inactivity for {base_name}.")
                else:
                    print("⚠️ Skipping activity warning notification as activity checks are paused.")

                inactivity_tracker[base_name] = {
                    "notified_at": now.isoformat(),
                    "owner": owner_id,
                    "responded": False,
                    "responses": [],
                    "responded_at": None,
                    "followed_up": False
                }
                save_inactivity_tracker()

            except discord.Forbidden:
                print(f"❌ Couldn’t DM <@{owner_id}> ({base_name}): Forbidden (user may have DMs disabled).")
            except Exception as e:
                print(f"❌ Unexpected error while DMing <@{owner_id}> ({base_name}): {e}")

            if current_warnings >= 4 and admin_channel:
                from tracking import generate_weekly_report_embed
                embed = generate_weekly_report_embed(bot.get_guild(GUILD_ID))
                await admin_channel.send(
                    f"🚨 <@&{MODERATOR_ROLE_ID}> {user.mention} has received 4 inactivity warnings. "
                    f"Please vote whether to remove them from the roleplay.\n"
                    f"Here is their character activity:",
                    embed=embed
                )

        await asyncio.sleep(3600)  # Repeat every hour


async def viewusers_logic(interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    users = load_users()
    if not users:
        await interaction.response.send_message("No users found in the system.", ephemeral=True)
        return

    lines = ["📋 **User Overview**:\n"]

    for user_id, info in users.items():
        mention = f"<@{user_id}>"
        warnings = info.get("warnings", 0)

        lines.append(f"👤 {mention}")
        lines.append(f"🔢 Warnings: `{warnings}`")
        lines.append("—" * 25)

    await interaction.response.send_message("\n".join(lines), ephemeral=True)

def parse_timestamp(msg: discord.Message) -> float:
    return msg.edited_at.timestamp() if msg.edited_at else msg.created_at.timestamp()


async def handle_thread_activity(msg):
    from state import characters_data
    from config import CHARACTER_FILE

    # Validación básica
    if not msg.guild or not msg.channel or not msg.channel.parent:
        return

    forum_channel = msg.channel.parent
    forum_id = forum_channel.id
    forum_name = forum_channel.name

    print(f"📌 Foro detectado: {forum_name} ({forum_id})")

    if forum_id not in category_data:
        print(f"❌ Foro no rastreado: {forum_id} → '{forum_name}'")
        print(f"🔍 Foros rastreados actualmente: {category_data}")
        return

    # Ignorar si no es un tupper (webhook)
    if not msg.webhook_id:
        print(f"⛔ Mensaje ignorado, no es un webhook (tupper): {msg.author}")
        return

    # Tupper alias → personaje
    tupper_name = msg.author.display_name
    timestamp = datetime.utcnow().isoformat()

    # Inicializar la actividad semanal con 0 para todas las categorías
    initial_weekly = {cat_id: 0 for cat_id in category_data}

    characters_data["activity"].setdefault(tupper_name, {
        "thread": msg.channel.name,
        "last_seen": timestamp,
        "history": {},
        "weekly_activity": initial_weekly
    })

    char_data = characters_data["activity"][tupper_name]

    # Actualizar datos
    char_data["thread"] = msg.channel.name
    char_data["last_seen"] = timestamp
    char_data["history"][msg.channel.name] = timestamp
    char_data["weekly_activity"].setdefault(forum_id, 0)
    char_data["weekly_activity"][forum_id] += 1

    characters_data["activity"][tupper_name] = char_data

    print(f"✅ character_data actualizado para {tupper_name}: {char_data}")

    # Guardado con trazas
    print(f"💾 Guardando character_data en {CHARACTER_FILE}")
    print("📦 Contenido actual character_data:", json.dumps(characters_data, indent=2, ensure_ascii=False))
    save_json(CHARACTER_FILE, characters_data)



from storage import save_data
from state import tracking_data
from datetime import datetime
from config import GUILD_ID

async def handle_message_activity(message):
    if not message.webhook_id or not hasattr(message.author, "name"):
        return

    thread = message.channel
    now = datetime.now(timezone.utc).isoformat()
    tupper_name = message.author.name
    guild = message.guild
    thread_id = str(thread.id)
    thread_url = f"https://discord.com/channels/{guild.id}/{thread.id}"
    category_id = str(thread.parent_id) if thread.parent_id else "unknown"
    category_name = thread.parent.name if thread.parent else "unknown"

    print(f"🟡 Tupper `{tupper_name}` detected in `{thread.name}` ({thread.id})")
    print(f"📁 Forum ID: {category_id} → {category_name}")

    # Register character if missing
    if tupper_name not in characters_data["owners"]:
        from utils_helper import normalize_alias
        characters_data["owners"][tupper_name] = None
        normalized = normalize_alias(tupper_name)
        first_word = normalized.split()[0]
        characters_data["aliases"][tupper_name] = first_word

        print(f"➕ Registered new character: {tupper_name}")

    # Ensure activity block exists and assign
    if tupper_name not in characters_data["activity"]:
        characters_data["activity"][tupper_name] = {
            "thread": thread.name,
            "last_seen": now,
            "history": {},
            "weekly_activity": {}
        }

    activity = characters_data["activity"][tupper_name]
    activity["thread"] = thread.name
    activity["last_seen"] = now

    # Track history per category/thread name
    activity["history"].setdefault(category_id, {})
    activity["history"][category_id][thread.name] = now

    # Increment weekly activity for that category
    activity["weekly_activity"].setdefault(category_id, 0)
    activity["weekly_activity"][category_id] += 1
    print(f"📈 +1 to weekly_activity[{category_id}] → {activity['weekly_activity'][category_id]}")

    # Track thread for all known users
    for user_id in tracking_data:
        tracked_threads = tracking_data[user_id].setdefault("tracked_threads", {})
        tracked_threads.setdefault(thread_id, {
            "name": thread.name,
            "link": thread_url,
            "last_active_tupper": None,
            "last_active_time": None,
            "activity_log": {}
        })

        tracked_threads[thread_id]["last_active_time"] = now
        tracked_threads[thread_id]["last_active_tupper"] = tupper_name
        tracked_threads[thread_id]["activity_log"][tupper_name] = now

    save_characters()
    save_data()
    print("✅ character_data and tracking_data saved.")
    
async def flag_user_inactive(bot: commands.Bot, user: discord.User, thread: discord.Thread, threshold: float):
    # Usamos el nombre del hilo como identificador del personaje
    base_name = character_aliases.get(thread.name, thread.name)
    char_data = characters_data.get("activity", {}).get(base_name, {})
    last_seen_str = char_data.get("last_seen")

    if not last_seen_str:
        return

    try:
        last_seen_dt = datetime.fromisoformat(last_seen_str)
    except ValueError:
        return

    if (datetime.utcnow() - last_seen_dt).total_seconds() < threshold:
        return

    if base_name in inactivity_tracker:
        return

    inactivity_tracker[base_name] = {
        "notified_at": datetime.utcnow().isoformat(),
        "owner": user.id,
        "responded": False,
        "responses": [],
        "responded_at": None,
    }

    # DM the user
    try:
        await user.send(
            f"Hi there! 👋 Your character **{thread.name}** hasn't posted in **{thread.parent.name}** for a while.\n"
            f"Please reply to confirm you're still active, or let us know if you need a hiatus."
        )
    except discord.Forbidden:
        print(f"Couldn't DM {user.name}")

    # Notify admin channel
    channel = bot.get_channel(ADMIN_ALERT_CHANNEL_ID)
    if channel:
        timestamp_unix = int(last_seen_dt.replace(tzinfo=timezone.utc).timestamp())
        await channel.send(
            f"⚠️ {user.mention} has been flagged as **inactive** in `{thread.name}`.\n"
            f"Last seen: <t:{timestamp_unix}:R>"
        )

    save_inactivity_tracker()


def generate_weekly_report_embed(guild):
    embed = Embed(
        title="📊 Weekly Activity Report",
        description=f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        color=0x5E9CD3
    )

    owners = characters_data.get("owners", {})
    activity = characters_data.get("activity", {})

    # Group characters by user
    user_characters = {}
    for char_name, info in activity.items():
        owner_id = owners.get(char_name)
        if not owner_id:
            continue
        user_characters.setdefault(owner_id, []).append(char_name)

    for user_id, chars in user_characters.items():
        member = guild.get_member(int(user_id))
        display_name = member.display_name if member else f"<@{user_id}>"

        lines = []

        for char in chars:
            char_data = activity.get(char, {})
            weekly = char_data.get("weekly_activity", {})

            thread_count = 0
            imessage_count = 0

            for forum_id, msg_count in weekly.items():
                forum_channel = guild.get_channel(int(forum_id))
                if forum_channel and hasattr(forum_channel, 'parent') and forum_channel.parent:
                    parent_name = forum_channel.parent.name.lower()
                    if "thread" in parent_name:
                        thread_count += msg_count
                    else:
                        imessage_count += msg_count
                else:
                    # Fallback if parent is missing
                    imessage_count += msg_count

            lines.append(f"• **{char}**\n  ↳ threads: `{thread_count}` | imessages: `{imessage_count}`")

        embed.add_field(name=display_name, value="\n".join(lines), inline=False)

    return embed

class WarningView(View):
    def __init__(self, user_id, character_name):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.character_name = character_name

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Logic for confirming the warning
        await interaction.response.send_message(f"✅ Warning for `{self.character_name}` has been acknowledged.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Logic for canceling the warning
        await interaction.response.send_message(f"❌ Warning for `{self.character_name}` has been dismissed.", ephemeral=True)
        self.stop()

async def send_warning(user: discord.Member, character_name: str):
    view = WarningView(user.id, character_name)
    try:
        await user.send(f"⚠️ Your character `{character_name}` has been inactive. Please confirm your activity.", view=view)
    except discord.Forbidden:
        print(f"Could not send a warning to {user.name}.")