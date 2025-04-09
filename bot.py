from datetime import timezone
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import asyncio
from collections import deque

# Import logic from other files
from admin import (
    trackforum_logic, 
    cleardata_logic, 
    givechar_logic, 
    renamechar_logic, 
    delchar_logic, 
    accept_logic,   
    viewall_command,
    hiatus_logic,
    viewinactive_logic
)
from tracking import handle_message_activity, generate_weekly_report_embed
from storage import load_data, save_data, load_characters, save_characters, delete_character_by_name, users_data, save_users, get_character_owner, remove_character, tracking_data, still_has_characters, character_owners, registered_characters, admin_tracked_categories
from datetime import datetime, timedelta
from config import ADMIN_ALERT_CHANNEL_ID, ARCHIVE_CATEGORY_ID, MUN_ROLE_ID, CHARACTER_FILE
from utils_helper import get_forum_channel_from_link, save_json
from state import characters_data, category_data, tracking_data, pause_activity_function, resume_activity_function
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
from state import inactivity_tracker
from storage import save_inactivity_tracker
intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)
now = datetime.now(timezone.utc)
recent_dms = {}


## COMANDS AVAILABLE ##

@client.tree.command(name="ping", description="Test command to check if the bot is working")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)

## TRACK FORUM COMMAND ##
#@client.tree.command(name="trackforum", description="Add a forum category to be tracked for admin reports")
#async def trackforum(interaction: discord.Interaction, category: discord.ForumChannel):
#    await trackforum_logic(interaction, category)

## CLEAR DATA COMMAND ##
#@client.tree.command(name="cleardata", description="Clear all tracking and character data (admin only)")
#async def cleardata(interaction: discord.Interaction, confirm: bool = False):
#    await cleardata_logic(interaction, confirm)

## VIEW INACTIVE COMMAND ##
#@client.tree.command(name="viewinactive", description="List characters inactive for more than 3 days (Admin Only)")
#async def viewinactive(interaction: discord.Interaction):
#    await viewinactive_logic(interaction)

## GIVE CHARACTER COMMAND ##
@client.tree.command(name="givechar", description="Assign a character to a user (Admin Only)")
@app_commands.describe(character="Character name (Tupper)", user="User to assign the character to")
async def givechar(interaction: discord.Interaction, character: str, user: discord.Member):
    from admin import givechar_logic
    await givechar_logic(interaction, character, user)

## RENAME CHARACTER COMMAND ##
@client.tree.command(name="renamechar", description="Rename a character (Admin Only)")
@app_commands.describe(old_name="Current character name", new_name="New character name")
async def renamechar(interaction: discord.Interaction, old_name: str, new_name: str):
    await renamechar_logic(interaction, old_name, new_name)

## DELETE CHARACTER COMMAND ##
@client.tree.command(name="delchar", description="Delete a character and archive their forum")
@app_commands.describe(name_or_owner="Character name or alias", confirm="Type true to confirm deletion")
async def delchar(interaction: discord.Interaction, name_or_owner: str, confirm: bool = False):
    result = await delchar_logic(interaction, name_or_owner, interaction.guild, confirm)
    if result:
        await interaction.response.send_message(result, ephemeral=True)


## ACCEPT COMMAND ##
@client.tree.command(name="accept", description="Accept a new user and start 48h setup timer")
@app_commands.describe(user="User to accept", forum_post="Forum post link")
async def accept_command(interaction: discord.Interaction, user: discord.Member, forum_post: str):
    await accept_logic(interaction, user, forum_post)

## VIEWALL COMMAND ##
@client.tree.command(name="viewall", description="List all characters or filter by owner/alias/name")
@app_commands.describe(filter="Optional filter: character name, alias or owner ID")
async def viewall(interaction: discord.Interaction, filter: str = None):
    
    await viewall_command(interaction, filter)

## HIATUS COMMAND ##
@client.tree.command(name="hiatus", description="Put a user on hiatus for X days")
@app_commands.describe(user="User to put on hiatus", days="Number of days")
async def hiatus_command(interaction: discord.Interaction, user: discord.Member, days: int):
    await hiatus_logic(interaction, user, days)

