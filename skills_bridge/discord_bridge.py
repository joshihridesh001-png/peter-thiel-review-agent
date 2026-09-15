"""
Discord Bridge integrating with send-to-discord skill conventions and REST API.
Provides high-level async methods for sending embeds, reports, and interacting with Discord channels.
"""

import aiohttp
from typing import Optional, Dict, Any, List, Union
from config import DISCORD_BOT_TOKEN, CHANNELS

BASE_URL = "https://discord.com/api/v10"

# Embed Colors
COLOR_PRIMARY = 0x5865F2  # Blurple
COLOR_SUCCESS = 0x2ECC71  # Green (Praise / High Score)
COLOR_WARNING = 0xF1C40F  # Yellow (Carryover goals / Alert)
COLOR_DANGER = 0xE74C3C   # Red (Bottleneck / Disputed update)
COLOR_EQUITY = 0x9B59B6   # Purple (Monthly Dynamic Earnout)
COLOR_SWOT = 0x3498DB     # Blue (Weekly SWOT)


def resolve_channel(channel_input: Union[str, int]) -> int:
    """Resolve channel alias or string/int ID to numeric channel ID."""
    if isinstance(channel_input, int):
        return channel_input
    if str(channel_input).isdigit():
        return int(channel_input)
    alias = str(channel_input).lower()
    if alias in CHANNELS:
        return CHANNELS[alias]
    raise ValueError(f"Unknown channel identifier: '{channel_input}'. Available: {list(CHANNELS.keys())}")


def build_embed(
    title: str,
    description: str = "",
    color: int = COLOR_PRIMARY,
    fields: Optional[List[Dict[str, Any]]] = None,
    footer: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a standard Discord embed dictionary."""
    embed: Dict[str, Any] = {
        "title": title,
        "description": description,
        "color": color,
    }
    if fields:
        embed["fields"] = fields
    if footer:
        embed["footer"] = {"text": footer}
    return embed


async def send_to_channel(
    channel_input: Union[str, int],
    content: Optional[str] = None,
    embed: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Send message or rich embed to a Discord channel via HTTP REST API."""
    channel_id = resolve_channel(channel_input)
    bot_token = token or DISCORD_BOT_TOKEN
    url = f"{BASE_URL}/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 201):
                err_text = await resp.text()
                raise RuntimeError(f"Discord API Error ({resp.status}): {err_text}")
            return await resp.json()


async def fetch_channel_messages(
    channel_input: Union[str, int],
    limit: int = 50,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch recent messages from a channel."""
    channel_id = resolve_channel(channel_input)
    bot_token = token or DISCORD_BOT_TOKEN
    url = f"{BASE_URL}/channels/{channel_id}/messages?limit={limit}"
    headers = {"Authorization": f"Bot {bot_token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                raise RuntimeError(f"Failed to fetch messages ({resp.status}): {err_text}")
            return await resp.json()
