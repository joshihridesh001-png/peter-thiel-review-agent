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


from config import DISCORD_BOT_TOKEN, PRIMARY_GOALS_CHANNEL_ID, TIMEZONE


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

    # Optional startup test message (disabled by default to prevent spam)
    if os.getenv("SEND_STARTUP_MSG", "false").lower() == "true":
        try:
            channel = bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="🟢 Peter Thiel Review Agent Live",
                    description=(
                        "**Status:** 🟢 **Active & Monitoring**\n"
                        "**Timezone:** Asia/Kolkata (IST)\n\n"
                        "*\"Listening to founder channels. 8:00 PM scoring and 9:00 PM commitment locks armed.\"*"
                    ),
                    color=0x2ECC71,
                )
                embed.set_footer(text="Krishna Engineering OS • Active")
                await channel.send(embed=embed)
                logger.info("Sent startup message to Discord.")
        except Exception as e:
            logger.error(f"Failed to send startup test message: {e}")


import os
from datetime import datetime
from aiohttp import web


async def handle_health(request):
    return web.json_response({
        "status": "ok",
        "agent": "Peter Thiel",
        "bot_online": bot.is_ready(),
        "server_time_ist": datetime.now(TIMEZONE).isoformat()
    })


async def run_web_server():
    """Start lightweight HTTP health server on $PORT for Render / cloud keep-alive."""
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/healthz", handle_health)
    app.router.add_get("/health", handle_health)

    port = int(os.getenv("PORT", "10000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Healthcheck web server listening on 0.0.0.0:{port} (/healthz)")


async def main():
    await run_web_server()
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Start bot with backoff retry on Discord 429 rate limit
        while True:
            try:
                await bot.start(DISCORD_BOT_TOKEN)
                break
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    logger.warning("⚠️ Discord 429 rate limit encountered. Waiting 35s before retrying...")
                    await asyncio.sleep(35)
                else:
                    logger.error(f"Discord HTTP Exception ({e.status}): {e}. Waiting 15s...")
                    await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Connection error: {e}. Retrying in 15s...")
                await asyncio.sleep(15)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