from utils_helper import reset_warnings_for_user, reset_warnings_for_all
# Command to reset warnings for a specific user
# Command to reset warnings for a specific user
@client.tree.command(name="resetwarnings", description="Reset the warnings of a specific user")
@app_commands.describe(user="The user to reset warnings for")
async def reset_warnings_for_user_command(interaction: discord.Interaction, user: discord.Member):
    await reset_warnings_for_user(interaction, user)


from tracking import viewusers_logic
@client.tree.command(name="viewwarnings", description="Admin-only: View all users with warnings and characters")
async def viewusers_command(interaction: discord.Interaction):
    await viewusers_logic(interaction)

# Command to reset warnings for all users
@client.tree.command(name="resetallwarnings", description="Reset the warnings of all users")
async def reset_warnings_for_all_command(interaction: discord.Interaction):
    await reset_warnings_for_all(interaction)
from discord import app_commands
from datetime import datetime, timezone, timedelta
from state import characters_data

## TRACKING COMMAND ##
@client.tree.command(name="tracking", description="See your character threads and whose turn it is.")
async def tracking(interaction: discord.Interaction):
    from datetime import datetime, timezone, timedelta
    from state import characters_data

    user_id = str(interaction.user.id)
    now = datetime.now(timezone.utc)

    # STEP 1: Find characters owned by the user
    owned_chars = [
        name for name, owner in characters_data["owners"].items()
        if str(owner) == user_id
    ]

    if not owned_chars:
        await interaction.response.send_message("😢 You don't have any assigned characters.", ephemeral=True)
        return

    # STEP 2: Build a set of all threads YOUR characters are in
    relevant_threads = set()  # (forum_id, thread_name)

    for char in owned_chars:
        activity = characters_data["activity"].get(char, {})
        history = activity.get("history", {})
        for forum_id, threads in history.items():
            for thread_name in threads:
                if thread_name.strip().upper() != "TRACKER_SETUP !":
                    relevant_threads.add((forum_id, thread_name))

    if not relevant_threads:
        await interaction.response.send_message("🫥 Your characters are not active in any threads.", ephemeral=True)
        return

    # STEP 3: For each relevant thread, gather full character activity
    thread_map = {}  # (forum_id, thread_name): {"entries": [(char, last_seen)], "thread_id": ...}

    for char, activity in characters_data["activity"].items():
        history = activity.get("history", {})
        for forum_id, threads in history.items():
            for thread_name, last_seen in threads.items():
                key = (forum_id, thread_name)
                if key not in relevant_threads:
                    continue

                if key not in thread_map:
                    thread_map[key] = {"entries": [], "thread_id": None}

                thread_map[key]["entries"].append((char, last_seen))

                # Try to get thread ID
                for thread in interaction.guild.threads:
                    if thread.name == thread_name and str(thread.parent_id) == forum_id:
                        thread_map[key]["thread_id"] = thread.id
                        break

    # STEP 4: Build the display
    lines = [f"📊 **Tracked threads for your characters:**\n"]

    for (forum_id, thread_name), data in thread_map.items():
        entries = data["entries"]
        thread_id = data["thread_id"]

        timestamps = [datetime.fromisoformat(ts) for _, ts in entries]
        if all((now - t) > timedelta(days=14) for t in timestamps):
            continue  # skip inactive

        sorted_chars = sorted(entries, key=lambda item: datetime.fromisoformat(item[1]))
        turn_order = [char for char, _ in sorted_chars]
        next_up = turn_order[0] if turn_order else "❓"

        if thread_id:
            thread_link = f"https://discord.com/channels/{interaction.guild.id}/{thread_id}"
            lines.append(f"🧵 [`{thread_name}`]({thread_link})")
        else:
            lines.append(f"🧵 `{thread_name}` (ID unknown)")

        lines.append(f"🔁 Turn order: {' → '.join(turn_order)}")
        lines.append(f"🎯 Next up: **{next_up}**\n")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)

## PAUSE/RESUME ACTIVITY CHECKS ##
@client.tree.command(name="pauseactivity", description="Pause all activity checks for everyone.")
async def pause_activity_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return
    
    pause_activity_function()  # Pause activity checks
    await interaction.response.send_message("✅ Activity checks have been paused.", ephemeral=True)

