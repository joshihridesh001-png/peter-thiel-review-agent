"""
Async SQLite Database Manager using aiosqlite.
Manages connections, schema initialization, and initial founder seed data.
"""

import aiosqlite
from config import DB_PATH, FOUNDERS


from contextlib import asynccontextmanager

USERS_TABLE_SQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_key TEXT UNIQUE NOT NULL,
    discord_id INTEGER UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    vested_equity REAL NOT NULL DEFAULT 0.0,
    unvested_target REAL NOT NULL DEFAULT 0.0,
    earned_equity REAL NOT NULL DEFAULT 0.0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DROPPED_ROSTER_KEYS = ("riya",)

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

        # 1. Users Table. discord_id may be NULL when we do not know it yet.
        await db.execute("CREATE TABLE IF NOT EXISTS " + USERS_TABLE_SQL.split("CREATE TABLE ", 1)[1])

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

        await migrate_users_discord_id(db)
        await remove_dropped_roster(db)
        await seed_users(db)

        await db.commit()


async def migrate_users_discord_id(db) -> None:
    """Rebuild users so an unknown Discord id is NULL, not a shared 0."""
    cursor = await db.execute("PRAGMA table_info(users)")
    columns = await cursor.fetchall()
    discord_col = next((col for col in columns if col[1] == "discord_id"), None)
    if discord_col is None or not discord_col[3]:
        return

    # foreign_keys cannot change inside an open transaction. Commit first.
    await db.commit()
    await db.execute("PRAGMA foreign_keys = OFF;")
    # Keep other tables pointing at "users" while this table is rebuilt.
    await db.execute("PRAGMA legacy_alter_table = ON;")
    await db.execute("ALTER TABLE users RENAME TO users_old;")
    await db.execute(USERS_TABLE_SQL)
    await db.execute("""
        INSERT INTO users (
            id, founder_key, discord_id, display_name, role,
            vested_equity, unvested_target, earned_equity,
            current_streak, longest_streak, created_at
        )
        SELECT
            id, founder_key, NULLIF(discord_id, 0), display_name, role,
            vested_equity, unvested_target, earned_equity,
            current_streak, longest_streak, created_at
        FROM users_old;
    """)
    await db.execute("DROP TABLE users_old;")
    seq_table = await db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
    if await seq_table.fetchone():
        max_row = await (await db.execute("SELECT COALESCE(MAX(id), 0) FROM users")).fetchone()
        await db.execute("DELETE FROM sqlite_sequence WHERE name IN ('users', 'users_old')")
        await db.execute(
            "INSERT INTO sqlite_sequence (name, seq) VALUES ('users', ?)",
            (max_row[0],),
        )
    await db.commit()
    await db.execute("PRAGMA legacy_alter_table = OFF;")
    await db.execute("PRAGMA foreign_keys = ON;")


async def remove_dropped_roster(db) -> None:
    """Drop people who are no longer on the roster. Riya has no score history."""
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    tables = {row[0] for row in await cursor.fetchall()}
    for key in DROPPED_ROSTER_KEYS:
        for table in ("goals", "updates", "daily_scores", "monthly_equity_ledger"):
            if table in tables:
                await db.execute(f"DELETE FROM {table} WHERE founder_key = ?", (key,))
        if "users" in tables:
            await db.execute("DELETE FROM users WHERE founder_key = ?", (key,))


async def seed_users(db) -> None:
    """Insert the roster. A null id does not wipe a Discord id already saved by /set-role."""
    for key, data in FOUNDERS.items():
        await db.execute("""
        INSERT INTO users (founder_key, discord_id, display_name, role, vested_equity, unvested_target, earned_equity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(founder_key) DO UPDATE SET
            discord_id = COALESCE(excluded.discord_id, users.discord_id),
            display_name = excluded.display_name,
            role = excluded.role;
        """, (
            key,
            data.get("discord_id"),
            data["display_name"],
            data["role"],
            data["vested_equity"],
            data["unvested_target"],
            data["vested_equity"],
        ))
