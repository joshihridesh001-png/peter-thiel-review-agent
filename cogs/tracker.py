"""
Discord Cog: Tracker
Monitors channel activity, captures daytime updates, processes 9 PM goal posts, and tracks peer reactions.
"""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
import logging
import re
from typing import Optional, List, Tuple

from config import (
    CHANNELS,
    PRIMARY_GOALS_CHANNEL_ID,
    MONITORED_UPDATE_CHANNELS,
    SYSTEM_EMBED_TITLES,
    FOUNDERS,
    PEER_EMOJIS,
    TIMEZONE,
)
from database.models import (
    get_user_by_discord_id,
    save_daily_goals,
    save_channel_update,
    record_peer_reaction,
    remove_peer_reaction,
    get_all_users,
)
from engine.evaluator import parse_daily_goals_with_ai
from engine.attachment_reader import enrich_discord_message
from skills_bridge.discord_bridge import build_embed, COLOR_SUCCESS, COLOR_PRIMARY

logger = logging.getLogger(__name__)


class TrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _resolve_github_username(self, name: str) -> Optional[str]:
        """Match a GitHub username or alias to one of the founders."""
        if not name:
            return None
        clean = name.lower().strip()
        # Direct match in github_usernames or usernames
        for key, info in FOUNDERS.items():
            for gh in info.get("github_usernames", []):
                if gh.lower() == clean:
                    return key
            for alias in info.get("usernames", []):
                if alias.lower() == clean:
                    return key

        # Substring / fuzzy match
        for key, info in FOUNDERS.items():
            if key in clean:
                return key
            for gh in info.get("github_usernames", []):
                if gh.lower() in clean or clean in gh.lower():
                    return key
            for alias in info.get("usernames", []):
                if len(alias) >= 4 and alias.lower() in clean:
                    return key
        return None

    def _extract_github_updates(self, message: discord.Message) -> List[Tuple[str, str]]:
        """
        Inspect message for GitHub webhook or bot activity.
        Returns a list of (founder_key, formatted_content).
        """
        is_github = (
            "github" in (message.author.name or "").lower()
            or bool(getattr(message, "webhook_id", None))
        )
        if not is_github or not message.embeds:
            return []

        results = []
        for e in message.embeds:
            title = getattr(e, "title", "") or ""
            desc = getattr(e, "description", "") or ""
            url = getattr(e, "url", "") or ""
            author_obj = getattr(e, "author", None)
            author_name = (getattr(author_obj, "name", "") or "").strip()

            # Filter CI/CD noise
            author_lower = author_name.lower()
            if any(b in author_lower for b in ("vercel", "dependabot", "github-actions", "[bot]")):
                continue
            if any(n in title.lower() for n in ("unresolved feedback", "vercel checks success", "api failure")):
                continue

            founder_key = None
            if author_name:
                founder_key = self._resolve_github_username(author_name)

            if not founder_key:
                # Check title or desc for author attribution (e.g. "- joshihridesh001-png")
                words = re.findall(r'[\w\-]+', f"{title} {desc}")
                for w in words:
                    matched = self._resolve_github_username(w)
                    if matched:
                        founder_key = matched
                        if not author_name:
                            author_name = w
                        break

            if not founder_key:
                continue

            # Tag the update appropriately
            title_lower = title.lower()
            if "/pull/" in url or "pull request" in title_lower:
                tag = "GitHub PR"
            elif "/commit/" in url or "commit" in title_lower:
                tag = "GitHub Commit"
            elif "branch" in title_lower:
                tag = "GitHub Branch"
            else:
                tag = "GitHub Update"

            lines = [f"[{tag}: {title}]"]
            if author_name:
                lines.append(f"Author: {author_name}")
            if url:
                lines.append(f"URL: {url}")
            if desc:
                lines.append(f"Summary of work:\n{desc}")

            results.append((founder_key, "\n".join(lines)))

        return results

    def _resolve_founder_key(self, author_id: int, author_name: str, is_bot: bool = False) -> Optional[str]:
        """Match author to one of the 3 founders (Hridesh, Swarit, Rahul), including assistant bots."""
        lower_name = author_name.lower().strip()

        # 1. Bot messages attribution
        if is_bot:
            # Peter Thiel bot is Hridesh's personal assistant dropping sales & ops updates
            if "peter thiel" in lower_name or "ceo" in lower_name or (self.bot.user and author_id == self.bot.user.id):
                return "hridesh"
            if "rahul" in lower_name or "coo" in lower_name:
                return "rahul"
            if "swarit" in lower_name or "cto" in lower_name:
                return "swarit"

        # 2. Direct Discord ID match
        for key, info in FOUNDERS.items():
            if author_id == info.get("discord_id"):
                return key

        # 3. Known username / alias match
        for key, info in FOUNDERS.items():
            for alias in info.get("usernames", []):
                if alias.lower() in lower_name:
                    return key

        # 4. Key substring match
        for key in FOUNDERS.keys():
            if key in lower_name:
                return key

        return None

    async def sync_recent_channel_updates(self, limit: int = 100) -> int:
        """
        Scan monitored channels for any recent updates (including GitHub PRs/commits)
        that were missed and backfill them into the database.
        """
        synced_count = 0
        now = datetime.now(TIMEZONE)
        for channel_id in MONITORED_UPDATE_CHANNELS:
            channel = self.bot.get_channel(channel_id)
            if not channel or not hasattr(channel, "history"):
                continue
            try:
                async for message in channel.history(limit=limit):
                    # Check GitHub updates
                    gh_updates = self._extract_github_updates(message)
                    if gh_updates:
                        for idx, (f_key, gh_content) in enumerate(gh_updates):
                            effective_mid = message.id if idx == 0 else (message.id * 100 + idx)
                            author_id = FOUNDERS[f_key].get("discord_id", message.author.id)
                            msg_time = message.created_at.astimezone(TIMEZONE).isoformat() if hasattr(message.created_at, "astimezone") else now.isoformat()
                            saved_id = await save_channel_update(
                                message_id=effective_mid,
                                founder_key=f_key,
                                discord_user_id=author_id,
                                channel_id=channel_id,
                                content=gh_content,
                                timestamp=msg_time,
                            )
                            if saved_id:
                                synced_count += 1
                                logger.info(f"Backfilled GitHub update for {f_key}: {gh_content[:50]}...")
                    else:
                        # Check normal human/bot updates
                        f_key = self._resolve_founder_key(message.author.id, message.author.name, is_bot=message.author.bot)
                        if f_key and not message.author.bot:
                            content = await enrich_discord_message(message, self.bot)
                            if content.strip() and channel_id != PRIMARY_GOALS_CHANNEL_ID:
                                msg_time = message.created_at.astimezone(TIMEZONE).isoformat() if hasattr(message.created_at, "astimezone") else now.isoformat()
                                saved_id = await save_channel_update(
                                    message_id=message.id,
                                    founder_key=f_key,
                                    discord_user_id=message.author.id,
                                    channel_id=channel_id,
                                    content=content,
                                    timestamp=msg_time,
                                )
                                if saved_id:
                                    synced_count += 1
            except Exception as e:
                logger.warning(f"Failed to sync history for channel {channel_id}: {e}")
        return synced_count

    @commands.Cog.listener()
    async def on_ready(self):
        """On bot ready, run channel history sync to backfill any offline updates."""
        logger.info("Running initial channel history synchronization...")
        count = await self.sync_recent_channel_updates(limit=100)
        logger.info(f"Initial sync complete: backfilled {count} updates.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Intercept messages to capture nightly goals, GitHub PRs/commits, or daytime updates."""
        # 1. Ignore automated bot embeds generated by the review system itself
        for e in message.embeds:
            title = e.title or ""
            if any(ignored in title for ignored in SYSTEM_EMBED_TITLES):
                return

        channel_id = message.channel.id
        now = datetime.now(TIMEZONE)

        # 2. Check for GitHub webhook updates (PRs, commits, branches)
        gh_updates = self._extract_github_updates(message)
        if gh_updates and channel_id in MONITORED_UPDATE_CHANNELS:
            for idx, (f_key, gh_content) in enumerate(gh_updates):
                effective_mid = message.id if idx == 0 else (message.id * 100 + idx)
                author_id = FOUNDERS[f_key].get("discord_id", message.author.id)
                msg_time = message.created_at.astimezone(TIMEZONE).isoformat() if hasattr(message.created_at, "astimezone") else now.isoformat()
                await save_channel_update(
                    message_id=effective_mid,
                    founder_key=f_key,
                    discord_user_id=author_id,
                    channel_id=channel_id,
                    content=gh_content,
                    timestamp=msg_time,
                )
                logger.info(f"Logged GitHub update for {f_key} ({author_id}) in channel {channel_id}: {gh_content[:60]}...")
            return

        # 3. Resolve founder (including assistant bots)
        founder_key = self._resolve_founder_key(
            message.author.id,
            message.author.name,
            is_bot=message.author.bot
        )

        if not founder_key:
            return

        content = await enrich_discord_message(message, self.bot)

        if not content.strip():
            return

        # Ignore bot's own posts in primary goals channel (prevents feedback loops on scorecards and lock embeds)
        if channel_id == PRIMARY_GOALS_CHANNEL_ID and message.author.bot:
            return

        # Goals can ONLY be declared by human founders, never by automated bots
        is_human = not message.author.bot
        is_goals_channel = channel_id == PRIMARY_GOALS_CHANNEL_ID
        is_explicit_goal = content.lower().startswith(("goal", "tomorrow", "!goal", "/goal", "targets", "commitment", "commitments", "today"))
        is_numbered_list = content.strip().startswith(("1.", "1)", "1 -", "- ", "* ", "• "))
        is_nighttime = now.hour >= 20 or now.hour <= 4

        # In primary goals channel, numbered lists, explicit keywords, or multi-line nighttime messages lock commitments
        is_goal_declaration = is_human and (
            is_explicit_goal
            or (is_goals_channel and (
                is_numbered_list
                or (is_nighttime and not content.startswith("<@") and len(content.splitlines()) >= 2)
            ))
        )

        if is_goal_declaration:
            # If posted in evening/night (after 5 PM), it's tomorrow's goals. If daytime (before 5 PM), it's today's goals.
            target_date = (now + timedelta(days=1) if now.hour >= 17 else now).strftime("%Y-%m-%d")

            # Parse with Gemini AI
            parsed_tasks = await parse_daily_goals_with_ai(founder_key, content)
            await save_daily_goals(founder_key, target_date, content, parsed_tasks)

            # Confirm with a neat reaction and verification message
            try:
                await message.add_reaction("🔒")
            except Exception:
                pass

            task_blocks = []
            for i, t in enumerate(parsed_tasks, start=1):
                task_title = t.get("task", "Commitment")
                size = t.get("complexity", 3)
                reason = t.get("score_reason", t.get("dharma_reason", "Important task for your role"))
                block = f"**{i}. {task_title}**\n↳ **Size:** `{size}/5`\n💬 *Why: {reason}*"
                task_blocks.append(block)

            tasks_text = "\n\n".join(task_blocks)
            desc = (
                f"Goals for: **{target_date}** • **{len(parsed_tasks)} Commitments Locked**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{tasks_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

            embed = discord.Embed(
                title=f"🔒 Plan Saved • {FOUNDERS[founder_key]['display_name']} ({FOUNDERS[founder_key]['role']})",
                description=desc,
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Peter Thiel Review Bot • Scored tomorrow at 8:00 PM")
            await message.reply(embed=embed, mention_author=False)
            return

        # Check if message is in any monitored update channels
        if channel_id in MONITORED_UPDATE_CHANNELS:
            await save_channel_update(
                message_id=message.id,
                founder_key=founder_key,
                discord_user_id=message.author.id,
                channel_id=channel_id,
                content=content,
                timestamp=now.isoformat(),
            )
            logger.info(f"Logged update from {founder_key} in channel {channel_id}: {content[:40]}...")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Track peer emoji reactions (✅, 🔥, ⚠️) on updates."""
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        if emoji_str not in PEER_EMOJIS:
            return

        # Check reactor identity
        user = await get_user_by_discord_id(payload.user_id)
        reactor_key = user["founder_key"] if user else "peer"

        weight = PEER_EMOJIS[emoji_str]
        await record_peer_reaction(
            message_id=payload.message_id,
            reactor_discord_id=payload.user_id,
            reactor_founder_key=reactor_key,
            emoji=emoji_str,
            weight=weight,
        )
        logger.info(f"Recorded reaction {emoji_str} by {reactor_key} on message {payload.message_id}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle removed reactions."""
        emoji_str = str(payload.emoji.name)
        if emoji_str in PEER_EMOJIS:
            await remove_peer_reaction(payload.message_id, payload.user_id, emoji_str)


async def setup(bot: commands.Bot):
    await bot.add_cog(TrackerCog(bot))