@client.tree.command(name="resumeactivity", description="Resume all activity checks for everyone.")
async def resume_activity_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return
    
    resume_activity_function()  # Resume activity checks
    await interaction.response.send_message("✅ Activity checks have been resumed.", ephemeral=True)

from tracking import track_inactivity_response, track_inactivity_response_edit, track_inactivity_response_delete
## ON MESSAGE TRACKING ##
@client.event
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # ✅ Handle DMs from muns
    if isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)

        # Cache for edit/delete tracking
        if user_id not in recent_dms:
            recent_dms[user_id] = deque(maxlen=10)
        recent_dms[user_id].append((message.id, message.content))

        await track_inactivity_response(message)

        from state import inactivity_tracker
        from storage import save_inactivity_tracker
        from config import ADMIN_ALERT_CHANNEL_ID

        matched_characters = []

        for char_name, info in inactivity_tracker.items():
            if str(info.get("owner")) == user_id:
                info["responded"] = True
                info["responded_at"] = now.isoformat()
                info.setdefault("responses", []).append({
                    "message": message.content,
                    "timestamp": now.isoformat()
                })
                matched_characters.append(char_name)

        if matched_characters:
            save_inactivity_tracker()

            alert_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
            if matched_characters:
                alert_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)

                def format_names(names):
                    if len(names) == 1:
                        return names[0]
                    elif len(names) == 2:
                        return f"{names[0]} and {names[1]}"
                    else:
                        return f"{', '.join(names[:-1])}, and {names[-1]}"

                formatted_names = format_names(matched_characters)
                view = None

                # Pick the first matched character to anchor the reply button
                primary_char = matched_characters[0]
                tracked = inactivity_tracker[primary_char]

                if not tracked.get("reply_button_sent", False):
                    view = AdminReplyView(primary_char, user_id)
                    tracked["reply_button_sent"] = True
                
                save_inactivity_tracker()

                if alert_channel:
                    await alert_channel.send(
                        f"📩 **{formatted_names}**'s owner (<@{user_id}>) replied:\n> {message.content}",
                        view=view
                    )

                print(f"[DM] <@{user_id}> replied for {matched_characters}: {message.content}")


            print(f"[DM] <@{user_id}> replied for {matched_characters}: {message.content}")

    # ✅ Handle Tupper messages in guild (unchanged)
    elif message.guild is not None:
        await handle_message_activity(message)

    await client.process_commands(message)


## EDITED MESSAGE TRACKING ##
@client.event
async def on_message_edit(before, after):
    if isinstance(after.channel, discord.DMChannel):
        user_id = str(after.author.id)

        # Update recent DM cache
        if user_id in recent_dms:
            for i, (msg_id, _) in enumerate(recent_dms[user_id]):
                if msg_id == before.id:
                    recent_dms[user_id][i] = (after.id, after.content)
                    break

        from datetime import datetime, timezone
        from state import inactivity_tracker
        from storage import save_inactivity_tracker
        from config import ADMIN_ALERT_CHANNEL_ID

        now = datetime.now(timezone.utc)

        for char_name, info in inactivity_tracker.items():
            if str(info.get("owner")) == user_id:
                info.setdefault("responses", []).append({
                    "message": f"[EDITED] {after.content}",
                    "timestamp": now.isoformat()
                })

                save_inactivity_tracker()

                channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
                if channel:
                    await channel.send(
                        f"✏️ **{char_name}**’s mun <@{user_id}> edited their reply:\n"
                        f"**Before:** {before.content}\n**After:** {after.content}"
                    )
                print(f"[DM-EDIT] {char_name}’s owner ({user_id}) edited their reply:")
                print(f"> Before: {before.content}")
                print(f"> After : {after.content}")

