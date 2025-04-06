# admin.py
import json
import discord

from discord import app_commands, Embed
from datetime import datetime, timezone, timedelta
from utils_helper import save_json, load_json, resolve_user_display_name, get_forum_channel_from_link

from discord_client import client  # Make sure this import is present for client
from config import MUN_ROLE_ID, ADMIN_ALERT_CHANNEL_ID, CHARACTER_FILE, ARCHIVE_CATEGORY_ID # Ensure MUN_ROLE_ID is imported from config
from storage import (
    tracking_data,
    save_data,
    save_categories,
    admin_tracked_categories,
    character_owners,
    character_aliases,
    characters_data,
    registered_characters,
    save_characters,
    users_data,
    save_users,
    inactivity_tracker,
    delete_character_by_name,
    get_character_owner, 
    remove_character, 
    still_has_characters
)


from storage import load_users, save_users
async def hiatus_logic(interaction: discord.Interaction, user: discord.User, days: int):
    users = load_users()
    uid = str(user.id)
    until = datetime.now(timezone.utc) + timedelta(days=days)

    if uid not in users:
        await interaction.response.send_message("❌ This user is not registered.", ephemeral=True)
        return

    users[uid]["hiatus_until"] = until.isoformat()
    users_data.update(users)
    save_users() 

    await interaction.response.send_message(
        f"✅ {user.mention} is now on hiatus until `{until.strftime('%Y-%m-%d %H:%M UTC')}`.",
        ephemeral=True
    )

async def trackforum_logic(interaction: discord.Interaction, category: discord.ForumChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return
    # Logic for tracking the forum category
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

async def cleardata_logic(interaction: discord.Interaction, confirm: bool):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return
    if not confirm:
        await interaction.response.send_message("⚠️ This will erase all data. Run `/cleardata confirm:true` to confirm.", ephemeral=True)
        return
    # Logic for clearing data
    tracking_data.clear()
    character_owners.clear()
    character_aliases.clear()
    registered_characters.clear()
    characters_data.clear()

    # Write empty JSON files
    save_data(tracking_data)
    save_characters()

    await interaction.response.send_message("🧹 All data has been cleared.", ephemeral=True)

# Add consistent logic for tracking and notifications
async def givechar_logic(interaction: discord.Interaction, character: str, user: discord.Member):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ You don’t have permission to assign characters.", ephemeral=True)
        return

    from storage import users_data, save_users
    from utils_helper import give_mun_role
    from config import MUN_ROLE_ID
    from state import characters_data
    from storage import save_characters

    user_id_str = str(user.id)

    # ✅ Nombre original como lo usa Tupperbox
    original = character.strip()
    alias = original.lower().split()[0]

    characters_data.setdefault("owners", {})
    characters_data.setdefault("aliases", {})

    # ✅ Guardar owner y alias correctamente
    characters_data["owners"][original] = user.id
    if original not in characters_data["aliases"]:
        characters_data["aliases"][original] = alias

    # ✅ Solo crear entrada nueva en users_data si no existe
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            "assigned_count": 1,
            "warnings": 0
        }

    save_characters()
    save_users()

    mun_role = discord.utils.get(interaction.guild.roles, id=MUN_ROLE_ID)
    if mun_role and mun_role not in user.roles:
        await give_mun_role(user)

    await interaction.response.send_message(
        f"✅ **Assigned `{original}` to {user.mention}**.\n"
        f"🧮 They now have `{users_data[user_id_str]['assigned_count']}` assigned character(s).",
        ephemeral=True
    )


