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

from config import FOUNDERS, PRIMARY_GOALS_CHANNEL_ID, LEADERSHIP_CHANNEL_ID
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
        desc = "\n".join([
            f"• **{t.get('task')}** (Weight: {t.get('complexity')}/5 | Dharma: {t.get('dharma_multiplier')}x)\n  *Reason: {t.get('dharma_reason', 'N/A')}*"
            for t in tasks_list
        ])

        embed = discord.Embed(
            title=f"🎯 Locked Goals: {display_name} • {target_date}",
            description=desc,
            color=COLOR_PRIMARY
        )
        embed.set_footer(text=f"Raw text: {record.get('raw_text')[:100]}...")
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
        embed = discord.Embed(
            title=f"📊 Score Report: {display_name} • {target_date}",
            description=(
                f"**Final Krishna OS Score:** **{record['final_score']:.2f} pts**\n\n"
                f"• **Raw Task Sum:** {breakdown.get('raw_task_sum', 0.0):.2f}\n"
                f"• **Peer Multiplier ($M_{{peer}}$):** {breakdown.get('peer_multiplier', 1.0)}x "
                f"(✅ {breakdown.get('emoji_counts', {}).get('✅', 0)} | 🔥 {breakdown.get('emoji_counts', {}).get('🔥', 0)} | ⚠️ {breakdown.get('emoji_counts', {}).get('⚠️', 0)})\n"
                f"• **Spontaneous Bonus ($I_{{bonus}}$):** +{breakdown.get('bonus_points', 0.0):.2f}\n\n"
                f"🏆 **Win of the Day:** {record.get('praise_text', 'N/A')}\n"
                f"⚙️ **Systems Feedback:** {record.get('feedback_text', 'N/A')}"
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


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsCog(bot))