## DELETED MESSAGE TRACKING ##
@client.event
async def on_message_delete(message):
    if isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        deleted_text = "[unknown]"

        # Try to find message content from recent cache
        for msg_id, content in recent_dms.get(user_id, []):
            if msg_id == message.id:
                deleted_text = content
                break

        from datetime import datetime, timezone
        from state import inactivity_tracker
        from storage import save_inactivity_tracker
        from config import ADMIN_ALERT_CHANNEL_ID

        now = datetime.now(timezone.utc)

        for char_name, info in inactivity_tracker.items():
            if str(info.get("owner")) == user_id:
                info.setdefault("responses", []).append({
                    "message": f"[DELETED] {deleted_text}",
                    "timestamp": now.isoformat()
                })

                save_inactivity_tracker()

                channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
                if channel:
                    await channel.send(
                        f"🗑️ **{char_name}**’s mun <@{user_id}> deleted their reply:\n"
                        f"**Deleted Message:** {deleted_text}"
                    )
                print(f"[DM-DELETE] {char_name}’s owner ({user_id}) deleted a reply:")
                print(f"> Deleted Message: {deleted_text}")


## THREAD CREATION TRACKING ##
async def handle_thread_creation(thread):
    print(f"🔧 handle_thread_creation called for: {thread.name} ({thread.id})")

    now = datetime.now(timezone.utc).isoformat()
    guild_id = thread.guild.id
    thread_id = str(thread.id)
    thread_url = f"https://discord.com/channels/{guild_id}/{thread.id}"

    detected_characters = set()

    # Recorremos los últimos mensajes del hilo
    async for msg in thread.history(limit=50):
        if msg.webhook_id and hasattr(msg.author, "name"):
            char_name = msg.author.name
            detected_characters.add(char_name)
            print(f"🟡 Tupper `{char_name}` detected in `{thread.name}` ({thread.id})")

            # Registro automático de personaje
            if char_name not in characters_data["owners"]:
                characters_data["owners"][char_name] = None
                characters_data["aliases"][char_name] = char_name.lower().split()[0]
                print(f"➕ Registered character `{char_name}`")

            if char_name not in characters_data["activity"]:
                characters_data["activity"][char_name] = {
                    "thread": thread.name,
                    "last_seen": msg.created_at.isoformat(),
                    "history": {thread.name: msg.created_at.isoformat()},
                    "weekly_activity": {cat_id: 0 for cat_id in category_data}
                }

    # Añadimos el hilo a todos los usuarios que ya tienen datos en tracking_data
    for user_id in tracking_data:
        tracked_threads = tracking_data[user_id].setdefault("tracked_threads", {})

        if thread_id not in tracked_threads:
            tracked_threads[thread_id] = {
                "link": thread_url,
                "name": thread.name,
                "last_active_tupper": None,
                "last_active_time": None,
                "activity_log": {}
            }

        for char_name in detected_characters:
            tracked_threads[thread_id]["activity_log"][char_name] = now

    # Guardamos los cambios
    print("💾 Saving characters_data and tracking_data...")
    save_characters()
    save_data()
    print("✅ Thread and character data saved.")




## SENDS ADMIN UPDATES BEFORE RESTARTING TRACKER ##
@tasks.loop(hours=24)
async def reset_weekly_activity():
    from datetime import timezone
    now = datetime.now(timezone.utc)

    last_reset_str = characters_data.get("_meta", {}).get("last_weekly_reset")
    if last_reset_str:
        last_reset = datetime.fromisoformat(last_reset_str).replace(tzinfo=timezone.utc)
    else:
        last_reset = datetime.min.replace(tzinfo=timezone.utc)

    if (now - last_reset) >= timedelta(days=7):
        for char_name, data in characters_data.get("activity", {}).items():
            if "weekly_activity" in data:
                for category_id in data["weekly_activity"]:
                    data["weekly_activity"][category_id] = 0

        # Guardar la nueva fecha de reset
        characters_data["_meta"] = characters_data.get("_meta", {})
        characters_data["_meta"]["last_weekly_reset"] = now.isoformat()

        save_characters()
        print("✅ Weekly activity counters have been reset.")