# Add debug prints to verify function execution
async def renamechar_logic(interaction: discord.Interaction, old_name: str, new_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return

    # Asignar el nuevo alias en ambos diccionarios
    character_aliases[old_name] = new_name
    characters_data["aliases"][old_name] = new_name  # <-- esto es lo que se guarda en el JSON

    save_characters()  # ¡Asegúrate de guardar los cambios!

    await interaction.response.send_message(
        f"✅ Character `{old_name}` has been renamed to `{new_name}` (alias updated).", ephemeral=True
    )



async def archive_forum_of_character(base_name):
    from storage import users_data, character_aliases, character_owners, save_users

    user_id = character_owners.get(base_name)
    if not user_id:
        print(f"❌ No owner found for character: {base_name}")
        return

    user_id_str = str(user_id)
    alias = base_name
    for original, aliased in character_aliases.items():
        if aliased == base_name:
            alias = original
            break

    if user_id_str not in users_data:
        print(f"❌ No user entry found for user {user_id}")
        return

    guild = client.guilds[0]  # Assumes bot is only in one server
    archive_category = guild.get_channel(ARCHIVE_CATEGORY_ID)
    user = guild.get_member(user_id)

    to_delete = None
    for forum_key, forum_data in users_data[user_id_str].items():
        if not forum_key.startswith("forum_"):
            continue

        link = forum_data.get("link", "")
        if alias in link:
            forum_channel = await get_forum_channel_from_link(user_id, forum_key, guild, users_data)
            if forum_channel and archive_category:
                await forum_channel.edit(
                    category=archive_category,
                    name=f"archived-{forum_channel.name}"
                )
                print(f"📦 Archived forum {forum_channel.name}")
            to_delete = forum_key
            break

    if to_delete:
        del users_data[user_id_str][to_delete]
        users_data[user_id_str]["assigned_count"] -= 1

        # If no forums left, remove mun role
        if users_data[user_id_str]["assigned_count"] <= 0:
            mun_role = guild.get_role(MUN_ROLE_ID)
            if mun_role and user:
                await user.remove_roles(mun_role, reason="No characters remaining")

        save_users()

# Add debug prints to verify function execution
async def delchar_logic(interaction: discord.Interaction, input_name: str, guild: discord.Guild, confirm: bool):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
        return
    if not confirm:
        return "⚠️ You must confirm the deletion by setting `confirm=True`."

    from state import characters_data
    from storage import save_characters, users_data, save_users
    from config import ARCHIVE_CATEGORY_ID, MUN_ROLE_ID
    from utils_helper import get_forum_channel_from_link
    import discord.utils

    print(f"🔍 Starting deletion for character input: {input_name}")

    aliases = characters_data.get("aliases", {})
    owners = characters_data.get("owners", {})
    activity = characters_data.get("activity", {})

    full_name = None
    if input_name in owners:
        full_name = input_name
    else:
        for char, alias in aliases.items():
            if alias.lower() == input_name.lower():
                full_name = char
                break

    if not full_name:
        print(f"❌ Could not resolve full name from input `{input_name}`")
        return f"❌ No character or alias found matching `{input_name}`."

    print(f"✅ Resolved full name: {full_name}")

    alias = aliases.get(full_name, full_name.lower().split()[0])
    print(f"🔗 Using alias: {alias}")

    owner_id = owners.get(full_name)
    user_id_str = str(owner_id) if owner_id else None
    forum_archived = False
    forum_channel = None  # Necesario más abajo para intentar borrar categoría

    if user_id_str and user_id_str in users_data:
        print(f"📁 Found user data for owner ID: {user_id_str}")
        for forum_key, forum_data in users_data[user_id_str].items():
            if not forum_key.startswith("forum_"):
                continue

            link = forum_data.get("link", "")
            print(f"🔗 Checking forum link `{link}` from key `{forum_key}`")

            forum_channel = await get_forum_channel_from_link(owner_id, forum_key, guild, users_data)
            if not forum_channel:
                print(f"⚠️ Could not resolve forum channel from link: {link}")
                continue

            print(f"📛 Forum name resolved: {forum_channel.name} ({type(forum_channel)})")

            if alias.lower() in forum_channel.name.lower():
                print(f"🎯 Match found for alias `{alias}` in channel name")

                archive_category = guild.get_channel(ARCHIVE_CATEGORY_ID)
                print(f"🏷️ archive_category: {archive_category} (type: {type(archive_category)})")

                try:
                    kwargs = {
                        "name": f"archived-{forum_channel.name}"
                    }

                    if isinstance(forum_channel, discord.Thread):
                        kwargs["archived"] = True
                        kwargs["locked"] = True
                    elif archive_category:
                        kwargs["category"] = archive_category

                    await forum_channel.edit(**kwargs)
                    print(f"✅ Forum edited with: {kwargs}")

                except discord.HTTPException as e:
                    if e.status == 429:
                        print("⛔ Rate limited! Wait and try again.")
                        return "⚠️ Rate limited by Discord. Please wait a bit and try again."
                    else:
                        print(f"❌ Discord API error during forum edit: {e}")
                        return f"❌ Error while editing the forum: {e}"

                del users_data[user_id_str][forum_key]
                users_data[user_id_str]["assigned_count"] -= 1
                print(f"🧮 Updated assigned_count: {users_data[user_id_str]['assigned_count']}")

                forum_archived = True
                break
            else:
                print(f"🚫 Alias `{alias}` not found in channel name `{forum_channel.name}`")
    else:
        print(f"❌ No users_data entry found for owner ID: {user_id_str}")

    # Fallback: reduce assigned_count even if forum wasn't archived
    if not forum_archived and user_id_str in users_data and users_data[user_id_str].get("assigned_count", 0) > 0:
        users_data[user_id_str]["assigned_count"] -= 1
        print(f"🧮 Fallback: Reduced assigned_count to {users_data[user_id_str]['assigned_count']}")

    # Si assigned_count es 0, quitar rol y borrar categoría si aplica
    if user_id_str in users_data and users_data[user_id_str]["assigned_count"] <= 0:
        user = guild.get_member(owner_id)
        mun_role = guild.get_role(MUN_ROLE_ID)
        if mun_role and user:
            await user.remove_roles(mun_role, reason="No characters remaining")
            print(f"🚫 Removed MUN role from {user.display_name}")

        if forum_channel:
            parent_category = forum_channel.category
            archive_category = guild.get_channel(ARCHIVE_CATEGORY_ID)
            if parent_category and parent_category != archive_category:
                try:
                    await parent_category.delete()
                    print(f"🗑️ Deleted empty parent category: {parent_category.name}")
                except Exception as e:
                    print(f"⚠️ Could not delete category: {e}")

    save_users()

    # Borrar del character_data
    owners.pop(full_name, None)
    aliases.pop(full_name, None)
    activity.pop(full_name, None)
    print(f"🧼 Removed `{full_name}` from character data")
    save_characters()

    if forum_archived:
        return f"🗑️ Character `{full_name}` deleted and forum archived successfully."
    else:
        return f"🗑️ Character `{full_name}` deleted, but no matching forum was archived."

async def give_mun_role(user):
    guild = user.guild
    mun_role = discord.utils.get(guild.roles, id=MUN_ROLE_ID)
    if mun_role and mun_role not in user.roles:
        await user.add_roles(mun_role, reason="Accepted as MUN")

async def accept_logic(interaction: discord.Interaction, user: discord.Member, forum_post: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an admin to use this command.", ephemeral=True)
        return

    if not user:
        await interaction.response.send_message("❌ **User not found.**", ephemeral=True)
        return

    user_id_str = str(user.id)
    now = datetime.utcnow().isoformat()

    # ✅ Give the 'mun' role
    await give_mun_role(user)

    # ✅ Load or initialize user entry
    old_data = users_data.get(user_id_str, {})
    previous_count = old_data.get("assigned_count", 0)
    new_count = previous_count + 1

    # ✅ Initialize warnings if not present
    if "warnings" not in old_data:
        old_data["warnings"] = 0

    # ✅ Find the next available forum_X slot
    forum_index = 1
    while f"forum_{forum_index}" in old_data:
        forum_index += 1

    # ✅ Rebuild user entry
    new_entry = {
        "username": user.display_name,
        "accepted_at": now,
        "checked": False,
        "assigned_count": new_count,
        "warnings": old_data["warnings"]
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

    # ✅ DM user
    try:
        await user.send(
            f"🌟 Hi {user.display_name}! You've been accepted into **CRESTFALL**.\n"
            f"Please complete your character setup within 48 hours here:\n{forum_post}"
        )
    except:
        pass  # DMs closed

    # ✅ Notify admin channel
    admin_channel = client.get_channel(ADMIN_ALERT_CHANNEL_ID)
    if admin_channel:
        await admin_channel.send(
            f"✅ Accepted <@{user.id}> into CRESTFALL.\nForum link saved as `forum_{forum_index}`.\n{forum_post}"
        )

    # ✅ Confirm to admin
    await interaction.response.send_message(
        f"✅ {user.mention} has been accepted (x{new_count})!\n"
        f"Their forum link was saved as `forum_{forum_index}`, and a 48h timer has started.",
        ephemeral=True
    )

@client.tree.command(name="trackforum", description="Add a forum category to be tracked for admin reports")
@app_commands.describe(category="Select a forum channel to track")
async def trackforum(interaction: discord.Interaction, category: discord.ForumChannel):
    await trackforum_logic(interaction, category)

@client.tree.command(name="inactivity", description="List characters inactive for more than 3 days (Admin Only)")
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
                value=(f"👤 **Owner:** {owner}\n"
                       f"🕰️ **Last Seen:** {last_seen_fmt}\n"
                       f"⏳ **Inactive for:** {days_inactive} days ⚠️"),
                inline=False
            )

    if not found_any:
        embed.description = "✅ No characters have been inactive for more than 3 days."

    await interaction.followup.send(embed=embed, ephemeral=True)

# Define your addcategory function
async def addcategory(interaction, category):
    # Logic to add the category
    save_data(tracking_data)

@client.tree.command(name="cleardata", description="⚠️ Clear all tracking and character data (admin only)")
@app_commands.describe(confirm="Type true to confirm deletion")
async def cleardata(interaction: discord.Interaction, confirm: bool = False):
    await cleardata_logic(interaction, confirm)

async def givechar_logic(interaction: discord.Interaction, character: str, user: discord.Member):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ You don’t have permission to assign characters.", ephemeral=True)
        return

    from storage import users_data, save_users
    from utils_helper import give_mun_role
    from config import MUN_ROLE_ID
    from state import characters_data
    from storage import save_characters

    user_id_str = str(user.id)
    input_name = character.strip()
    aliases = characters_data.get("aliases", {})
    owners = characters_data.setdefault("owners", {})

    # ✅ Buscar si input_name es un alias de algún personaje
    matching_char = None
    for original_name, alias in aliases.items():
        if alias.lower() == input_name.lower():
            matching_char = original_name
            break

    # Si no se encontró, usar input tal cual y generar alias
    if not matching_char:
        matching_char = input_name
        if matching_char not in aliases:
            aliases[matching_char] = matching_char.lower().split()[0]

    # ✅ Asignar el owner al personaje correspondiente
    owners[matching_char] = user.id

    # ✅ Si el usuario no estaba en users_data (ej. no se usó /accept)
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            "assigned_count": 1,
            "warnings": 0
        }

    # Guardar cambios
    save_characters()
    save_users()

    # ✅ Dar rol MUN si no lo tiene
    mun_role = discord.utils.get(interaction.guild.roles, id=MUN_ROLE_ID)
    if mun_role and mun_role not in user.roles:
        await give_mun_role(user)

    await interaction.response.send_message(
        f"✅ **Assigned `{matching_char}` to {user.mention}**.",
        ephemeral=True
    )
        


async def viewall_command(interaction, filter=None):
    await interaction.response.defer()  # 👈 no ephemeral
     # 🔄 Auto-reload character data
    new_data = load_json(CHARACTER_FILE, {})
    if new_data:
        characters_data.clear()
        characters_data.update(new_data)
    now = datetime.now(timezone.utc)
    embed = Embed(title="📋 All Registered Characters", color=0x3498db)

    category_names = {}  # Carga los nombres de las categorías
    try:
        import discord
        for guild in interaction.client.guilds:
            for category in guild.channels:
                if isinstance(category, discord.ForumChannel):
                    category_names[str(category.id)] = category.name
    except:
        pass

    # Unir todos los personajes posibles
    all_chars = set(
        list(characters_data.get("activity", {}).keys())
        + list(characters_data.get("owners", {}).keys())
        + list(characters_data.get("aliases", {}).keys())
    )

    for tupper_name in sorted(all_chars):
        alias = characters_data.get("aliases", {}).get(tupper_name)
        base_name = alias if alias else tupper_name
        owner_id = characters_data.get("owners", {}).get(tupper_name)
        owner = f"<@{owner_id}>" if owner_id else "Unassigned"
        data = characters_data.get("activity", {}).get(tupper_name, {})

        # Filtro
        if filter:
            lower = filter.lower()
            mention_id = None
            if filter.startswith("<@") and filter.endswith(">"):
                mention_id = filter.replace("<@", "").replace(">", "").replace("!", "")

            if lower not in tupper_name.lower() and (alias and lower not in alias.lower()) and (str(owner_id) != lower and str(owner_id) != mention_id):
                continue

        last_seen = data.get("last_seen", "No activity")
        activity_summary = ""

        weekly = data.get("weekly_activity", {})
        for category_id, count in weekly.items():
            category_label = category_names.get(str(category_id), f"Category {category_id}")
            activity_summary += f"\n⁠{category_label}: {count} msg(s)"

        if not activity_summary:
            activity_summary = "No posts yet."

        warn = ""
        if last_seen != "No activity":
            try:
                last_seen_dt = datetime.fromisoformat(last_seen)
                days_inactive = (now - last_seen_dt).days
                if days_inactive >= 3:
                    warn = f"\n⚠️ Inactive for {days_inactive} days"
            except:
                pass

        embed.add_field(
            name=f"🎭 {base_name} (aka {tupper_name})" if alias else f"🎭 {tupper_name}",
            value=f"👤 **Owner:** {owner}\n🕰️ **Last seen:** {last_seen}\n📊 **Activity:** {activity_summary}{warn}",
            inline=False
        )


    await interaction.followup.send(embed=embed)


@client.tree.command(name="renamechar", description="Rename a character (Admin Only)")
@app_commands.describe(old_name="Current character name", new_name="New character name")
async def renamechar(interaction: discord.Interaction, old_name: str, new_name: str):
    await renamechar_logic(interaction, old_name, new_name)


@client.tree.command(name="accept", description="Accept a new user and start 48h setup timer")
@app_commands.describe(user="User to accept", forum_post="Forum post link")
async def accept_command(interaction: discord.Interaction, user: discord.Member, forum_post: str):
    await accept_logic(interaction, user, forum_post)

@client.tree.command(name="adminhelp", description="Lists available commands for admins")
async def admin_help_command(interaction: discord.Interaction):
    msg = """**Slash Commands Available:**
    `/givechar [name] [user]` → **Assign a character to a user (Admin Only)**
    `/renamechar [old] [new]` → **Rename a character for display (Admin Only)**
    `/trackforum [forum]` → **Track a forum category for admin reports (Admin Only)**
    `/viewall` → **List all registered characters and owners (Admin Only)**
    `/inactive` → **List inactive characters over 3 days (Admin Only)**
    `/activity [forum]` → **View character activity within a specific category (Admin Only)**
    `/clearall` → **Will delete all the data (Admin Only)**
    `/delchar` → **Will delete all the data relating to one character (Admin Only)**"""
    await interaction.response.send_message(msg, ephemeral=True)

async def warn_and_archive_user(user_id):
    # Send a warning to the user
    user = await client.fetch_user(user_id)
    await user.send("⚠️ You have not responded within the required time. Your data is now archived.")
    
    # Archive user data (implement the actual logic to archive the data, e.g., moving threads to an archive category)
    # Example of notifying admin about this
    admin_channel = await client.fetch_channel(ADMIN_ALERT_CHANNEL_ID)  # Assuming you have an admin channel
    if admin_channel:
        await admin_channel.send(f"User {user_id} has exceeded the 48-hour limit and their data is archived.")

    # Additional archiving logic, like moving threads or saving the user data to another JSON file
    # Save the updated user data (optional)
    if user_id in users_data:
        users_data[user_id]["archived"] = True  # Or whatever field you want to track
        save_users()  # Ensure you save the updated data


