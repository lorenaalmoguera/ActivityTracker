import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import json
import os
import asyncio
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # ✅ matches your .env file key
TRACK_FILE = "tracking_data.json"
CHARACTER_FILE = "character_data.json"
CATEGORY_FILE = "category_data.json"
USERS_FILE="users.json"

intents = discord.Intents.all()
intents.guilds = True
intents.message_content = True
intents.messages = True
intents.members = True


GUILD_ID = discord.Object(id=1278339570320019577)  # Replace with your server ID

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        self.loop.create_task(check_inactive_characters())  # ✅ starts your background task
        self.loop.create_task(check_user_setup_timers())

        await self.tree.sync()  # optional: sync global commands


# Character ownership mapping (name → user ID)
  # List of forum channel IDs to track (shared across all admins)  # List of forum channel IDs to track
client = commands.Bot(command_prefix="!", intents=intents)

INACTIVITY_TRACKER_FILE = "inactivity_dm_tracker.json"
ADMIN_ALERT_CHANNEL_ID = 1356640519249465444  # Replace with your mod channel ID

def load_inactivity_tracker():
    if os.path.exists(INACTIVITY_TRACKER_FILE):
        with open(INACTIVITY_TRACKER_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_inactivity_tracker():
    with open(INACTIVITY_TRACKER_FILE, "w") as f:
        json.dump(inactivity_tracker, f, indent=2)

inactivity_tracker = load_inactivity_tracker()

def load_characters():
    if os.path.exists(CHARACTER_FILE):
        with open(CHARACTER_FILE, "r") as f:
            try:
                data = json.load(f)
                if "owners" not in data:
                    data["owners"] = {}
                if "aliases" not in data:
                    data["aliases"] = {}
                if "activity" not in data:
                    data["activity"] = {}
                return data
            except json.JSONDecodeError:
                return {"owners": {}, "aliases": {}, "activity": {}}
    return {"owners": {}, "aliases": {}, "activity": {}}
characters_data = load_characters()




def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
users_data = load_users()


def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users_data, f, indent=2)

# Load once at startup