@client.tree.command(name="weeklyactive", description="View weekly activity report by owner")
async def weekly_active_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    embed = generate_weekly_report_embed(interaction.guild)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="reject", description="Reject a user and notify them privately")
@app_commands.describe(user="User to reject", reason="Reason for rejection")
async def reject_command(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    # Notify the user privately via DM
    try:
        await user.send(
            f"🚫 Hi {user.display_name}, your application to **CRESTFALL** has been rejected.\n"
            f"**Reason:** {reason}\n"
            f"If you have any questions, feel free to contact the moderators."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            f"⚠️ Could not DM {user.mention}. They might have DMs disabled.",
            ephemeral=True
        )

    # Log the rejection in the activity channel
    activity_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
    if activity_channel:
        await activity_channel.send(
            f"🚫 **{user.mention}** has been rejected by {interaction.user.mention}.\n"
            f"**Reason:** {reason}"
        )

    # Confirm the rejection to the admin
    await interaction.response.send_message(
        f"✅ {user.mention} has been rejected and notified via DM.",
        ephemeral=True
    )


#allows us to reply to the mun in dms
class AdminReplyView(discord.ui.View):
    def __init__(self, char_name, user_id):
        super().__init__(timeout=None)
        self.char_name = char_name
        self.user_id = user_id

    @discord.ui.button(label="Reply to Mun", style=discord.ButtonStyle.primary, custom_id="admin_reply_button")
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminReplyModal(self.char_name, self.user_id))


class AdminReplyModal(discord.ui.Modal, title="Reply to Mun"):
    def __init__(self, char_name, user_id):
        super().__init__()
        self.char_name = char_name
        self.user_id = user_id

        self.response_input = discord.ui.TextInput(
            label="Your message",
            style=discord.TextStyle.paragraph,
            placeholder="Type the message to send to the mun...",
            max_length=2000,
            required=True
        )
        self.add_item(self.response_input)

    async def on_submit(self, interaction: discord.Interaction):
        response_text = self.response_input.value

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(
                f"📬 **Mod reply about your character _{self.char_name}_**:\n> {response_text}"
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to DM user <@{self.user_id}>: {e}", ephemeral=True
            )
            return

        # Log the mod response
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        tracked = inactivity_tracker.get(self.char_name)
        if tracked:
            tracked.setdefault("responses", []).append({
                "message": f"[MOD REPLY] {response_text}",
                "timestamp": now
            })
            save_inactivity_tracker()

        # ✅ Reply in admin channel with the message and "Send another" button
        view = AdminReplyView(self.char_name, self.user_id)
        await interaction.response.send_message(
            f"✅ Reply sent and logged!\n\n"
            f"📬 You said:\n> {response_text}\n\n"
            f"🔁 Want to send another?",
            view=view,
            ephemeral=False  # or True if you want it hidden
        )


