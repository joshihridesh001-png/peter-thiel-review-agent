"""
Database Access Layer (DAO) for the Founder Operations Bot.
Provides high-level async functions to interact with the SQLite database.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from database.db import get_db


async def get_user_by_discord_id(discord_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user record by Discord user ID."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM users WHERE discord_id = ?;", (discord_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_key(founder_key: str) -> Optional[Dict[str, Any]]:
    """Fetch user record by founder key (e.g. 'hridesh', 'swarit', 'rahul')."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM users WHERE founder_key = ?;", (founder_key.lower(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_users() -> List[Dict[str, Any]]:
    """Fetch all founder records."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM users ORDER BY id ASC;") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_founder_discord_id(founder_key: str, discord_id: int) -> None:
    """Associate or update a founder's real Discord ID."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET discord_id = ? WHERE founder_key = ?;",
            (discord_id, founder_key.lower())
        )
        await db.commit()


async def save_daily_goals(founder_key: str, goal_date: str, raw_text: str, parsed_goals: List[Dict[str, Any]]) -> int:
    """Save parsed daily commitments locked in at 9:00 PM."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO goals (founder_key, goal_date, raw_text, parsed_goals, status)
            VALUES (?, ?, ?, ?, 'locked');
        """, (founder_key, goal_date, raw_text, json.dumps(parsed_goals)))
        await db.commit()
        return cursor.lastrowid or 0


async def get_goals_for_date(founder_key: str, goal_date: str) -> Optional[Dict[str, Any]]:
    """Retrieve locked goals for a specific founder and date."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM goals WHERE founder_key = ? AND goal_date = ? ORDER BY id DESC LIMIT 1;",
            (founder_key, goal_date)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["parsed_goals"] = json.loads(res["parsed_goals"])
            return res


async def save_channel_update(
    message_id: int,
    founder_key: str,
    discord_user_id: int,
    channel_id: int,
    content: str,
    timestamp: str,
) -> int:
    """Log an ambient daytime progress update posted in a monitored channel."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT OR IGNORE INTO updates (message_id, founder_key, discord_user_id, channel_id, content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (message_id, founder_key, discord_user_id, channel_id, content, timestamp))
        await db.commit()
        return cursor.lastrowid or 0


