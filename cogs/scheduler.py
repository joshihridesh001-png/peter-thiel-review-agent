"""
Discord Cog: Scheduler
Runs 24/7 background tasks:
- 8:00 PM: Daily scoring calculation, Praise & Bottlenecks digest
- 9:00 PM: Tomorrow's Goal Setting prompt
- Sunday 9:00 PM: Weekly Executive SWOT Report
- 1st of Month 10:00 AM: Monthly Dynamic Earnout Ledger
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any

import zoneinfo
from config import (
    PRIMARY_GOALS_CHANNEL_ID,
    LEADERSHIP_CHANNEL_ID,
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
    record_monthly_equity_tranche,
    get_latest_equity_status,
    get_recent_founder_context,
)
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


class SchedulerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
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
        await self.bot.wait_until_ready()

    async def sync_channel_history_for_today(self, target_date: Optional[datetime.date] = None):
        """Actively read monitored Discord channels for today's updates and save to DB."""
        if not target_date:
            target_date = datetime.now(TIMEZONE).date()

        # Strictly calculate start (05:00 AM IST) and end of target day in IST, then convert to UTC
        start_of_day_ist = datetime(target_date.year, target_date.month, target_date.day, 5, 0, 0, tzinfo=TIMEZONE)
        end_of_day_ist = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=TIMEZONE)
        start_utc = start_of_day_ist.astimezone(zoneinfo.ZoneInfo("UTC"))
        end_utc = end_of_day_ist.astimezone(zoneinfo.ZoneInfo("UTC"))

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
                # Limit to recent messages after start of day UTC
                async for msg in channel.history(limit=100, after=start_utc):
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

                    # Build content including embed descriptions for assistant posts
                    content = msg.content.strip()
                    for e in msg.embeds:
                        if e.description:
                            content += f"\n[Embed: {e.title or ''}] {e.description}"

                    if not content.strip():
                        continue

                    # If the content explicitly states it's an update for a previous date, ignore it
                    lower_content = content.lower()
                    if any(p in lower_content for p in prev_patterns):
                        continue

                    # Resolve founder key (including Peter Thiel assistant bot for Hridesh)
                    founder_key = None
                    if tracker_cog:
                        founder_key = tracker_cog._resolve_founder_key(
                            msg.author.id,
                            msg.author.name,
                            is_bot=msg.author.bot
                        )
                    if not founder_key:
                        continue

                    # Store in SQLite with IST timestamp for exact day matching
                    msg_ist = msg.created_at.astimezone(TIMEZONE)
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
                                    r_key = tracker_cog._resolve_founder_key(user.id, user.name) if tracker_cog else "peer"
                                    await record_peer_reaction(
                                        message_id=msg.id,
                                        reactor_discord_id=user.id,
                                        reactor_founder_key=r_key or "peer",
                                        emoji=emoji_str,
                                        weight=PEER_EMOJIS[emoji_str],
                                    )
            except Exception as e:
                logger.warning(f"Could not fetch history from channel {ch_id}: {e}")

    async def run_daily_goals_callout(self):
        """Prompt all 3 founders in #daily-reports to lock in tomorrow's commitments."""
        channel = self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title="🌙 9:00 PM Check-In • What's your plan for tomorrow?",
            description=(
                "Team, before you head to bed, drop 2 to 4 big things you want to finish tomorrow:\n\n"
                "• **Hridesh (CEO)**: Big deals, investors, and company direction\n"
                "• **Swarit (CTO)**: Writing code, fixing bugs, and making the product work\n"
                "• **Rahul (COO)**: Talking to customers, pilots, and daily operations\n\n"
                "Just write a quick list in this channel!"
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

    async def run_daily_scoring(self, today_str: str):
        """Calculate and publish 8:00 PM daily scores, praise, and feedback."""
        channel = self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        # 1. Parse target date and sync live channel history strictly for that day
        try:
            target_date = datetime.strptime(today_str, "%Y-%m-%d").date()
        except Exception:
            target_date = datetime.now(TIMEZONE).date()

        await self.sync_channel_history_for_today(target_date)

        # Strictly filter updates from 05:00:00 to 23:59:59 of today IST (daytime work cycle)
        start_time = f"{today_str}T05:00:00"
        end_time = f"{today_str}T23:59:59"

        summary_fields = []
        leaderboard_ranks = []

        prev_date = target_date - timedelta(days=1)
        prev_patterns = [
            f"{prev_date.day} {prev_date.strftime('%b').lower()}",
            f"{prev_date.strftime('%Y-%m-%d')}",
        ]

        hist_context = await get_recent_founder_context(days=3)

        for key, info in FOUNDERS.items():
            goals_record = await get_goals_for_date(key, today_str)
            locked_goals = goals_record["parsed_goals"] if goals_record else []

            raw_updates = await get_updates_for_date_range(key, start_time, end_time)
            # Filter out any updates that explicitly belong to a previous day or are bot lock embeds
            updates = [
                u for u in raw_updates 
                if not any(p in u["content"].lower() for p in prev_patterns)
                and "commitments locked" not in u["content"].lower()
                and "[embed: 🔒" not in u["content"].lower()
            ]
            updates_text = "\n".join([f"[{u['timestamp']}] {u['content']}" for u in updates])

            msg_ids = [u["message_id"] for u in updates]
            reactions = await get_reactions_for_messages(msg_ids)

            # Gemini Evaluation with Historical Context Memory
            ai_eval = await evaluate_daily_execution_with_ai(
                key, locked_goals, updates_text, historical_context=hist_context
            )

            # Krishna OS Mathematical Engine
            author_id = info.get("discord_id", 0)
            score_data = compute_daily_score(
                task_evaluations=ai_eval.get("task_evaluations", []),
                reactions=reactions,
                author_discord_id=author_id,
                spontaneous_bonus=ai_eval.get("spontaneous_bonus", 0.0),
            )

            final_score = score_data["final_score"]
            leaderboard_ranks.append((key, info["display_name"], info["role"], final_score))

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

            task_lines = []
            for t in score_data.get("task_breakdown", []):
                task_desc = t.get("task", "Task")
                if len(task_desc) > 38:
                    task_desc = task_desc[:35] + "..."
                comp_pct = int(t.get("completion", 0.0) * 100)
                w = int(t.get("complexity", 3))
                pts = t.get("task_points", 0.0)
                task_lines.append(f"• **{task_desc}** (Size: {w}/5, {comp_pct}% done) → **+{pts:.1f} pts**")

            tasks_str = "\n".join(task_lines) if task_lines else "• *No tasks finished today*"
            bonus_pts = score_data.get("bonus_points", 0.0)
            bonus_reason = ai_eval.get("spontaneous_reason", "")
            bonus_suffix = f" *({bonus_reason[:35]})*" if bonus_reason else ""
            bonus_str = f"• **Bonus Points:** +{bonus_pts:.1f} pts{bonus_suffix}"

            raw_sum = score_data.get("raw_task_sum", 0.0)
            peer_mult = score_data.get("peer_multiplier", 1.0)
            formula_str = f"📐 *How it's counted: ({raw_sum:.1f} task pts × {peer_mult}x team boost) + {bonus_pts:.1f} bonus = {final_score:.1f} pts*"

            m_q = ai_eval.get("mentor_question", "")
            m_q_section = f"\n\n❓ **Question for Tomorrow:** *\"{m_q}\"*" if m_q else ""

            val = (
                f"📊 **Score Details:**\n"
                f"{tasks_str}\n"
                f"{bonus_str}\n"
                f"👍 **Team Boost:** {peer_mult}x (✅ {score_data['emoji_counts']['✅']} | 🔥 {score_data['emoji_counts']['🔥']} | ⚠️ {score_data['emoji_counts']['⚠️']})\n"
                f"{formula_str}\n\n"
                f"🏆 **What went great:** {ai_eval.get('praise_text', 'Good steady work today.')}\n\n"
                f"💡 **Advice from Peter:** {ai_eval.get('feedback_text', 'Keep building and moving fast.')}"
                f"{m_q_section}"
            )
            if len(val) > 1024:
                val = val[:1020] + "..."

            summary_fields.append({
                "name": f"{info['display_name']} ({info['role']}) — {final_score:.1f} pts",
                "value": val,
                "inline": False,
            })
            await asyncio.sleep(1.0)

        # Sort leaderboard
        leaderboard_ranks.sort(key=lambda x: x[3], reverse=True)
        top_name = leaderboard_ranks[0][1] if leaderboard_ranks else "Team"

        embed = discord.Embed(
            title=f"🌆 8:00 PM Daily Scorecard • {today_str}",
            description=f"MVP of the Day: 👑 **{top_name}**\nHere is how everyone did today!",
            color=COLOR_SUCCESS,
        )
        for field in summary_fields:
            embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])

        embed.set_footer(text="Calcrum Review Bot • Scores are saved automatically every night")
        await channel.send(embed=embed)

    async def run_weekly_swot(self):
        """Aggregate 7-day data and post Executive SWOT to #leadership."""
        channel = self.bot.get_channel(LEADERSHIP_CHANNEL_ID) or self.bot.get_channel(PRIMARY_GOALS_CHANNEL_ID)
        if not channel:
            return

        end_date = datetime.now(TIMEZONE).date()
        start_date = end_date - timedelta(days=6)

        weekly_payload = {}
        for key in FOUNDERS.keys():
            scores = await get_scores_in_date_range(key, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            weekly_payload[key] = {
                "name": FOUNDERS[key]["display_name"],
                "role": FOUNDERS[key]["role"],
                "total_points": sum([s["final_score"] for s in scores]),
                "avg_daily_points": sum([s["final_score"] for s in scores]) / max(1, len(scores)),
                "days_active": len(scores),
            }

        swot_data = await generate_weekly_swot_with_ai(weekly_payload)

        embed = discord.Embed(
            title="📊 Weekly Strategic Executive SWOT Report",
            description=swot_data.get("overall_summary", "Weekly sprint summary."),
            color=COLOR_SWOT,
        )

        founder_swots = swot_data.get("founder_swot", {})
        for key, data in founder_swots.items():
            name = FOUNDERS.get(key, {}).get("display_name", key.capitalize())
            role = FOUNDERS.get(key, {}).get("role", "")
            pts = weekly_payload.get(key, {}).get("total_points", 0.0)

            embed.add_field(
                name=f"{name} ({role}) — Total Weekly: {pts:.1f} pts",
                value=(
                    f"💪 **Strengths:** {data.get('strengths', 'High output')}\n"
                    f"⚠️ **Weaknesses:** {data.get('weaknesses', 'None flagged')}\n"
                    f"🚀 **Opportunities:** {data.get('opportunities', 'Expansion')}\n"
                    f"🛑 **Threats:** {data.get('threats', 'Burnout risk')}"
                ),
                inline=False
            )

        await channel.send(embed=embed)

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

        # Sum monthly scores for Swarit (CTO) and Rahul (COO)
        swarit_scores = await get_scores_in_date_range("swarit", start_date, end_date)
        rahul_scores = await get_scores_in_date_range("rahul", start_date, end_date)

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
