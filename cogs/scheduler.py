"""
Discord Cog: Scheduler
Runs 24/7 background tasks:
- 8:00 PM: Daily scoring calculation, Praise & Bottlenecks digest
- 9:00 PM: Tomorrow's Goal Setting prompt
- Sunday 9:00 PM: Weekly Executive SWOT Report
- 1st of Month 10:00 AM: Monthly Dynamic Earnout Ledger
"""

import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any

import zoneinfo
from config import (
    PRIMARY_GOALS_CHANNEL_ID,
    LEADERSHIP_CHANNEL_ID,
    SCORES_CHANNEL_ID,
    MONITORED_UPDATE_CHANNELS,
    SYSTEM_EMBED_TITLES,
    PEER_EMOJIS,
    FOUNDERS,
    DAILY_SCORING_HOUR,
    DAILY_GOALS_HOUR,
    WEEKLY_SWOT_DAY,
    WEEKLY_SWOT_HOUR,
    MONTHLY_CLOSE_DAY,
    MONTHLY_CLOSE_HOUR,
    TIMEZONE,
)
from engine.discord_budget import fit_embed, pack_embeds, pack_field_embeds
from database.models import (
    get_all_users,
    get_goals_for_date,
    get_updates_for_date_range,
    get_reactions_for_messages,
    save_daily_score,
    get_daily_score,
    save_channel_update,
    record_peer_reaction,
    get_scores_in_date_range,
    get_all_scores_in_date_range,
    record_monthly_equity_tranche,
    get_latest_equity_status,
    get_recent_founder_context,
)
from engine.credit import assign_credit, prior_from_scores
from engine.impact import praise_for_scored_lines, size_label
from engine.evaluator import evaluate_daily_execution_with_ai
from engine.scoring import compute_daily_score
from engine.swot import generate_weekly_swot_with_ai
from engine.equity import compute_monthly_equity_split
from skills_bridge.discord_bridge import (
    COLOR_SUCCESS,
    COLOR_PRIMARY,
    COLOR_WARNING,
    COLOR_EQUITY,
    COLOR_SWOT,
)

logger = logging.getLogger(__name__)


def failed_score_card(key: str, info: Dict[str, Any]) -> Dict[str, Any]:
    """A card that keeps one person's failure from erasing the rest of the night."""
    name = info.get("display_name", key)
    return {
        "founder_key": key,
        "name": f"{name} ({info.get('role', 'Team')})",
        "final_score": 0.0,
        "failed": True,
        "description": (
            f"{name}'s score did not save tonight. "
            "The rest of the team is still on this card."
        ),
    }


def rep_beat_founders_line(scored: List[tuple]) -> str:
    """One sentence when a sales rep finishes above every founder. No equity write."""
    by_key = {key: score for key, score in scored}
    founder_scores = [
        by_key[key]
        for key, info in FOUNDERS.items()
        if info.get("on_cap_table") and key in by_key
    ]
    if not founder_scores:
        return ""
    ceiling = max(founder_scores)
    beaters = []
    for key, info in FOUNDERS.items():
        if info.get("on_cap_table") or key not in by_key:
            continue
        gap = by_key[key] - ceiling
        if gap > 0:
            beaters.append((info["display_name"], gap))
    if not beaters:
        return ""
    if len(beaters) == 1:
        name, gap = beaters[0]
        return f"{name} finished {gap:.1f} pts above every founder."
    joined = " and ".join(f"{name} ({gap:.1f} pts above)" for name, gap in beaters)
    return f"{joined} finished above every founder."


def score_window(score_date):
    """Notes from last night's 8:00 PM through the end of this calendar day.

    The card runs at 8:00 PM, so a report posted after that lands on the next card.
    A note at 1:00 AM belongs to that calendar day. It is not dropped.
    """
    start_day = score_date - timedelta(days=1)
    return (
        f"{start_day.strftime('%Y-%m-%d')}T20:00:00",
        f"{score_date.strftime('%Y-%m-%d')}T23:59:59",
    )