## SEND DM TO USER ##
@client.tree.command(name="dm_user", description="Manually DM a mun about their character.")
@app_commands.describe(character="Name of the character (Tupper name)", message="Message to send to the user")
async def dm_user(interaction: discord.Interaction, character: str, message: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    tracked = inactivity_tracker.get(character)
    if not tracked:
        await interaction.response.send_message(f"⚠️ No entry found for character: `{character}`.", ephemeral=True)
        return

    owner_id = tracked.get("owner")
    if not owner_id:
        await interaction.response.send_message(f"⚠️ Character `{character}` has no owner.", ephemeral=True)
        return

    try:
        user = await client.fetch_user(owner_id)
        await user.send(f"📬 **Mod Message about your character _{character}_**:\n> {message}")

        # ✅ Log it
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        tracked.setdefault("responses", []).append({
            "message": f"[MANUAL MOD MESSAGE] {message}",
            "timestamp": now
        })
        save_inactivity_tracker()

        # ✅ Forward to the activity channel
        activity_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
        if activity_channel:
            await activity_channel.send(
                f"📤 **Manual DM sent** by {interaction.user.mention} regarding **{character}**:\n"
                f"> {message}"
            )

        await interaction.response.send_message(
            f"✅ DM sent to <@{owner_id}> and logged under `{character}`.",
            ephemeral=True
        )

    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to DM user: {e}", ephemeral=True)


## BUTTONS FOR CHECKING SETUP ##
class CheckSetupButtons(discord.ui.View):
    def __init__(self, user_id, forum_key):
        super().__init__(timeout=None)
        self.user_id = int(user_id)
        self.forum_key = forum_key

    @discord.ui.button(label="✅ Yes — user is active", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        users_data[str(self.user_id)][self.forum_key]["checked"] = True
        save_users()

        forum_channel = await get_forum_channel_from_link(self.user_id, self.forum_key, interaction.guild, users_data)
        forum_name = forum_channel.name

        await asyncio.sleep(1)
        await interaction.message.delete()

        await interaction.channel.send(
            f"✅ Check-up for `{forum_name}` and <@{self.user_id}> finished!"
        )




    @discord.ui.button(label="❌ No — ask them to reapply", style=discord.ButtonStyle.danger)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = guild.get_member(self.user_id)
        user_id_str = str(self.user_id)

        forum_channel = await get_forum_channel_from_link(self.user_id, self.forum_key, guild, users_data)
        forum_name = forum_channel.name
        archive_category = guild.get_channel(ARCHIVE_CATEGORY_ID)

        if archive_category:
            await forum_channel.edit(
                category=archive_category,
                name=f"archived-{forum_channel.name}"
            )
            await asyncio.sleep(1)

        users_data[user_id_str]["assigned_count"] -= 1
        del users_data[user_id_str][self.forum_key]

        if users_data[user_id_str]["assigned_count"] < 1:
            mun_role = guild.get_role(MUN_ROLE_ID)
            if user and mun_role:
                await user.remove_roles(mun_role)
                await asyncio.sleep(1)

            parent_category = forum_channel.category
            if parent_category and parent_category != archive_category:
                try:
                    await parent_category.delete()
                    await asyncio.sleep(1)
                except:
                    pass

        save_users()

        if user:
            try:
                await user.send(
                    "🚫 Hi! You didn’t set up your character for **CRESTFALL** in time. "
                    "Please reapply if you're still interested."
                )
            except:
                pass

        await asyncio.sleep(1)
        await interaction.message.delete()

        await interaction.channel.send(
            f"✅ Check-up for `{forum_name}` and <@{self.user_id}> finished!"
        )

## CHECK USER SETUP TIMERS ##
@tasks.loop(minutes=30)
async def check_user_setup_timers():
    await client.wait_until_ready()
    datetime.now(timezone.utc)

    for user_id, info in users_data.items():
        for key, forum_data in info.items():
            if not key.startswith("forum_") or forum_data.get("checked"):
                continue

            accepted_time = datetime.fromisoformat(forum_data["accepted_at"])
            if accepted_time.tzinfo is None:
                accepted_time = accepted_time.replace(tzinfo=timezone.utc)

            if now - accepted_time > timedelta(hours=48):
                channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
                if channel:
                    view = CheckSetupButtons(user_id=user_id, forum_key=key)
                    await channel.send(
                        f"🕵️ **Check Setup for <@{user_id}>**\nForum link: {forum_data['link']}",
                        view=view
                    )
                    forum_data["checked"] = True
                    save_users()

@tasks.loop(minutes=5)
async def upload_json_backups():
    await client.wait_until_ready()
    backup_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
    if not backup_channel:
        print("❌ Backup channel not found!")
        return

    files = []
    paths = [
        "data/character_data.json",
        "data/users.json",
        "data/inactivity_dm_tracker.json",
        "data/category_data.json"
    ]

    for path in paths:
        if os.path.exists(path):
            files.append(discord.File(path))
        else:
            print(f"⚠️ File not found: {path}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    await backup_channel.send(content=f"📦 JSON backup at `{timestamp}`", files=files)
    print("✅ Uploaded JSON backups to Discord.")


from tracking import check_inactive_characters
from config import MODERATOR_ROLE_ID
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    # 🔔 Notify mods
    activity_champion = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
    if activity_champion:
        mod_mention = f"<@&{MODERATOR_ROLE_ID}>"
        await activity_champion.send(f"🟢 Bot is now online and running! {mod_mention}")

    # 🕵️ Start timers if not running
    if not check_user_setup_timers.is_running():
        check_user_setup_timers.start()

    if not reset_weekly_activity.is_running():
        reset_weekly_activity.start()

    if not upload_json_backups.is_running():
        upload_json_backups.start()

    # 🧠 Start inactivity check (only once)
    if not hasattr(client, "inactivity_started"):
        client.loop.create_task(check_inactive_characters(client))
        client.inactivity_started = True

    # 🔁 Sync command tree
    await client.tree.sync()

    print("✅ Ready and fully synced.") 



client.run(TOKEN)