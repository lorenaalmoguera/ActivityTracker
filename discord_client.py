import discord
from discord.ext import commands

intents = discord.Intents.all()

client = commands.Bot(command_prefix="!", intents=intents)  # This creates the bot client

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
