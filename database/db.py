"""
Async SQLite Database Manager using aiosqlite.
Manages connections, schema initialization, and initial founder seed data.
"""

import aiosqlite
from typing import Optional
from config import DB_PATH, FOUNDERS


from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    """Yield an open aiosqlite connection with foreign keys and WAL enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA journal_mode = WAL;")
        db.row_factory = aiosqlite.Row
        yield db


async def init_db() -> None:
    """Create all required tables and seed default founder rows if not present."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA journal_mode = WAL;")

        # 1. Users Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            founder_key TEXT UNIQUE NOT NULL,
            discord_id INTEGER UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            vested_equity REAL NOT NULL DEFAULT 0.0,
            unvested_target REAL NOT NULL DEFAULT 0.0,
            earned_equity REAL NOT NULL DEFAULT 0.0,
            current_streak INTEGER NOT NULL DEFAULT 0,
            longest_streak INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Goals Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            founder_key TEXT NOT NULL,
            goal_date TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            parsed_goals TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'locked',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (founder_key) REFERENCES users (founder_key)
        );
        """)

        # 3. Channel Updates Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE NOT NULL,
            founder_key TEXT NOT NULL,
            discord_user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            matched_goal_id INTEGER NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (founder_key) REFERENCES users (founder_key)
        );
        """)

        # 4. Peer Reactions Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            reactor_discord_id INTEGER NOT NULL,
            reactor_founder_key TEXT NOT NULL,
            emoji TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(message_id, reactor_discord_id, emoji)
        );
        """)

        # 5. Daily Scores Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS daily_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            founder_key TEXT NOT NULL,
            score_date TEXT NOT NULL,
            completion_score REAL NOT NULL,
            complexity_score REAL NOT NULL,
            dharma_score REAL NOT NULL,
            peer_multiplier REAL NOT NULL,
            bonus_points REAL NOT NULL DEFAULT 0.0,
            final_score REAL NOT NULL,
            breakdown_json TEXT NOT NULL,
            praise_text TEXT,
            feedback_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(founder_key, score_date),
            FOREIGN KEY (founder_key) REFERENCES users (founder_key)
        );
        """)

        # 6. Monthly Dynamic Earnout Ledger Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS monthly_equity_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_index INTEGER NOT NULL,
            year_month TEXT NOT NULL,
            founder_key TEXT NOT NULL,
            total_monthly_score REAL NOT NULL,
            score_ratio REAL NOT NULL,
            equity_awarded REAL NOT NULL,
            cumulative_equity REAL NOT NULL,
            treasury_diverted REAL NOT NULL DEFAULT 0.0,
            is_ratified INTEGER NOT NULL DEFAULT 0,
            ratified_at TIMESTAMP NULL,
            UNIQUE(month_index, founder_key),
            FOREIGN KEY (founder_key) REFERENCES users (founder_key)
        );
        """)

        # 7. System Audit & Observability Log Table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS system_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Seed or sync founders into users table
        for key, data in FOUNDERS.items():
            await db.execute("""
            INSERT INTO users (founder_key, discord_id, display_name, role, vested_equity, unvested_target, earned_equity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(founder_key) DO UPDATE SET
                discord_id = excluded.discord_id,
                display_name = excluded.display_name,
                role = excluded.role;
            """, (
                key,
                data["discord_id"],
                data["display_name"],
                data["role"],
                data["vested_equity"],
                data["unvested_target"],
                data["vested_equity"]  # CEO starts with 45% earned/vested, CTO/COO start at 0.0
            ))

        await db.commit()
