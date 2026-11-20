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
    discord_ids_for,
)
from database.models import (
    get_user_by_discord_id,
    save_daily_goals,
    save_channel_update,
    upsert_channel_update,
    record_peer_reaction,
    remove_peer_reaction,
    get_all_users,
)
from engine.evaluator import parse_daily_goals_with_ai
from engine.attachment_reader import enrich_discord_message
from engine.impact import has_finished_verb, reports_finished_work
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

    def _resolve_founder_key(
        self,
        author_id: int,
        author_name: str,
        display_name: str = "",
        is_bot: bool = False,
        global_name: str = "",
        nick: str = "",
    ) -> Optional[str]:
        """Match an author to a team member, including assistant bots.

        A server nick must not hide the account. Username, global name,
        nick, and display name are all checked. yy4sh is Yash.
        """
        seen = set()
        parts = []
        for part in (author_name, global_name, display_name, nick):
            text = str(part or "").strip().lower()
            if text and text not in seen:
                seen.add(text)
                parts.append(text)
        names = " ".join(parts)

        # 1. A known Discord account wins over any name guess. This includes
        #    second accounts and Rahul's assistant bot.
        if author_id:
            for key in FOUNDERS:
                if author_id in discord_ids_for(key):
                    return key

        # 2. Other bots, matched by name
        if is_bot:
            # Peter Thiel bot is Hridesh's personal assistant dropping sales & ops updates
            bot_user = self.bot.user if self.bot is not None else None
            if "peter thiel" in names or "ceo" in names or (bot_user and author_id == bot_user.id):
                return "hridesh"
            if "rahul" in names or "coo" in names:
                return "rahul"
            if "swarit" in names or "cto" in names:
                return "swarit"
            if "shivang" in names:
                return "shivang"
            if "yash" in names:
                return "yash"

        # 3. Known username / alias match against the handle and the display name
        for key, info in FOUNDERS.items():
            for alias in info.get("usernames", []):
                if alias and alias.lower() in names:
                    return key

        # 4. Key substring match
        for key in FOUNDERS.keys():
            if key in names:
                return key

        return None

    def _logged_channel_id(self, channel) -> Optional[int]:
        """Parent channel when the message is in a thread under a watched channel."""
        channel_id = getattr(channel, "id", None)
        parent_id = getattr(channel, "parent_id", None)
        if channel_id in MONITORED_UPDATE_CHANNELS:
            return channel_id
        if parent_id in MONITORED_UPDATE_CHANNELS:
            return parent_id
        return None

    def _child_threads(self, channel) -> List:
        raw = getattr(channel, "threads", None)
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return []

    async def _archived_threads(self, channel):
        """Old threads on a real Discord channel. Test doubles are skipped."""
        if channel.__class__.__module__.split(".")[0] != "discord":
            return
        method = getattr(channel, "archived_threads", None)
        if not callable(method):
            return
        try:
            async for thread in method(limit=25):
                yield thread
        except Exception as exc:
            logger.warning("Could not list old threads in %s: %s", getattr(channel, "id", "?"), exc)

    async def _iter_history(self, channel, *, limit: int = 100, after=None, cap: Optional[int] = None):
        """Walk history newest-first, then older pages, until the cap or the start."""
        method = getattr(channel, "history", None)
        if not callable(method):
            return
        remaining = cap if cap is not None else limit
        before = None
        while remaining > 0:
            page = min(100, remaining)
            kwargs = {"limit": page}
            if after is not None:
                kwargs["after"] = after
            if before is not None:
                kwargs["before"] = before
            try:
                iterator = method(**kwargs)
            except TypeError:
                if before is not None or after is not None:
                    return
                iterator = method(limit=page)
            batch = []
            async for message in iterator:
                batch.append(message)
            if not batch:
                return
            for message in batch:
                yield message
            remaining -= len(batch)
            if len(batch) < page:
                return
            before = batch[-1]
            created = getattr(batch[-1], "created_at", None)
            if after is not None and created is not None and created <= after:
                return

    def _author_kwargs(self, author) -> dict:
        return {
            "display_name": getattr(author, "display_name", None) or "",
            "global_name": getattr(author, "global_name", None) or "",
            "nick": getattr(author, "nick", None) or "",
            "is_bot": bool(getattr(author, "bot", False)),
        }

    def _mark_voice(self, message, content: str) -> str:
        """A voice note with no typed words has to say so. It does not score."""
        attachments = getattr(message, "attachments", None)
        if not isinstance(attachments, (list, tuple)):
            return content
        for att in attachments:
            filename = (getattr(att, "filename", "") or "").lower()
            ctype = (getattr(att, "content_type", "") or "").lower()
            is_voice = (
                ctype.startswith("audio/")
                or filename.endswith((".ogg", ".opus", ".m4a", ".wav"))
                or "voice-message" in filename
                or "voice_message" in filename
            )
            if is_voice and "voice note with no transcript" not in (content or "").lower():
                content = (content + "\n[Voice note with no transcript]").strip()
        return content

    async def _readable_content(self, message) -> str:
        content = (getattr(message, "content", "") or "").strip()
        attachments = getattr(message, "attachments", None)
        has_files = isinstance(attachments, (list, tuple)) and len(attachments) > 0
        if has_files or not content:
            try:
                enriched = await enrich_discord_message(message, self.bot)
                if enriched:
                    content = enriched
            except Exception as exc:
                logger.warning("Could not read attachments on message %s: %s", getattr(message, "id", "?"), exc)
        return self._mark_voice(message, content)

    async def _text_channel(self, channel_id: int):
        """Use the cache, then ask Discord. A missing cache entry used to skip the whole channel."""
        channel = self.bot.get_channel(channel_id) if self.bot is not None else None
        if channel is not None and hasattr(channel, "history"):
            return channel
        if self.bot is None:
            return None
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except Exception as exc:
            logger.warning(f"Could not open channel {channel_id}: {exc}")
            return None
        if channel is not None and hasattr(channel, "history"):
            return channel
        return None

    def _message_time(self, message: discord.Message, fallback: datetime) -> str:
        created = getattr(message, "created_at", None)
        if created is not None and hasattr(created, "astimezone"):
            return created.astimezone(TIMEZONE).isoformat()
        return fallback.isoformat()

    def _is_system_message(self, message: discord.Message) -> bool:
        for embed in message.embeds or []:
            title = embed.title or ""
            if any(ignored in title for ignored in SYSTEM_EMBED_TITLES):
                return True
        return False

    def _is_goal_declaration(self, content: str, channel_id: int, when: datetime, is_human: bool) -> bool:
        """A plan for tomorrow. A note about work that already happened is not a plan.

        "Today I sent 40 requests" and a sales list stay on the scorecard.
        "Tomorrow" and a night list with no finished work still lock a plan.
        """
        if not is_human:
            return False
        text = content or ""
        lower = text.lower().strip()
        plan_start = lower.startswith((
            "goal", "tomorrow", "!goal", "/goal", "targets", "commitment", "commitments",
        ))
        if reports_finished_work(text) and not plan_start:
            # After 8 PM, a list in #daily-reports is tomorrow's plan unless it
            # says the work already happened ("sent", "booked", "did").
            night_plan = (
                channel_id == PRIMARY_GOALS_CHANNEL_ID
                and (when.hour >= 20 or when.hour <= 4)
                and not has_finished_verb(text)
            )
            if not night_plan:
                return False
        is_goals_channel = channel_id == PRIMARY_GOALS_CHANNEL_ID
        is_numbered_list = text.strip().startswith(("1.", "1)", "1 -", "- ", "* ", "• "))
        is_nighttime = when.hour >= 20 or when.hour <= 4
        return (
            plan_start
            or (is_goals_channel and (
                is_numbered_list
                or (is_nighttime and not text.startswith("<@") and len(text.splitlines()) >= 2)
            ))
        )

    async def sync_recent_channel_updates(self, limit: int = 100) -> int:
        """
        Scan monitored channels for any recent updates (including GitHub PRs/commits)
        that were missed and backfill them into the database.
        """
        synced_count = 0
        now = datetime.now(TIMEZONE)
        for channel_id in MONITORED_UPDATE_CHANNELS:
            channel = await self._text_channel(channel_id)
            if channel is None:
                continue
            try:
                sources = [channel, *self._child_threads(channel)]
                async for thread in self._archived_threads(channel):
                    sources.append(thread)
                for source in sources:
                    async for message in self._iter_history(source, limit=limit):
                        if self._is_system_message(message):
                            continue
                        # Check GitHub updates
                        gh_updates = self._extract_github_updates(message)
                        if gh_updates:
                            for idx, (f_key, gh_content) in enumerate(gh_updates):
                                effective_mid = message.id if idx == 0 else (message.id * 100 + idx)
                                author_id = FOUNDERS[f_key].get("discord_id") or message.author.id
                                msg_time = self._message_time(message, now)
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
                            f_key = self._resolve_founder_key(
                                message.author.id,
                                message.author.name,
                                **self._author_kwargs(message.author),
                            )
                            own_bot = bool(self.bot and self.bot.user and message.author.id == self.bot.user.id)
                            if f_key and not own_bot:
                                content = await self._readable_content(message)
                                posted_at = message.created_at.astimezone(TIMEZONE) if hasattr(message.created_at, "astimezone") else now
                                is_goal = self._is_goal_declaration(content, channel_id, posted_at, not message.author.bot)
                                if content.strip() and not is_goal:
                                    msg_time = self._message_time(message, now)
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

        # A thread keeps its parent's channel id, or the reply is invisible.
        channel_id = self._logged_channel_id(message.channel) or message.channel.id
        now = datetime.now(TIMEZONE)

        # 2. Check for GitHub webhook updates (PRs, commits, branches)
        gh_updates = self._extract_github_updates(message)
        if gh_updates and channel_id in MONITORED_UPDATE_CHANNELS:
            for idx, (f_key, gh_content) in enumerate(gh_updates):
                effective_mid = message.id if idx == 0 else (message.id * 100 + idx)
                author_id = FOUNDERS[f_key].get("discord_id") or message.author.id
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
            **self._author_kwargs(message.author),
        )

        if not founder_key:
            return

        content = self._mark_voice(message, await enrich_discord_message(message, self.bot))

        if not content.strip():
            return

        # Ignore bot's own posts in primary goals channel (prevents feedback loops on scorecards and lock embeds)
        if channel_id == PRIMARY_GOALS_CHANNEL_ID and message.author.bot:
            return

        # Goals can ONLY be declared by human founders, never by automated bots
        is_goal_declaration = self._is_goal_declaration(
            content,
            channel_id,
            now,
            not message.author.bot,
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
                timestamp=self._message_time(message, now),
            )
            logger.info(f"Logged update from {founder_key} in channel {channel_id}: {content[:40]}...")

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """An edited note replaces the saved one. The first draft is not a second score."""
        if self.bot is None:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                return
        logged_channel_id = self._logged_channel_id(channel)
        if logged_channel_id is None:
            return

        message = getattr(payload, "cached_message", None) or getattr(payload, "message", None)
        if message is None:
            try:
                message = await channel.fetch_message(payload.message_id)
            except Exception:
                return
        if self._is_system_message(message):
            return
        if self._extract_github_updates(message):
            return

        founder_key = self._resolve_founder_key(
            message.author.id,
            message.author.name,
            **self._author_kwargs(message.author),
        )
        if not founder_key:
            return
        own_bot = bool(self.bot.user and message.author.id == self.bot.user.id)
        if own_bot:
            return

        content = self._mark_voice(message, await enrich_discord_message(message, self.bot))
        if not content.strip():
            return
        posted_at = message.created_at.astimezone(TIMEZONE) if hasattr(message.created_at, "astimezone") else datetime.now(TIMEZONE)
        if self._is_goal_declaration(content, logged_channel_id, posted_at, not message.author.bot):
            return
        await upsert_channel_update(
            message_id=message.id,
            founder_key=founder_key,
            discord_user_id=message.author.id,
            channel_id=logged_channel_id,
            content=content,
            timestamp=self._message_time(message, posted_at),
        )

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