def load_categories():
    if os.path.exists(CATEGORY_FILE):
        with open(CATEGORY_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

characters_data = load_characters()
character_owners = characters_data.get("owners", {})
character_aliases = characters_data.get("aliases", {})
admin_tracked_categories = load_categories()
if isinstance(admin_tracked_categories, dict):
    admin_tracked_categories = list(admin_tracked_categories.values())
def load_data():
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def load_categories():
    if os.path.exists(CATEGORY_FILE):
        with open(CATEGORY_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []
    return {}

def save_data(data):
    with open(TRACK_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print("📤 Saving tracking data:", tracking_data)


def save_characters():
    with open(CHARACTER_FILE, "w") as f:
        json.dump({
            "owners": character_owners,
            "aliases": character_aliases,
            "activity": characters_data.get("activity", {})
        }, f, indent=2)
    print("📤 Saving character data:", {
        "owners": character_owners,
        "aliases": character_aliases,
        "activity": characters_data.get("activity", {})
    })
    print("📂 Tracking file path:", os.path.abspath(TRACK_FILE))
    print("📂 Character file path:", os.path.abspath(CHARACTER_FILE))

def save_categories():
    with open(CATEGORY_FILE, "w") as f:
        json.dump(admin_tracked_categories, f, indent=2)

tracking_data = load_data()

# CHARACTER TRACKING
registered_characters = set(character_owners.keys())

def extract_thread_id(link):
    try:
        parts = link.strip().split("/")
        return parts[-1] if parts else None
    except:
        return None


#### THREAD TRACKING FOR USERS

@client.tree.command(name="track", description="Track a thread by its link")
@app_commands.describe(link="Paste the full Discord thread link")
async def trackthread(interaction: discord.Interaction, link: str):
    user_id = str(interaction.user.id)
    thread_id = extract_thread_id(link)
    if not thread_id:
        await interaction.response.send_message("❌ **Invalid thread link.**", ephemeral=True)
        return

    if user_id not in tracking_data:
        tracking_data[user_id] = {"tracked_threads": {}}

    if thread_id in tracking_data[user_id]["tracked_threads"]:
        await interaction.response.send_message("⚠️ **You're already tracking this thread.**", ephemeral=True)
        return

    try:
        thread = await interaction.guild.fetch_channel(int(thread_id))

        tracking_data[user_id]["tracked_threads"][thread_id] = {
            "link": link,
            "name": thread.name,
            "last_active_tupper": None,
            "last_active_time": None
        }

        # Auto-register characters seen in this thread
        async for msg in thread.history(limit=50):
            if msg.webhook_id:
                char_name = msg.author.name
                if char_name not in character_owners:
                    registered_characters.add(char_name)

        save_data(tracking_data)
        await interaction.response.send_message(f"✅ **Added {thread.name} to your tracked threads.**", ephemeral=True)
    except:
        await interaction.response.send_message("❌ **Could not find thread. Make sure the link is correct.**", ephemeral=True)

@client.tree.command(name="untrack", description="Stop tracking a thread")
@app_commands.describe(link="Link to the thread you want to untrack")
async def deletetrackthread(interaction: discord.Interaction, link: str):
    user_id = str(interaction.user.id)
    thread_id = extract_thread_id(link)
    if user_id in tracking_data and thread_id in tracking_data[user_id]["tracked_threads"]:
        thread_name = tracking_data[user_id]["tracked_threads"][thread_id]["name"]
        del tracking_data[user_id]["tracked_threads"][thread_id]
        save_data(tracking_data)
        await interaction.response.send_message(f"🗑️ **Removed {thread_name} from your tracked threads.**", ephemeral=True)
    else:
        await interaction.response.send_message("❌ **You're not tracking this thread.**", ephemeral=True)

@deletetrackthread.autocomplete("link")
async def deletetrackthread_autocomplete(interaction: discord.Interaction, current: str):
    user_id = str(interaction.user.id)
    results = []
    if user_id in tracking_data:
        for thread_id, info in tracking_data[user_id]["tracked_threads"].items():
            thread_name = info.get("name", "Unnamed")
            link = info.get("link", "")
            if current.lower() in thread_name.lower():
                results.append(app_commands.Choice(name=thread_name, value=link))
    return results[:25]

@client.tree.command(name="tracking", description="View your tracked threads")
async def viewtracking(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in tracking_data or not tracking_data[user_id]["tracked_threads"]:
        await interaction.response.send_message("📭 **You have no tracked threads.**", ephemeral=True)
        return

    msg = "📘 **Your Tracked Threads:**\n"
    found = False

    for thread_id, info in tracking_data[user_id]["tracked_threads"].items():
        name = info.get("name", "Unknown")
        link = info.get("link", "No link")
        activity_log = info.get("activity_log", {})

        msg += f"**Thread:** [{name}]({link})\n"

        if not activity_log:
            msg += "_No character activity yet._\n\n"
            continue

        # Collect and sort character activity
        char_entries = []
        for tupper_raw, last_seen in activity_log.items():
            try:
                dt = datetime.fromisoformat(last_seen)
            except:
                dt = datetime.min
            char_entries.append((tupper_raw, dt))

        # Sort by oldest activity (first = longest ago)
        char_entries.sort(key=lambda x: x[1])

        # Track each character
        for tupper_raw, last_seen_dt in char_entries:
            alias = character_aliases.get(tupper_raw, tupper_raw)
            owner_lookup = character_aliases.get(tupper_raw, tupper_raw)
            owner_id = character_owners.get(owner_lookup)
            owner_display = f"<@{owner_id}>" if owner_id else "Unassigned"
            last_seen_fmt = last_seen_dt.strftime("%Y-%m-%d %H:%M:%S")
            msg += f"🎭 **{alias}** ({owner_display}) 🕰️ **Last Seen:** {last_seen_fmt}\n"

        # ✅ Add turn tracker
        turn_raw = char_entries[0][0]  # First = longest inactive
        turn_alias = character_aliases.get(turn_raw, turn_raw)
        msg += f"🌀 **Turn:** {turn_alias}\n\n"
        found = True

    if not found:
        msg += "_No character activity found yet._"

    await interaction.response.send_message(msg, ephemeral=True)


@client.tree.command(name="givechar", description="Assign a character name to a Discord user")
@app_commands.describe(character_name="Name of the character (as appears in Tupperbox)", user="User who owns this character")
async def assigncharacter(interaction: discord.Interaction, character_name: str, user: discord.User):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ **You don’t have permission to assign characters.**", ephemeral=True)
        return
    character_owners[character_name] = user.id
    save_characters()
    await interaction.response.send_message(f"✅ **Assigned `{character_name}` to {user.mention}.**", ephemeral=True)

@client.tree.command(name="renamechar", description="Rename a character globally")
@app_commands.describe(old_name="Old character name", new_name="New name to use")
async def renamecharacter(interaction: discord.Interaction, old_name: str, new_name: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ **You don’t have permission to rename characters.**", ephemeral=True)
        return
    character_aliases[old_name] = new_name
    save_characters()
    await interaction.response.send_message(f"✅ **Renamed `{old_name}` to `{new_name}` for tracking purposes.**", ephemeral=True)

@client.tree.command(name="trackforum", description="Add a forum category to be tracked for admin reports")
@app_commands.describe(category="Select a forum channel to track")
async def addcategory(interaction: discord.Interaction, category: discord.ForumChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **You must be an administrator to use this command.**", ephemeral=True)
        return

    if category.id not in admin_tracked_categories:
        admin_tracked_categories.append(category.id)
        save_categories()

    threads = category.threads  # Get all current threads/posts in the forum

    for thread in threads:
        for user_id in tracking_data:
            if str(thread.id) not in tracking_data[user_id]["tracked_threads"]:
                tracking_data[user_id]["tracked_threads"][str(thread.id)] = {
                    "link": thread.jump_url,
                    "name": thread.name,
                    "last_active_tupper": None,
                    "last_active_time": None
                }

        save_data(tracking_data)
        await interaction.response.send_message(f"✅ **Category `{category.name}` is now being tracked.**", ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ **Category `{category.name}` is already being tracked.**", ephemeral=True)


@client.tree.command(name="activity", description="View character activity for a specific forum category")
@app_commands.describe(
    category="Forum category to view activity for",
    character_filter="Filter by character name (optional)",
    character_owner="Filter by character owner (optional)"
)
async def viewcategoryactivity(
    interaction: discord.Interaction,
    category: discord.ForumChannel,
    character_filter: str = None,
    character_owner: discord.User = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **You must be an administrator to use this command.**", ephemeral=True)
        return

    now = datetime.utcnow()
    character_usage = {}
    any_inactive = False

    for user_id, data in tracking_data.items():
        for thread_id, info in data.get("tracked_threads", {}).items():
            try:
                thread_channel = await interaction.guild.fetch_channel(int(thread_id))
            except:
                continue
            if thread_channel.parent_id != category.id:
                continue

            log = info.get("activity_log", {})
            for char, timestamp in log.items():
                owner = character_owners.get(char)
                alias = character_aliases.get(char, char)

                # Apply filters
                if character_filter and character_filter.lower() not in char.lower():
                    continue
                if character_owner and owner != character_owner.id:
                    continue

                if char not in character_usage or timestamp > character_usage[char]["last_seen"]:
                    character_usage[char] = {
                        "alias": alias,
                        "owner": owner,
                        "last_seen": timestamp,
                        "thread": info["name"]
                    }

    if not character_usage:
        await interaction.response.send_message(f"📭 **No activity found in `{category.name}` with the current filters.**", ephemeral=True)
        return

    # Build embed
    embed_color = 0x2ecc71  # Green by default
    embed = discord.Embed(title=f"📊 Character Activity in `{category.name}`", color=embed_color)

    for char, info in character_usage.items():
        alias = info["alias"]
        owner_id = info["owner"]
        owner = f"<@{owner_id}>" if owner_id else "Unassigned"
        thread = info["thread"]
        last_seen_raw = info["last_seen"]
        last_seen = last_seen_raw.split("T")[0] + " " + last_seen_raw.split("T")[1].split(".")[0]

        # Check for inactivity
        last_seen_time = datetime.fromisoformat(last_seen_raw)
        days_inactive = (now - last_seen_time).days
        warning = " ⚠️" if days_inactive >= 3 else ""
        if days_inactive >= 3:
            any_inactive = True

        embed.add_field(
            name=f"🎭 {alias}",
            value=f"👤 **Owner**: {owner}\n🧵 **Thread**: `{thread}`\n🕰️ **Last Seen**: {last_seen}{warning}",
            inline=False
        )

    if any_inactive:
        embed.color = 0xe74c3c  # Red

    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="inactivity", description="List characters inactive for more than 4 days (Admin Only)")
async def viewinactive(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **You must be an administrator to use this command.**", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    now = datetime.utcnow()
    embed = discord.Embed(title="📋 Inactive Characters (Over 3 Days)", color=0xe74c3c)
    found_any = False

    activity_log = characters_data.get("activity", {})
    for char_name, data in activity_log.items():
        base_name = character_aliases.get(char_name, char_name)
        owner_id = character_owners.get(base_name)
        owner = f"<@{owner_id}>" if owner_id else "Unassigned"

        last_seen_raw = data.get("last_seen")
        if not last_seen_raw:
            continue

        try:
            last_seen_time = datetime.fromisoformat(last_seen_raw)
        except ValueError:
            continue

        days_inactive = (now - last_seen_time).days
        if days_inactive >= 3:
            found_any = True
            last_seen_fmt = last_seen_time.strftime("%Y-%m-%d %H:%M:%S")
            embed.add_field(
                name=f"🎭 {base_name}",
                value=(
                    f"👤 **Owner:** {owner}\n"
                    f"🕰️ **Last Seen:** {last_seen_fmt}\n"
                    f"⏳ **Inactive for:** {days_inactive} days ⚠️"
                ),
                inline=False
            )

    if not found_any:
        embed.description = "✅ No characters have been inactive for more than 3 days."

    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="viewall", description="List all known characters and their activity")
@app_commands.describe(
    character_filter="Filter by character name (optional)",
    character_owner="Filter by owner (optional)"
)
async def viewcharacters(
    interaction: discord.Interaction,
    character_filter: str = None,
    character_owner: discord.User = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    activity = characters_data.get("activity", {})
    if not activity:
        await interaction.response.send_message("📭 No characters found in the database.", ephemeral=True)
        return

    now = datetime.utcnow()
    any_inactive = False
    embed = discord.Embed(title="🎭 Registered Characters", color=0x2ecc71)  # Green by default
    found = False

    for char_name, info in activity.items():
        base_name = character_aliases.get(char_name, char_name)
        alias = base_name
        owner_id = character_owners.get(base_name)
        owner = f"<@{owner_id}>" if owner_id else "Unassigned"

        if character_filter and character_filter.lower() not in char_name.lower():
            continue
        if character_owner and owner_id != character_owner.id:
            continue

        thread = info.get("thread", "Unknown")
        last_seen_raw = info.get("last_seen", "Never")
        last_seen_fmt = (
            last_seen_raw.split("T")[0] + " " + last_seen_raw.split("T")[1].split(".")[0]
            if "T" in last_seen_raw else last_seen_raw
        )

        # ✅ Inactivity logic
        warning = ""
        try:
            last_seen_dt = datetime.fromisoformat(last_seen_raw)
            days_inactive = (now - last_seen_dt).days
            if days_inactive >= 3:
                warning = " ⚠️"
                any_inactive = True
        except:
            pass

        value = f"👤 **Owner**: {owner}\n🧵 **Thread**: `{thread}`\n🕰️ **Last Seen**: {last_seen_fmt}"
        if warning:
            value += f"\n⏳ **Inactive for {days_inactive} days**"

        embed.add_field(
            name=f"🎭 {alias}{warning}",
            value=value,
            inline=False
        )

        found = True

    if not found:
        await interaction.response.send_message("📭 No characters matched the filters.", ephemeral=True)
        return

    if any_inactive:
        embed.color = 0xe74c3c  # Red if anyone is inactive

    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="help", description="List available commands")
async def help_command(interaction: discord.Interaction):
    msg = """📚 **Slash Commands Available:**

`/track [link]` → **Start tracking a thread**
`/untrack [link]` → **Untrack a thread**
`/tracking` → **See all threads you're tracking**
`/help` → **Show this help message**"""
    await interaction.response.send_message(msg, ephemeral=True)

@client.tree.command(name="adminhelp", description="Lists available commands for admins")
async def admin_help_command(interaction: discord.Interaction):
    msg="""**Slash Commands Available:**"

"`/givechar [name] [user]` → **Assign a character to a user (Admin Only)**
`/renamechar [old] [new]` → **Rename a character for display (Admin Only)**
`/trackforum [forum]` → **Track a forum category for admin reports (Admin Only)**
`/viewall` → **List all registered characters and owners (Admin Only)**
`/inactive` → **List inactive characters over 3 days (Admin Only)**
`/activity [forum]` → **View character activity within a specific category (Admin Only)**
`/clearall` → **Will delete all the data (Admin Only)**
`/delchar` → **Will delete all the data relating to one character (Admin Only)**"""
    await interaction.response.send_message(msg, ephemeral=True)

@client.event
async def on_thread_create(thread):
    if thread.parent_id in admin_tracked_categories:
        for user_id in tracking_data:
            tracking_data[user_id]["tracked_threads"][str(thread.id)] = {
                "link": thread.jump_url,
                "name": thread.name,
                "last_active_tupper": None,
                "last_active_time": None
            }
        save_data(tracking_data)

@client.event
async def on_message(message):
    updated_threads = set()
    last_seen_time = datetime.utcnow().isoformat()

    # ✅ 1. Handle DM replies to inactivity warnings
    if not message.guild and not message.author.bot:
        print(f"💬 DM received from {message.author.name}: {message.content}")
        user_id = str(message.author.id)
        for key, data in inactivity_tracker.items():
            if str(data["owner"]) == user_id and not data.get("responded", False):
                inactivity_tracker[key]["responded"] = True
                inactivity_tracker[key]["response"] = message.content
                inactivity_tracker[key]["responded_at"] = datetime.utcnow().isoformat()
                save_inactivity_tracker()

                # ✅ Notify admin channel
                admin_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
                if admin_channel:
                    await admin_channel.send(
                        f"📨 <@{user_id}> responded to inactivity warning for **{data['char']}**:\n"
                        f"> {message.content}"
                    )
                break

    # ✅ 2. Tupperbox/webhook activity in tracked threads
    key = message.author.name if message.webhook_id else None

    if message.webhook_id:
        thread_id = str(message.channel.id)

        for user_id in tracking_data:
            user_threads = tracking_data[user_id].get("tracked_threads", {})

            # 🔄 Auto-track new thread if needed
            if thread_id not in user_threads:
                print(f"📌 Auto-tracking new thread for user {user_id}: {message.channel.name}")
                tracking_data[user_id]["tracked_threads"][thread_id] = {
                    "link": message.channel.jump_url,
                    "name": message.channel.name,
                    "last_active_tupper": None,
                    "last_active_time": None,
                    "activity_log": {}
                }

            # 🕒 Update thread activity
            thread_info = tracking_data[user_id]["tracked_threads"][thread_id]
            if "activity_log" not in thread_info:
                thread_info["activity_log"] = {}

            thread_info["activity_log"][key] = last_seen_time
            thread_info["last_active_tupper"] = key
            thread_info["last_active_time"] = last_seen_time
            updated_threads.add(thread_id)

            print(f"📬 {key} posted in {message.channel.name}")

        # ✅ Update character_data.json
        if "activity" not in characters_data:
            characters_data["activity"] = {}

        characters_data["activity"][key] = {
            "thread": getattr(message.channel, "name", "DM or Unknown"),
            "last_seen": last_seen_time
        }

        if key not in character_owners and key not in registered_characters:
            registered_characters.add(key)

        save_data(tracking_data)
        save_characters()

    # ✅ 3. Detect thread creation in tracked forums
    if message.type == discord.MessageType.thread_created and message.channel.parent_id in admin_tracked_categories:
        if hasattr(message.channel, "name"):
            print(f"🧵 New thread created in tracked category: {message.channel.name}")
        else:
            print("🧵 New thread created in tracked category (no name)")

        for user_id in tracking_data:
            tracking_data[user_id]["tracked_threads"][str(message.channel.id)] = {
                "link": message.channel.jump_url,
                "name": message.channel.name,
                "last_active_tupper": None,
                "last_active_time": None
            }
        save_data(tracking_data)

    # ✅ Always call this last
    await client.process_commands(message)


async def delete_character_by_name(base_name: str):
    names_to_remove = {base_name}

    for alias, target in character_aliases.items():
        if target == base_name:
            names_to_remove.add(alias)

    for name in list(characters_data["activity"].keys()):
        if character_aliases.get(name, name) == base_name:
            names_to_remove.add(name)

    for alias in list(character_aliases.keys()):
        if alias in names_to_remove or character_aliases[alias] == base_name:
            del character_aliases[alias]

    for name in list(characters_data["activity"].keys()):
        if name in names_to_remove:
            del characters_data["activity"][name]

    for user_data in tracking_data.values():
        for thread_info in user_data.get("tracked_threads", {}).values():
            for char in list(thread_info.get("activity_log", {}).keys()):
                if char in names_to_remove:
                    del thread_info["activity_log"][char]
            if thread_info.get("last_active_tupper") in names_to_remove:
                thread_info["last_active_tupper"] = None

    # Remove ownership entry ONLY IF no characters left under that name
    for name in list(character_owners.keys()):
        if name in names_to_remove:
            del character_owners[name]

    save_characters()
    save_data(tracking_data)
    return bool(names_to_remove)



@client.tree.command(name="delchar", description="⚠️ Delete a character or all of a user's characters (Admin Only)")
@app_commands.describe(name_or_owner="Character name or Discord ID/mention", confirm="Type true to confirm deletion")
async def deletecharacter(interaction: discord.Interaction, name_or_owner: str, confirm: bool = False):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    if not confirm:
        await interaction.response.send_message(
            f"⚠️ This will permanently delete either a character or all characters belonging to a user.\n\n"
            f"If you're sure, run again with `confirm: true`.",
            ephemeral=True
        )
        return

    is_user_id = False
    try:
        if name_or_owner.startswith("<@") and name_or_owner.endswith(">"):
            user_id = int(name_or_owner.strip("<@!>"))
            is_user_id = True
        elif name_or_owner.isdigit():
            user_id = int(name_or_owner)
            is_user_id = True
    except:
        pass

    if is_user_id:
        deleted_chars = []
        user_id_str = str(user_id)
        for char_name, owner in list(character_owners.items()):
            if owner == user_id:
                await delete_character_by_name(char_name)
                deleted_chars.append(char_name)

                # Update assigned_count
                if user_id_str in users_data and users_data[user_id_str]["assigned_count"] > 0:
                    users_data[user_id_str]["assigned_count"] -= 1
                    save_users()

        # Remove mun role if count hits 0
        if user_id_str in users_data and users_data[user_id_str]["assigned_count"] == 0:
            mun_role = discord.utils.get(interaction.guild.roles, id=MUN_ROLE_ID)
            member = interaction.guild.get_member(user_id)
            if member and mun_role and mun_role in member.roles:
                await member.remove_roles(mun_role)

        if deleted_chars:
            await interaction.response.send_message(
                f"🧨 Deleted **{len(deleted_chars)}** characters owned by <@{user_id}>:\n" +
                "\n".join(f"• {name}" for name in deleted_chars),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ No characters found owned by <@{user_id}>.",
                ephemeral=True
            )
    else:
        base_name = character_aliases.get(name_or_owner, name_or_owner)
        matched = await delete_character_by_name(base_name)

        if matched:
            owner_id = character_owners.get(base_name)
            user_id_str = str(owner_id)

            # Update assigned_count
            if user_id_str in users_data and users_data[user_id_str]["assigned_count"] > 0:
                users_data[user_id_str]["assigned_count"] -= 1
                save_users()

                if users_data[user_id_str]["assigned_count"] == 0:
                    mun_role = discord.utils.get(interaction.guild.roles, id=MUN_ROLE_ID)
                    member = interaction.guild.get_member(owner_id)
                    if member and mun_role and mun_role in member.roles:
                        await member.remove_roles(mun_role)

            await interaction.response.send_message(f"🗑️ Deleted character: **{base_name}**", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ Character **{base_name}** not found.", ephemeral=True)

ADMIN_CHANNEL_ID = 1356640519249465444
MOD_ROLE_ID = 1356642834484301924


async def check_inactive_characters():
    await client.wait_until_ready()

    while not client.is_closed():
        now = datetime.utcnow()
        threshold = now - timedelta(days=3)

        for char_name, info in characters_data.get("activity", {}).items():
            last_seen_str = info.get("last_seen")
            if not last_seen_str:
                continue

            try:
                last_seen_time = datetime.fromisoformat(last_seen_str)
            except ValueError:
                continue

            if last_seen_time >= threshold:
                continue  # Still active

            base_name = character_aliases.get(char_name, char_name)
            owner_id = character_owners.get(base_name)
            if not owner_id:
                print(f"⚠️ No owner found for {base_name}, skipping...")
                continue

            if base_name in inactivity_tracker:
                print(f"🕒 Already notified about inactivity: {base_name}")
                continue

            days_inactive = (now - last_seen_time).days
            print(f"🚨 {base_name} ({char_name}) inactive for {days_inactive} days.")

            # Admin alert
            admin_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
            if admin_channel:
                await admin_channel.send(
                    f"📣 Messaged <@{owner_id}> about inactivity for **{base_name}** ({days_inactive} days)"
                )

            # DM the user
            try:
                user = await client.fetch_user(owner_id)
                await user.send(
                    f"👋 Hi! Your character **{base_name}** has been inactive for {days_inactive} days.\n"
                    f"Please reply to this message within 24 hours to remain in the roleplay or request a hiatus.\n"
                    f"Your reply will be forwarded to the moderators."
                )

                inactivity_tracker[base_name] = {
                    "notified_at": now.isoformat(),
                    "owner": owner_id,
                    "responded": False
                }

                save_inactivity_tracker()
            except Exception as e:
                print(f"❌ Couldn’t DM <@{owner_id}> ({base_name}): {e}")

        await asyncio.sleep(60)  # run every 60 seconds for testing (increase later)

    
@client.tree.command(name="cleardata", description="⚠️ Clear all tracking and character data (admin only)")
@app_commands.describe(confirm="Type true to confirm deletion")
async def cleardata(interaction: discord.Interaction, confirm: bool = False):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to run this command.", ephemeral=True)
        return

    if not confirm:
        await interaction.response.send_message(
            "⚠️ This will erase all character and thread tracking data.\n\n"
            "If you're sure, run:\n`/cleardata confirm:true`",
            ephemeral=True
        )
        return

    # Clear in-memory structures
    tracking_data.clear()
    character_owners.clear()
    character_aliases.clear()
    registered_characters.clear()
    characters_data.clear()

    # Write empty JSON files
    save_data(tracking_data)
    save_characters()

    await interaction.response.send_message("🧹 All tracking and character data has been cleared.", ephemeral=True)


### USER HANDLING COMMANDS

ADMIN_CHANNEL_ID = 1356640519249465444  # Replace with your mod channel ID
MUN_ROLE_ID = 1354961212290498680       # Replace with actual mun role ID


@client.tree.command(name="accept", description="Accept a new user and start 48h setup timer")
@app_commands.describe(user="User to accept", forum_post="Forum post link to track setup")
async def accept_user(interaction: discord.Interaction, user: discord.Member, forum_post: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an admin to use this command.", ephemeral=True)
        return

    user_id_str = str(user.id)
    now = datetime.utcnow().isoformat()

    # ✅ Give the 'mun' role (even if they already have it)
    mun_role = discord.utils.get(interaction.guild.roles, id=MUN_ROLE_ID)
    if mun_role and mun_role not in user.roles:
        await user.add_roles(mun_role, reason="Accepted as MUN")

    # ✅ Load or initialize user entry
    old_data = users_data.get(user_id_str, {})
    previous_count = old_data.get("assigned_count", 0)
    new_count = previous_count + 1

    # ✅ Find the next available forum_X slot
    forum_index = 1
    while f"forum_{forum_index}" in old_data:
        forum_index += 1

    # ✅ Rebuild the user data entry
    new_entry = {
        "username": user.display_name,
        "accepted_at": now,
        "checked": False,
        "assigned_count": new_count
    }

    for i in range(1, forum_index):
        new_entry[f"forum_{i}"] = old_data[f"forum_{i}"]

    new_entry[f"forum_{forum_index}"] = {
        "link": forum_post,
        "accepted_at": now,
        "checked": False
    }

    users_data[user_id_str] = new_entry
    save_users()

    # ✅ Send DM to user
    try:
        await user.send(
            f"🌟 Hi {user.display_name}! You've been accepted into **CRESTFALL**.\n"
            f"Please complete your character setup within 48 hours here:\n{forum_post}"
        )
    except:
        pass  # Couldn't DM user

    # ✅ Notify admin channel
    admin_channel = client.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        await admin_channel.send(
            f"✅ Accepted <@{user.id}> into CRESTFALL.\nForum link saved as `forum_{forum_index}`.\n{forum_post}"
        )

    # ✅ Confirm back to the admin who used the command
    await interaction.response.send_message(
        f"✅ {user.mention} has been accepted (x{new_count})!\n"
        f"Their forum link was saved as `forum_{forum_index}`, and a 48h timer has started.",
        ephemeral=True
    )


async def check_user_setup_timers():
    await client.wait_until_ready()
    while not client.is_closed():
        now = datetime.utcnow()
        for user_id, info in users_data.items():
            user_id_str = str(user_id)

            for key, forum_data in info.items():
                if not key.startswith("forum_") or not isinstance(forum_data, dict):
                    continue

                if forum_data.get("checked"):
                    continue

                try:
                    accepted_time = datetime.fromisoformat(forum_data["accepted_at"])
                except Exception:
                    continue

                if (now - accepted_time) >= timedelta(hours=48):
                    channel = client.get_channel(ADMIN_CHANNEL_ID)
                    if channel:
                        view = CheckSetupButtons(user_id=user_id, forum_key=key)
                        await channel.send(
                            f"🕵️ **Check Setup for <@{user_id}>**\nForum link: {forum_data['link']}",
                            view=view
                        )
                        forum_data["checked"] = True
                        save_users()
        await asyncio.sleep(3600)

def extract_channel_id(forum_link: str) -> int | None:
    try:
        forum_link = forum_link.strip()
        if forum_link.startswith("<#") and forum_link.endswith(">"):
            return int(forum_link.strip("<#>"))
        elif "discord.com/channels/" in forum_link:
            return int(forum_link.strip("/").split("/")[-1])
        elif forum_link.isdigit():
            return int(forum_link)
    except (ValueError, IndexError):
        return None

ARCHIVE_CATEGORY_ID = 1356732979010863274  # replace with your actual category ID



class CheckSetupButtons(discord.ui.View):
    def __init__(self, user_id, forum_key):
        super().__init__(timeout=None)
        self.user_id = int(user_id)
        self.forum_key = forum_key

    @discord.ui.button(label="✅ Yes — user is active", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"✅ No action taken. User <@{self.user_id}> appears active.", ephemeral=True
        )

    @discord.ui.button(label="❌ No — ask them to reapply", style=discord.ButtonStyle.danger)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = guild.get_member(self.user_id)
        user_id_str = str(self.user_id)

        forum_data = users_data.get(user_id_str, {}).get(self.forum_key, {})
        forum_link = forum_data.get("link", "")
        forum_channel_id = extract_channel_id(forum_link)
        category = None

        # ✅ Move the forum channel to archive instead of deleting
        if forum_channel_id:
            try:
                forum_channel = await guild.fetch_channel(forum_channel_id)
                category = forum_channel.category

                archive_category = discord.utils.get(guild.categories, id=ARCHIVE_CATEGORY_ID)
                if archive_category:
                    await forum_channel.edit(category=archive_category, reason="Moved to archive — user didn't finish setup.")
                    await forum_channel.edit(name=f"archived-{forum_channel.name}")
                else:
                    print("⚠️ Archive category not found.")
            except Exception as e:
                print(f"❌ Failed to archive forum: {e}")

        # ✅ Remove the specific forum entry
        if user_id_str in users_data:
            users_data[user_id_str].pop(self.forum_key, None)

            # 🔻 Decrease character count
            if users_data[user_id_str].get("assigned_count", 0) > 0:
                users_data[user_id_str]["assigned_count"] -= 1

            save_users()

        # ✅ If no more characters, remove role and delete their personal category (if it exists)
        still_has_characters = users_data.get(user_id_str, {}).get("assigned_count", 0) > 0

        if not still_has_characters:
            mun_role = discord.utils.get(guild.roles, id=MUN_ROLE_ID)
            if mun_role and user and mun_role in user.roles:
                await user.remove_roles(mun_role)

            if category:
                try:
                    await category.delete(reason="User has no remaining characters — deleted personal category.")
                except Exception as e:
                    print(f"❌ Failed to delete category: {e}")

        # ✅ DM the user
        if user:
            try:
                await user.send("🚫 Hi! You didn’t set up your character for **CRESTFALL** in time. Please reapply if you're still interested.")
            except:
                pass  # User DMs are closed

        await interaction.response.send_message(
            f"🗑️ <@{self.user_id}> was removed.\n"
            f"{'Category deleted.' if not still_has_characters else 'Forum moved to archive.'}",
            ephemeral=True
        )


# --- All your imports, data loading, and function definitions ---
# e.g. load_characters(), commands, check_inactive_characters()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    if not hasattr(client, "inactivity_task_started"):
        client.loop.create_task(check_inactive_characters())
        client.loop.create_task(check_user_setup_timers())
        client.inactivity_task_started = True

# --- Slash command sync, if any ---
# await client.tree.sync()

# Run the bot
client.run(TOKEN)


