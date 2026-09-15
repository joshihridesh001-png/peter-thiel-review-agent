"""
Krishna Engineering OS • Founder Operations & Equity Evolution Bot
Main entrypoint initializing intents, database, and Discord cogs.
"""

import asyncio
import logging
import sys
import discord
from discord.ext import commands

from config import DISCORD_BOT_TOKEN
from database.db import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FounderOpsBot")

# Define intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.tracker",
    "cogs.scheduler",
    "cogs.commands",
]


@bot.event
async def on_ready():
    logger.info(f"🚀 Bot connected as {bot.user} (ID: {bot.user.id})")
    # Initialize database
    await init_db()
    logger.info("📦 SQLite database initialized and verified.")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"✨ Synced {len(synced)} application slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")


async def main():
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