async def get_updates_for_date_range(founder_key: str, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
    """Retrieve all updates logged by a founder between two ISO timestamps."""
    async with get_db() as db:
        async with db.execute("""
            SELECT * FROM updates 
            WHERE founder_key = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC;
        """, (founder_key, start_iso, end_iso)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def record_peer_reaction(
    message_id: int,
    reactor_discord_id: int,
    reactor_founder_key: str,
    emoji: str,
    weight: float,
) -> None:
    """Record a co-founder's emoji verification or concern on an update message."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO reactions (message_id, reactor_discord_id, reactor_founder_key, emoji, weight)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(message_id, reactor_discord_id, emoji) 
            DO UPDATE SET weight = excluded.weight;
        """, (message_id, reactor_discord_id, reactor_founder_key, emoji, weight))
        await db.commit()


async def remove_peer_reaction(message_id: int, reactor_discord_id: int, emoji: str) -> None:
    """Remove a reaction when unreacted in Discord."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM reactions WHERE message_id = ? AND reactor_discord_id = ? AND emoji = ?;",
            (message_id, reactor_discord_id, emoji)
        )
        await db.commit()


async def get_reactions_for_messages(message_ids: List[int]) -> List[Dict[str, Any]]:
    """Retrieve all reactions associated with a list of update message IDs."""
    if not message_ids:
        return []
    placeholders = ",".join(["?"] * len(message_ids))
    async with get_db() as db:
        async with db.execute(
            f"SELECT * FROM reactions WHERE message_id IN ({placeholders});",
            message_ids
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def save_daily_score(
    founder_key: str,
    score_date: str,
    completion_score: float,
    complexity_score: float,
    dharma_score: float,
    peer_multiplier: float,
    bonus_points: float,
    final_score: float,
    breakdown_json: Dict[str, Any],
    praise_text: str = "",
    feedback_text: str = "",
) -> None:
    """Record or update calculated daily scores and feedback at 8:00 PM."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO daily_scores (
                founder_key, score_date, completion_score, complexity_score,
                dharma_score, peer_multiplier, bonus_points, final_score,
                breakdown_json, praise_text, feedback_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(founder_key, score_date) DO UPDATE SET
                completion_score = excluded.completion_score,
                complexity_score = excluded.complexity_score,
                dharma_score = excluded.dharma_score,
                peer_multiplier = excluded.peer_multiplier,
                bonus_points = excluded.bonus_points,
                final_score = excluded.final_score,
                breakdown_json = excluded.breakdown_json,
                praise_text = excluded.praise_text,
                feedback_text = excluded.feedback_text;
        """, (
            founder_key, score_date, completion_score, complexity_score,
            dharma_score, peer_multiplier, bonus_points, final_score,
            json.dumps(breakdown_json), praise_text, feedback_text
        ))

        # Update streak counter: if final_score >= 10, increment current_streak
        if final_score >= 10.0:
            await db.execute("""
                UPDATE users 
                SET current_streak = current_streak + 1,
                    longest_streak = MAX(longest_streak, current_streak + 1)
                WHERE founder_key = ?;
            """, (founder_key,))
        else:
            await db.execute("UPDATE users SET current_streak = 0 WHERE founder_key = ?;", (founder_key,))

        await db.commit()


async def get_daily_score(founder_key: str, score_date: str) -> Optional[Dict[str, Any]]:
    """Retrieve daily score for a founder on a given date."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM daily_scores WHERE founder_key = ? AND score_date = ?;",
            (founder_key, score_date)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["breakdown_json"] = json.loads(res["breakdown_json"])
            return res


async def get_scores_in_date_range(founder_key: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Get all daily scores for a founder between start_date and end_date (inclusive)."""
    async with get_db() as db:
        async with db.execute("""
            SELECT * FROM daily_scores 
            WHERE founder_key = ? AND score_date >= ? AND score_date <= ?
            ORDER BY score_date ASC;
        """, (founder_key, start_date, end_date)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["breakdown_json"] = json.loads(item["breakdown_json"])
                results.append(item)
            return results


async def record_monthly_equity_tranche(
    month_index: int,
    year_month: str,
    founder_key: str,
    total_monthly_score: float,
    score_ratio: float,
    equity_awarded: float,
    cumulative_equity: float,
    treasury_diverted: float = 0.0,
    is_ratified: int = 0,
) -> None:
    """Save or update a monthly dynamic earnout equity ledger record."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO monthly_equity_ledger (
                month_index, year_month, founder_key, total_monthly_score,
                score_ratio, equity_awarded, cumulative_equity, treasury_diverted, is_ratified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(month_index, founder_key) DO UPDATE SET
                total_monthly_score = excluded.total_monthly_score,
                score_ratio = excluded.score_ratio,
                equity_awarded = excluded.equity_awarded,
                cumulative_equity = excluded.cumulative_equity,
                treasury_diverted = excluded.treasury_diverted,
                is_ratified = excluded.is_ratified;
        """, (
            month_index, year_month, founder_key, total_monthly_score,
            score_ratio, equity_awarded, cumulative_equity, treasury_diverted, is_ratified
        ))
        await db.commit()


async def ratify_monthly_ledger(month_index: int) -> None:
    """Mark a monthly equity ledger tranche as verified & ratified by all founders."""
    now_iso = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute("""
            UPDATE monthly_equity_ledger 
            SET is_ratified = 1, ratified_at = ?
            WHERE month_index = ?;
        """, (now_iso, month_index))

        # Update the users table cumulative earned_equity from this ratified ledger
        async with db.execute(
            "SELECT founder_key, cumulative_equity FROM monthly_equity_ledger WHERE month_index = ?;",
            (month_index,)
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                await db.execute(
                    "UPDATE users SET earned_equity = ? WHERE founder_key = ?;",
                    (r["cumulative_equity"], r["founder_key"])
                )

        await db.commit()


async def get_latest_equity_status() -> List[Dict[str, Any]]:
    """Fetch current equity standings for all founders."""
    async with get_db() as db:
        async with db.execute("""
            SELECT founder_key, display_name, role, vested_equity, unvested_target, earned_equity, current_streak 
            FROM users ORDER BY vested_equity DESC, earned_equity DESC;
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_recent_founder_context(days: int = 3) -> str:
    """
    Aggregate recent score summaries, praise, and locked goals to provide
    the AI mentor with continuous memory of who worked on what.
    """
    async with get_db() as db:
        async with db.execute("""
            SELECT founder_key, score_date, final_score, praise_text, feedback_text
            FROM daily_scores
            ORDER BY score_date DESC, id DESC
            LIMIT ?;
        """, (days * 3,)) as cursor:
            score_rows = await cursor.fetchall()

    if not score_rows:
        return "No recent daily score logs found in the ledger."

    lines = ["Recent Historical Scores & Completed Milestones:"]
    for r in score_rows:
        f_name = r["founder_key"].capitalize()
        lines.append(
            f"• [{r['score_date']}] {f_name}: Score {r['final_score']} pts | Past Milestone: {r['praise_text'][:100]}"
        )
    return "\n".join(lines)
