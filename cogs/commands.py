"""
Discord Cog: Commands
Provides slash commands and prefix commands for founders:
/set-role, /goals, /score, /leaderboard, /equity, /swot, /calculate-today, /confirm-equity
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional, Literal

from config import FOUNDERS
from database.models import (
    update_founder_discord_id,
    get_all_users,
    get_user_by_discord_id,
    get_goals_for_date,
    get_daily_score,
    get_latest_equity_status,
    ratify_monthly_ledger,
)
from skills_bridge.discord_bridge import (
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_EQUITY,
    COLOR_SWOT,
    COLOR_WARNING,
)


class CommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set-role", description="Link a founder role to a Discord member")
    @app_commands.describe(
        role="Select the founder role",
        member="The Discord member to assign"
    )
    async def set_role(
        self,
        interaction: discord.Interaction,
        role: Literal["hridesh", "swarit", "rahul"],
        member: discord.Member,
    ):
        """Associate Discord User ID with founder key."""
        await update_founder_discord_id(role, member.id)
        display_name = FOUNDERS[role]["display_name"]
        founder_role = FOUNDERS[role]["role"]
        embed = discord.Embed(
            title="✅ Founder Identity Linked",
            description=f"Assigned **{member.mention}** as **{display_name} ({founder_role})** in the Krishna Engineering OS.",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="goals", description="View locked daily commitments")
    @app_commands.describe(
        founder="The founder whose goals you want to inspect",
        date="Date in YYYY-MM-DD format (defaults to today)"
    )
    async def view_goals(
        self,
        interaction: discord.Interaction,
        founder: Literal["hridesh", "swarit", "rahul"],
        date: Optional[str] = None,
    ):
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        record = await get_goals_for_date(founder, target_date)
        display_name = FOUNDERS[founder]["display_name"]

        if not record:
            embed = discord.Embed(
                title=f"📋 No Goals Found for {display_name}",
                description=f"No commitments locked in for date **{target_date}**.",
                color=COLOR_WARNING
            )
            await interaction.response.send_message(embed=embed)
            return

        tasks_list = record.get("parsed_goals", [])
        task_blocks = []
        for i, t in enumerate(tasks_list, start=1):
            task_title = t.get("task", "Commitment")
            size = t.get("complexity", 3)
            reason = t.get("score_reason", t.get("dharma_reason", "Important task for your role"))
            block = f"**{i}. {task_title}**\n↳ **Size:** `{size}/5`\n💬 *Why: {reason}*"
            task_blocks.append(block)

        tasks_text = "\n\n".join(task_blocks)
        desc = (
            f"Goals for: **{target_date}** • **{len(tasks_list)} Commitments**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{tasks_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        embed = discord.Embed(
            title=f"🎯 Planned Goals: {display_name} • {target_date}",
            description=desc,
            color=COLOR_PRIMARY
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="score", description="Check daily score and breakdown")
    @app_commands.describe(
        founder="The founder whose score to check",
        date="Date in YYYY-MM-DD format (defaults to today)"
    )
    async def view_score(
        self,
        interaction: discord.Interaction,
        founder: Literal["hridesh", "swarit", "rahul"],
        date: Optional[str] = None,
    ):
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        record = await get_daily_score(founder, target_date)
        display_name = FOUNDERS[founder]["display_name"]

        if not record:
            embed = discord.Embed(
                title=f"⏳ Score Pending for {display_name}",
                description=f"No score computed yet for **{target_date}**. Scores are calculated at 8:00 PM daily.",
                color=COLOR_WARNING
            )
            await interaction.response.send_message(embed=embed)
            return

        breakdown = record["breakdown_json"]
        task_lines = []
        for t in breakdown.get("task_breakdown", []):
            task_desc = t.get("task", "Task")
            if len(task_desc) > 38:
                task_desc = task_desc[:35] + "..."
            comp_pct = int(t.get("completion", 0.0) * 100)
            w = int(t.get("complexity", 3))
            pts = t.get("task_points", 0.0)
            reason = t.get("score_reason", "").strip()
            entry = f"• **{task_desc}** (Size: {w}/5, {comp_pct}% done) → **+{pts:.1f} pts**"
            if reason:
                if len(reason) > 75:
                    reason = reason[:72] + "..."
                entry += f"\n  💬 *Why: {reason}*"
            task_lines.append(entry)

        tasks_str = "\n".join(task_lines) if task_lines else "• *No tasks recorded*"

        embed = discord.Embed(
            title=f"📊 Score Report: {display_name} • {target_date}",
            description=(
                f"**Total Score:** **{record['final_score']:.2f} pts**\n\n"
                f"**Tasks Evaluated:**\n{tasks_str}\n\n"
                f"• **Team Boost:** {breakdown.get('peer_multiplier', 1.0)}x "
                f"(✅ {breakdown.get('emoji_counts', {}).get('✅', 0)} | 🔥 {breakdown.get('emoji_counts', {}).get('🔥', 0)} | ⚠️ {breakdown.get('emoji_counts', {}).get('⚠️', 0)})\n"
                f"• **Bonus Points:** +{breakdown.get('bonus_points', 0.0):.2f}\n\n"
                f"🏆 **What went great:** {record.get('praise_text', 'N/A')}\n"
                f"💡 **Advice from Peter:** {record.get('feedback_text', 'N/A')}"
            ),
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="equity", description="View the current Cap Table and 24-Month Earnout status")
    async def view_equity(self, interaction: discord.Interaction):
        standings = await get_latest_equity_status()
        embed = discord.Embed(
            title="🏛️ Cap Table & Dynamic Earnout Standing",
            description="24-Month Slicing Pie Dynamic Earnout • Monthly tranche release: ~2.2917%",
            color=COLOR_EQUITY
        )

        for s in standings:
            key = s["founder_key"]
            name = s["display_name"]
            role = s["role"]
            vested = s["vested_equity"]
            target = s["unvested_target"]
            earned = s["earned_equity"]
            streak = s["current_streak"]

            if role == "CEO":
                val = f"• **Status:** Fully Vested Fixed Baseline\n• **Ownership:** **{vested:.3f}%**\n• **Streak:** 🔥 {streak} days"
            else:
                val = (
                    f"• **Target Allocation:** {target:.1f}%\n"
                    f"• **Currently Earned:** **{earned:.4f}%**\n"
                    f"• **Vesting Speed:** Dynamic Month-by-Month Score Ratio\n"
                    f"• **Streak:** 🔥 {streak} days"
                )

            embed.add_field(name=f"{name} ({role})", value=val, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View founder performance and execution streaks")
    async def leaderboard(self, interaction: discord.Interaction):
        users = await get_all_users()
        embed = discord.Embed(
            title="🏆 Founder Execution Leaderboard",
            description="Tracking daily consistency, role throughput, and execution momentum.",
            color=COLOR_PRIMARY
        )
        for u in users:
            embed.add_field(
                name=f"{u['display_name']} ({u['role']})",
                value=f"• Current Streak: 🔥 **{u['current_streak']} days**\n• Record Streak: 🌟 {u['longest_streak']} days",
                inline=True
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="calculate-today", description="Force-run 8:00 PM scoring calculation right now")
    async def calculate_today(self, interaction: discord.Interaction):
        """Allows testing or manual calculation."""
        await interaction.response.defer()
        scheduler_cog = self.bot.get_cog("SchedulerCog")
        if not scheduler_cog:
            await interaction.followup.send("Scheduler cog not loaded.")
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        await scheduler_cog.run_daily_scoring(today_str)
        await interaction.followup.send(f"✅ Executed scoring calculation for **{today_str}**.")

    @app_commands.command(name="prompt-goals", description="Trigger the 9:00 PM goal callout right now")
    async def prompt_goals(self, interaction: discord.Interaction):
        """Allows testing goal callout embed."""
        await interaction.response.defer()
        scheduler_cog = self.bot.get_cog("SchedulerCog")
        if not scheduler_cog:
            await interaction.followup.send("Scheduler cog not loaded.")
            return

        await scheduler_cog.run_daily_goals_callout()
        await interaction.followup.send("✅ Sent 9:00 PM goal declaration callout.")

    @app_commands.command(name="confirm-equity", description="Ratify a monthly equity ledger tranche")
    @app_commands.describe(month_index="The month number to ratify (1 to 24)")
    async def confirm_equity(self, interaction: discord.Interaction, month_index: int):
        """Triple-confirmation governance gate."""
        await ratify_monthly_ledger(month_index)
        embed = discord.Embed(
            title="✅ Monthly Equity Ledger Ratified",
            description=f"Month **{month_index}** equity allocations have been verified and permanently committed to the cap table.",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sync-updates", description="Scan and backfill recent GitHub PRs, commits, and chat updates")
    @app_commands.describe(limit="Number of recent messages to inspect per channel (default 100)")
    async def sync_updates(self, interaction: discord.Interaction, limit: Optional[int] = 100):
        """Scan channels and backfill any missed GitHub PRs/commits or chat updates."""
        await interaction.response.defer()
        tracker_cog = self.bot.get_cog("TrackerCog")
        if not tracker_cog:
            await interaction.followup.send("TrackerCog not loaded.")
            return

        lim = max(10, min(200, limit or 100))
        count = await tracker_cog.sync_recent_channel_updates(limit=lim)
        embed = discord.Embed(
            title="🔄 Channel History Synchronized",
            description=f"Scanned monitored channels ({lim} messages each) and backfilled **{count}** updates (including GitHub PRs & commits) into the founder ledger.",
            color=COLOR_SUCCESS
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsCog(bot))