def keeps_update(update: Dict[str, Any], score_date) -> bool:
    """Should this note go on the card for score_date?

    A note posted last night after 8:00 PM is the late report this card
    exists to catch, so "Daily report 18 Nov" posted at 9:00 PM on the 18th
    counts here. A note posted today that names yesterday's date is a recap
    of a day that already had its card, so it stays off.
    """
    content = update.get("content") or ""
    lower = content.lower()
    if not content.strip():
        return False
    if "commitments locked" in lower or "[embed: 🔒" in lower:
        return False
    prev_date = score_date - timedelta(days=1)
    posted = str(update.get("timestamp") or "")
    posted_last_night = posted[:10] == prev_date.strftime("%Y-%m-%d")
    if posted_last_night:
        return True
    prev_patterns = (
        f"{prev_date.day} {prev_date.strftime('%b').lower()}",
        prev_date.strftime("%Y-%m-%d"),
    )
    return not any(pattern in lower for pattern in prev_patterns)


async def collect_score_cards(people, score_one):
    """Score each person. One failure still leaves the other cards."""
    cards = []
    ranks = []
    for key, info in people:
        try:
            card, rank = await score_one(key, info)
            cards.append(card)
            ranks.append(rank)
        except Exception:
            logger.exception("Daily score failed for %s", key)
            cards.append(failed_score_card(key, info))
            ranks.append((key, info.get("display_name", key), info.get("role", "Team"), 0.0))
    return cards, ranks


class SchedulerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_inquiry_date = ""
        self.last_scored_date = ""
        self.last_prompted_goals_date = ""
        self.last_goals_nudge_date = ""
        self.last_swot_date = ""
        self.last_equity_month = ""
        self.chronos_loop.start()

    def cog_unload(self):
        self.chronos_loop.cancel()

    @tasks.loop(minutes=1)
    async def chronos_loop(self):
        """Heartbeat loop checked every 60 seconds."""
        now = datetime.now(TIMEZONE)
        today_str = now.strftime("%Y-%m-%d")
        month_str = now.strftime("%Y-%m")

        # 0. 7:15 PM Pre-Scoring Context Check
        if (now.hour == 19 and now.minute >= 15 and now.hour < 20) and self.last_inquiry_date != today_str:
            self.last_inquiry_date = today_str
            logger.info(f"Triggering 7:15 PM Pre-Scoring Context Inquiry for {today_str}")
            await self.run_context_inquiry_callout(today_str)

        # 1. 8:00 PM Daily Scoring Calculation (with catch-up between 8 PM and 11 PM)
        if (now.hour >= DAILY_SCORING_HOUR and now.hour < 23) and self.last_scored_date != today_str:
            existing = await get_daily_score("hridesh", today_str)
            if not existing:
                self.last_scored_date = today_str
                logger.info(f"Triggering Daily Scoring calculation for {today_str}")
                await self.run_daily_scoring(today_str)
            else:
                self.last_scored_date = today_str

        # 2. 9:00 PM Tomorrow's Goal Setting Callout
        if now.hour == DAILY_GOALS_HOUR and self.last_prompted_goals_date != today_str:
            self.last_prompted_goals_date = today_str
            logger.info(f"Triggering 9:00 PM Goal Prompt for {today_str}")
            await self.run_daily_goals_callout()

        # 2b. 9:30 PM Tomorrow's Goal Setting Nudge (for missing commitments)
        if now.hour == 21 and now.minute >= 30 and self.last_goals_nudge_date != today_str:
            self.last_goals_nudge_date = today_str
            logger.info(f"Checking for missing 9:30 PM goals for {today_str}")
            await self.run_goals_nudge(today_str)

        # 3. Sunday 9:00 PM Weekly Executive SWOT Analysis
        if now.weekday() == WEEKLY_SWOT_DAY and now.hour == WEEKLY_SWOT_HOUR and self.last_swot_date != today_str:
            self.last_swot_date = today_str
            logger.info("Triggering Sunday 9:00 PM Weekly SWOT Analysis")
            await self.run_weekly_swot()

        # 4. 1st of Month 10:00 AM Monthly Equity Ledger Evolution
        if now.day == MONTHLY_CLOSE_DAY and now.hour == MONTHLY_CLOSE_HOUR and self.last_equity_month != month_str:
            self.last_equity_month = month_str
            logger.info(f"Triggering Monthly Equity Evolution Closeout for {month_str}")
            await self.run_monthly_equity_closeout(now)

    @chronos_loop.before_loop
    async def before_chronos(self):
        if hasattr(self.bot, "wait_until_ready") and callable(self.bot.wait_until_ready):
            res = self.bot.wait_until_ready()
            if asyncio.iscoroutine(res):
                await res

    async def sync_channel_history_for_today(self, target_date: Optional[datetime.date] = None):
        """Actively read monitored Discord channels for today's updates and save to DB."""
        if not target_date:
            target_date = datetime.now(TIMEZONE).date()

        # Same window the card scores: yesterday 8:00 PM through the end of this calendar day.
        window_start, window_end = score_window(target_date)
        start_of_window_ist = datetime.strptime(window_start, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=TIMEZONE)
        end_of_window_ist = datetime.strptime(window_end, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=TIMEZONE)
        start_utc = start_of_window_ist.astimezone(zoneinfo.ZoneInfo("UTC"))
        end_utc = end_of_window_ist.astimezone(zoneinfo.ZoneInfo("UTC"))

        prev_date = target_date - timedelta(days=1)
        prev_patterns = [
            f"{prev_date.day} {prev_date.strftime('%b').lower()}",
            f"{prev_date.strftime('%Y-%m-%d')}",
        ]

        tracker_cog = self.bot.get_cog("TrackerCog")

        for ch_id in MONITORED_UPDATE_CHANNELS:
            channel = self.bot.get_channel(ch_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(ch_id)
                except Exception:
                    continue
            if not channel:
                continue

            try:
                sources = [channel]
                if tracker_cog:
                    sources.extend(tracker_cog._child_threads(channel))
                    async for thread in tracker_cog._archived_threads(channel):
                        sources.append(thread)
                for source in sources:
                    async for msg in self._day_messages(source, tracker_cog, start_utc):
                        if msg.created_at < start_utc or msg.created_at > end_utc:
                            continue

                        # Skip automated system embeds generated by the review bot
                        is_sys = False
                        for e in msg.embeds:
                            title = e.title or ""
                            if any(ignored in title for ignored in SYSTEM_EMBED_TITLES):
                                is_sys = True
                                break
                        if is_sys:
                            continue

                        # Check for GitHub webhook updates (PRs, commits, branches)
                        if tracker_cog:
                            gh_updates = tracker_cog._extract_github_updates(msg)
                            if gh_updates:
                                msg_ist = msg.created_at.astimezone(TIMEZONE)
                                for idx, (f_key, gh_content) in enumerate(gh_updates):
                                    effective_mid = msg.id if idx == 0 else (msg.id * 100 + idx)
                                    author_id = FOUNDERS[f_key].get("discord_id") or msg.author.id
                                    await save_channel_update(
                                        message_id=effective_mid,
                                        founder_key=f_key,
                                        discord_user_id=author_id,
                                        channel_id=channel.id,
                                        content=gh_content,
                                        timestamp=msg_ist.isoformat(),
                                    )
                                continue

                        # Screenshots and voice notes need the same reader the live path uses.
                        attachments = getattr(msg, "attachments", None)
                        has_files = isinstance(attachments, (list, tuple)) and len(attachments) > 0
                        if tracker_cog and (has_files or not (msg.content or "").strip()):
                            content = await tracker_cog._readable_content(msg)
                        else:
                            content = (msg.content or "").strip()
                        for e in msg.embeds:
                            if e.description and e.description not in content:
                                content += f"\n[Embed: {e.title or ''}] {e.description}"
                        if tracker_cog:
                            content = tracker_cog._mark_voice(msg, content)

                        if not content.strip():
                            continue

                        # If the content explicitly states it's an update for a previous date, ignore it
                        lower_content = content.lower()
                        if any(p in lower_content for p in prev_patterns):
                            continue

                        msg_ist = msg.created_at.astimezone(TIMEZONE)
                        # A tomorrow-plan stays a goal. A finished sales log stays an update.
                        if tracker_cog and tracker_cog._is_goal_declaration(
                            content, channel.id, msg_ist, not msg.author.bot
                        ):
                            continue

                        # Resolve founder key (including Peter Thiel assistant bot for Hridesh)
                        founder_key = None
                        if tracker_cog:
                            founder_key = tracker_cog._resolve_founder_key(
                                msg.author.id,
                                msg.author.name,
                                **tracker_cog._author_kwargs(msg.author),
                            )
                        if not founder_key:
                            continue

                        # Store in SQLite with IST timestamp for exact day matching
                        await save_channel_update(
                            message_id=msg.id,
                            founder_key=founder_key,
                            discord_user_id=msg.author.id,
                            channel_id=channel.id,
                            content=content,
                            timestamp=msg_ist.isoformat(),
                        )

                        for reaction in msg.reactions:
                            emoji_str = str(reaction.emoji)
                            if emoji_str in PEER_EMOJIS:
                                async for user in reaction.users():
                                    if user.id != self.bot.user.id:
                                        r_key = tracker_cog._resolve_founder_key(
                                            user.id,
                                            user.name,
                                            **tracker_cog._author_kwargs(user),
                                        ) if tracker_cog else "peer"
                                        await record_peer_reaction(
                                            message_id=msg.id,
                                            reactor_discord_id=user.id,
                                            reactor_founder_key=r_key or "peer",
                                            emoji=emoji_str,
                                            weight=PEER_EMOJIS[emoji_str],
                                        )
            except Exception as e:
                logger.warning(f"Could not fetch history from channel {ch_id}: {e}")

    async def _day_messages(self, channel, tracker_cog, start_utc):
        """Every message since the window opened, including pages past the first 100."""
        if tracker_cog is not None:
            async for message in tracker_cog._iter_history(channel, after=start_utc, cap=1000):
                yield message
            return
        history = getattr(channel, "history", None)
        if history is None:
            return
        async for message in history(limit=100, after=start_utc):
            yield message

    async def run_context_inquiry_callout(self, today_str: str):
        """At 7:15 PM, ask founders quick clarification questions about ambiguous tasks or attachments before 8:00 PM scoring."""
        from engine.inquiry import generate_pre_scoring_inquiries
        inquiries = await generate_pre_scoring_inquiries(today_str)
        if not inquiries:
            logger.info(f"No context inquiries needed for {today_str}")
            return

        channel = self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            logger.error("Could not find primary goals channel for 7:15 PM context check.")
            return

        fields = []
        for key, question in inquiries.items():
            founder_info = FOUNDERS.get(key, {})
            name = founder_info.get("display_name", key.capitalize())
            role = founder_info.get("role", "Teammate")
            fields.append((f"❓ {name} ({role})", f"*{question}*", False))

        embeds = pack_field_embeds(
            title="🔍 7:15 PM Quick Context Check • Before Tonight's Scores",
            description=(
                "Hey team! I'm reviewing today's work before crunching tonight's 8:00 PM scorecards.\n"
                "I noticed a couple of things that could use a quick clarification so you get full credit:"
            ),
            fields=fields,
            color=COLOR_PRIMARY,
            footer="Reply in this channel before 8:00 PM so Peter can count it.",
        )
        for batch in pack_embeds(embeds):
            await channel.send(embeds=batch)

    async def run_daily_goals_callout(self):
        """Prompt the whole team in #daily-reports to lock in tomorrow's commitments."""
        channel = self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        lines = [
            f"• **{info['display_name']} ({info['role']})**: {info.get('goal_line', info['dharma_focus'][0])}"
            for info in FOUNDERS.values()
        ]
        embed = discord.Embed(
            title="🌙 9:00 PM Check-In • What's your plan for tomorrow?",
            description=(
                "Team, before you head to bed, drop 2 to 4 big things you want to finish tomorrow:\n\n"
                + "\n".join(lines)
                + "\n\nJust write a quick list in this channel!"
            ),
            color=COLOR_PRIMARY
        )
        embed.set_footer(text="Calcrum Review Bot • 60-Second Check-In")
        await channel.send(embed=embed)

    async def run_goals_nudge(self, today_str: str):
        """At 9:30 PM, check if all founders declared commitments and nudge missing ones."""
        channel = self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        now = datetime.now(TIMEZONE)
        target_date = (now if now.hour < 5 else now + timedelta(days=1)).strftime("%Y-%m-%d")

        missing = []
        for key, info in FOUNDERS.items():
            record = await get_goals_for_date(key, target_date)
            if not record:
                missing.append(f"**{info['display_name']} ({info['role']})**")

        if missing:
            embed = discord.Embed(
                title="⚠️ 9:30 PM Quick Reminder • Don't forget your goals!",
                description=(
                    f"Still waiting for tomorrow's plan from: {', '.join(missing)}\n\n"
                    "Take 60 seconds to share what you plan to finish tomorrow before you go to sleep. "
                    "Starting tomorrow with a clear plan makes everything easier!"
                ),
                color=COLOR_WARNING
            )
            embed.set_footer(text="Calcrum Review Bot • 60-Second Check-In")
            await channel.send(embed=embed)

    async def run_daily_scoring(self, today_str: str, target_channel_id: Optional[int] = None):
        """Calculate and publish 8:00 PM daily scores, praise, and feedback."""
        dest_id = target_channel_id or SCORES_CHANNEL_ID or PRIMARY_GOALS_CHANNEL_ID
        channel = self.bot.get_channel(dest_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(dest_id)
            except Exception:
                channel = self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        # 1. Parse target date and sync live channel history strictly for that day
        try:
            target_date = datetime.strptime(today_str, "%Y-%m-%d").date()
        except Exception:
            target_date = datetime.now(TIMEZONE).date()

        await self.sync_channel_history_for_today(target_date)

        # Yesterday 8:00 PM through the end of today. A 9:00 PM sales log lands on the next card.
        start_time, end_time = score_window(target_date)

        hist_context = await get_recent_founder_context(days=3)

        day_updates = []
        for roster_key in FOUNDERS:
            try:
                raw_updates = await get_updates_for_date_range(roster_key, start_time, end_time)
            except Exception:
                logger.exception("Could not load updates for %s", roster_key)
                continue
            for update in raw_updates:
                if keeps_update(update, target_date):
                    day_updates.append(update)

        # One pass over the whole day. The speaker does not keep the build.
        # Today's own card is not in the lookback, so a rerun does not zero today's work.
        prior_start = (target_date - timedelta(days=7)).isoformat()
        prior_end = (target_date - timedelta(days=1)).isoformat()
        prior_rows = await get_all_scores_in_date_range(prior_start, prior_end)
        credited = assign_credit(day_updates, prior_from_scores(prior_rows))

        async def score_one(key, info):
            goals_record = await get_goals_for_date(key, today_str)
            locked_goals = goals_record["parsed_goals"] if goals_record else []

            updates = [update for update in day_updates if update.get("founder_key") == key]
            msg_ids = [u["message_id"] for u in updates]
            reactions = await get_reactions_for_messages(msg_ids)

            tasks = credited.get(key, [])
            finished = [task for task in tasks if task.get("completion", 0) > 0]
            if finished:
                # The model writes the praise from scores that are already decided.
                credit_text = "\n".join(
                    (
                        f"{task['task']} | size {size_label(task.get('complexity', 1), task.get('rubric_size', 1))}"
                        f" | {task['score_reason']}"
                    )
                    for task in finished
                )
                ai_eval = await evaluate_daily_execution_with_ai(
                    key, locked_goals, credit_text, historical_context=hist_context
                )
                # A model bonus used to turn a small chore into 5 points.
                # Praise can only name the lines that scored.
                bonus = 0.0
                ai_eval["praise_text"] = praise_for_scored_lines(finished)
            elif tasks:
                bonus = 0.0
                ai_eval = {
                    "praise_text": "Nothing here counted as finished work.",
                    "feedback_text": tasks[0].get("score_reason") or "Saying it is done is not the same as doing it.",
                    "mentor_question": "",
                    "spontaneous_bonus": 0.0,
                }
            else:
                bonus = 0.0
                ai_eval = {
                    "praise_text": "No activity recorded today.",
                    "feedback_text": "Make sure to set your goals and finish them tomorrow!",
                    "mentor_question": "",
                    "spontaneous_bonus": 0.0,
                }

            author_id = info.get("discord_id") or 0
            score_data = compute_daily_score(
                task_evaluations=tasks,
                reactions=reactions,
                author_discord_id=author_id,
                spontaneous_bonus=bonus,
            )

            final_score = score_data["final_score"]

            # Save to Database
            await save_daily_score(
                founder_key=key,
                score_date=today_str,
                completion_score=score_data["raw_task_sum"],
                complexity_score=sum([t["complexity"] for t in score_data["task_breakdown"]]),
                dharma_score=1.0,
                peer_multiplier=score_data["peer_multiplier"],
                bonus_points=score_data["bonus_points"],
                final_score=final_score,
                breakdown_json=score_data,
                praise_text=ai_eval.get("praise_text", ""),
                feedback_text=ai_eval.get("feedback_text", ""),
            )

            task_blocks = []
            for t in score_data.get("task_breakdown", []):
                task_desc = t.get("task", "Task")
                comp_pct = int(t.get("completion", 0.0) * 100)
                w = int(t.get("complexity", 3))
                rubric = int(t.get("rubric_size", w))
                pts = t.get("task_points", 0.0)
                reason = t.get("score_reason", "Score based on verified activity.").strip()

                block = (
                    f"• **{task_desc}**\n"
                    f"  ↳ Size: `{size_label(w, rubric)}` | Done: `{comp_pct}%` → **+{pts:.1f} pts**\n"
                    f"  💬 *Why: {reason}*"
                )
                task_blocks.append(block)

            tasks_text = "\n\n".join(task_blocks) if task_blocks else "*No tasks finished today.*"
            bonus_pts = score_data.get("bonus_points", 0.0)
            raw_sum = score_data.get("raw_task_sum", 0.0)
            peer_mult = score_data.get("peer_multiplier", 1.0)

            m_q = ai_eval.get("mentor_question", "")
            m_q_section = f"\n\n❓ **Question for Tomorrow:**\n*\"{m_q}\"*" if m_q else ""

            founder_desc = (
                f"📋 **Commitments & Tasks:**\n\n"
                f"{tasks_text}\n\n"
                f"───────────────────────────────────────\n\n"
                f"📊 **Score Math:** `({raw_sum:.1f} task pts × {peer_mult}x boost) + {bonus_pts:.1f} bonus = {final_score:.2f} pts`\n\n"
                f"🏆 **What Went Great:**\n{ai_eval.get('praise_text', 'Good steady work today.')}\n\n"
                f"💡 **Advice from Peter:**\n{ai_eval.get('feedback_text', 'Keep building and moving fast.')}"
                f"{m_q_section}"
            )

            card = {
                "founder_key": key,
                "name": f"{info['display_name']} ({info['role']})",
                "final_score": final_score,
                "description": founder_desc,
            }
            await asyncio.sleep(1.0)
            return card, (key, info["display_name"], info["role"], final_score)

        founder_cards, leaderboard_ranks = await collect_score_cards(list(FOUNDERS.items()), score_one)

        # Sort leaderboard
        leaderboard_ranks.sort(key=lambda x: x[3], reverse=True)
        top_name = leaderboard_ranks[0][1] if leaderboard_ranks else "Team"

        # Build clean multi-embed payload
        embed_list = []

        # 1. Header Overview Embed
        medals = ("🥇", "🥈", "🥉")
        standing_lines = []
        for i, rank in enumerate(leaderboard_ranks):
            medal = medals[i] if i < len(medals) else "▫️"
            standing_lines.append(f"• {medal} **{rank[1]} ({rank[2]}):** **{rank[3]:.2f} pts**")
        beat_line = rep_beat_founders_line([
            (card["founder_key"], card["final_score"])
            for card in founder_cards
            if not card.get("failed")
        ])
        beat_section = f"\n\n{beat_line}" if beat_line else ""
        overview_desc = (
            f"👑 **MVP of the Day:** **{top_name}**\n\n"
            f"**Today's Standings:**\n"
            + "\n".join(standing_lines)
            + beat_section
            + "\n\n*Each person's proof and notes are in the cards below. Everyone can see the whole team.*"
        )
        footer = "Calcrum Review Bot • Scores are saved automatically every night"
        embed_list.append(fit_embed(
            title=f"🌆 8:00 PM Daily Scorecard • {today_str}",
            description=overview_desc,
            color=COLOR_SUCCESS,
            footer=footer,
        ))

        # 2. One card per person, packed so each Discord message stays under 6,000 characters.
        role_colors = {
            "hridesh": 0xF1C40F,  # Gold
            "swarit": 0x3498DB,   # Blue
            "rahul": 0xE67E22,    # Orange
            "yash": 0x1ABC9C,     # Teal
            "shivang": 0x27AE60,  # Green
        }

        for rank_info in leaderboard_ranks:
            f_key = rank_info[0]
            card = next((c for c in founder_cards if c["founder_key"] == f_key), None)
            if not card:
                continue
            color = role_colors.get(f_key, COLOR_PRIMARY)
            crown = "👑" if rank_info == leaderboard_ranks[0] else "🔹"
            embed_list.append(fit_embed(
                title=f"{crown} {card['name']} — {card['final_score']:.2f} pts",
                description=card["description"],
                color=color,
                footer=footer,
            ))

        for batch in pack_embeds(embed_list):
            await channel.send(embeds=batch)

    async def run_weekly_swot(self):
        """Aggregate 7-day data and post Executive SWOT to #leadership."""
        channel = self.bot.get_channel(LEADERSHIP_CHANNEL_ID) or self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        end_date = datetime.now(TIMEZONE).date()
        start_date = end_date - timedelta(days=6)

        all_scores = await get_all_scores_in_date_range(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

        weekly_payload = {}
        for key in FOUNDERS.keys():
            scores = [s for s in all_scores if s["founder_key"] == key]
            weekly_payload[key] = {
                "name": FOUNDERS[key]["display_name"],
                "role": FOUNDERS[key]["role"],
                "total_points": sum([s["final_score"] for s in scores]),
                "avg_daily_points": sum([s["final_score"] for s in scores]) / max(1, len(scores)),
                "days_active": len(scores),
            }

        swot_data = await generate_weekly_swot_with_ai(weekly_payload)

        founder_swots = swot_data.get("founder_swot", {})
        fields = []
        for key, info in FOUNDERS.items():
            data = founder_swots.get(key, {})
            pts = weekly_payload.get(key, {}).get("total_points", 0.0)
            fields.append((
                f"{info['display_name']} ({info['role']}) — {pts:.1f} pts this week",
                (
                    f"💪 **Strengths:** {data.get('strengths', 'No notes yet.')}\n"
                    f"⚠️ **Weaknesses:** {data.get('weaknesses', 'None flagged.')}\n"
                    f"🚀 **Opportunities:** {data.get('opportunities', 'Keep the daily log going.')}\n"
                    f"🛑 **Threats:** {data.get('threats', 'Missing updates hide the real work.')}"
                ),
                False,
            ))

        embeds = pack_field_embeds(
            title="📊 Weekly Team Report",
            description=swot_data.get("overall_summary", "Here is the week in plain words."),
            fields=fields,
            color=COLOR_SWOT,
            footer="Calcrum Review Bot • Everyone can see the whole team here",
        )
        for batch in pack_embeds(embeds):
            await channel.send(embeds=batch)

    async def run_monthly_equity_closeout(self, now: datetime):
        """Compute monthly dynamic tranche and post provisional draft to #leadership."""
        channel = self.bot.get_channel(LEADERSHIP_CHANNEL_ID) or self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        # Previous month
        first_day_current = now.replace(day=1)
        last_day_prev = first_day_current - timedelta(days=1)
        prev_month_str = last_day_prev.strftime("%Y-%m")
        start_date = last_day_prev.replace(day=1).strftime("%Y-%m-%d")
        end_date = last_day_prev.strftime("%Y-%m-%d")

        all_month_scores = await get_all_scores_in_date_range(start_date, end_date)

        # Sum monthly scores for Swarit (CTO) and Rahul (COO)
        swarit_scores = [s for s in all_month_scores if s["founder_key"] == "swarit"]
        rahul_scores = [s for s in all_month_scores if s["founder_key"] == "rahul"]

        total_swarit = sum([s["final_score"] for s in swarit_scores])
        total_rahul = sum([s["final_score"] for s in rahul_scores])

        # Current cumulative equity standings
        users = await get_all_users()
        user_map = {u["founder_key"]: u for u in users}
        cur_swarit_equity = user_map.get("swarit", {}).get("earned_equity", 0.0)
        cur_coo_equity = user_map.get("rahul", {}).get("earned_equity", 0.0)

        # Month index calculation (assuming Month 1 starts September 2026)
        month_index = 1

        split_result = compute_monthly_equity_split(
            month_index=month_index,
            year_month=prev_month_str,
            cto_score=total_swarit,
            coo_score=total_rahul,
            current_cto_equity=cur_swarit_equity,
            current_coo_equity=cur_coo_equity,
        )

        # Save draft in database
        await record_monthly_equity_tranche(
            month_index=month_index,
            year_month=prev_month_str,
            founder_key="swarit",
            total_monthly_score=total_swarit,
            score_ratio=split_result["ratio_cto"],
            equity_awarded=split_result["equity_awarded_cto"],
            cumulative_equity=split_result["cumulative_cto"],
            treasury_diverted=split_result["treasury_diverted"],
            is_ratified=0,
        )
        await record_monthly_equity_tranche(
            month_index=month_index,
            year_month=prev_month_str,
            founder_key="rahul",
            total_monthly_score=total_rahul,
            score_ratio=split_result["ratio_coo"],
            equity_awarded=split_result["equity_awarded_coo"],
            cumulative_equity=split_result["cumulative_coo"],
            treasury_diverted=split_result["treasury_diverted"],
            is_ratified=0,
        )

        embed = discord.Embed(
            title=f"🏛️ Monthly Equity Evolution Report • Month {month_index} ({prev_month_str})",
            description=(
                f"**Tranche Released:** {split_result['monthly_tranche']:.4f}% of company equity (Month {month_index}/24)\n"
                f"**Status:** ⏳ **Pending Founder Triple-Confirmation**\n\n"
                f"• **Hridesh (CEO)**: 45.000% (Protected Vested Baseline)\n"
                f"• **Swarit (CTO)**: Score {total_swarit:.1f} ({split_result['ratio_cto']*100:.1f}%) $\\to$ +{split_result['equity_awarded_cto']:.4f}% (Total: **{split_result['cumulative_cto']:.4f}%**)\n"
                f"• **Rahul (COO)**: Score {total_rahul:.1f} ({split_result['ratio_coo']*100:.1f}%) $\\to$ +{split_result['equity_awarded_coo']:.4f}% (Total: **{split_result['cumulative_coo']:.4f}%**)\n"
                f"• **Company Treasury**: +{split_result['treasury_diverted']:.4f}%\n\n"
                f"Type `/confirm-equity {month_index}` to ratify this allocation into permanent legal standing."
            ),
            color=COLOR_EQUITY
        )
        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
