"""Roster rules: unknown Discord ids, Riya removed, reps scored off the cap table."""

import unittest

import aiosqlite

from cogs.scheduler import collect_score_cards, rep_beat_founders_line
from database.db import migrate_users_discord_id, remove_dropped_roster, seed_users


OLD_USERS_SQL = """
CREATE TABLE users (
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
"""


class TestNullableDiscordId(unittest.IsolatedAsyncioTestCase):
    async def test_zero_becomes_null_and_a_second_unknown_id_inserts(self):
        async with aiosqlite.connect(":memory:") as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(OLD_USERS_SQL)
            await db.execute("""
                CREATE TABLE goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    founder_key TEXT NOT NULL,
                    goal_date TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    parsed_goals TEXT NOT NULL,
                    FOREIGN KEY (founder_key) REFERENCES users (founder_key)
                );
            """)
            await db.execute(
                "INSERT INTO users (founder_key, discord_id, display_name, role, vested_equity, unvested_target, earned_equity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("hridesh", 1159464740788109312, "Hridesh", "CEO", 45.0, 0.0, 45.0),
            )
            await db.execute(
                "INSERT INTO users (founder_key, discord_id, display_name, role, vested_equity, unvested_target, earned_equity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("yash", 0, "Yash", "Sales", 0.0, 0.0, 0.0),
            )
            await db.execute(
                "INSERT INTO users (founder_key, discord_id, display_name, role, vested_equity, unvested_target, earned_equity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("riya", 1458478666118987787, "Riya", "CMO", 0.0, 0.0, 0.0),
            )
            await db.execute(
                "INSERT INTO goals (founder_key, goal_date, raw_text, parsed_goals) VALUES (?, ?, ?, ?)",
                ("riya", "2026-10-01", "old", "[]"),
            )
            await db.commit()

            await migrate_users_discord_id(db)
            yash = await (await db.execute("SELECT discord_id FROM users WHERE founder_key = 'yash'")).fetchone()
            hridesh = await (await db.execute("SELECT discord_id FROM users WHERE founder_key = 'hridesh'")).fetchone()
            self.assertIsNone(yash[0])
            self.assertEqual(hridesh[0], 1159464740788109312)

            await remove_dropped_roster(db)
            riya = await (await db.execute("SELECT 1 FROM users WHERE founder_key = 'riya'")).fetchone()
            riya_goal = await (await db.execute("SELECT 1 FROM goals WHERE founder_key = 'riya'")).fetchone()
            self.assertIsNone(riya)
            self.assertIsNone(riya_goal)

            await seed_users(db)
            await db.commit()
            rows = await (await db.execute(
                "SELECT founder_key, discord_id FROM users WHERE founder_key IN ('yash', 'shivang') ORDER BY founder_key"
            )).fetchall()
            self.assertEqual([row[0] for row in rows], ["shivang", "yash"])
            self.assertEqual(rows[0][1], 665573807494529065)
            self.assertEqual(rows[1][1], 923595474454323281)

            from config import FOUNDERS
            saved = FOUNDERS["yash"]["discord_id"]
            FOUNDERS["yash"]["discord_id"] = None
            try:
                await db.execute("UPDATE users SET discord_id = ? WHERE founder_key = 'yash'", (4242,))
                await seed_users(db)
                await db.commit()
                kept = await (await db.execute("SELECT discord_id FROM users WHERE founder_key = 'yash'")).fetchone()
                self.assertEqual(kept[0], 4242)
            finally:
                FOUNDERS["yash"]["discord_id"] = saved

            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(
                "INSERT INTO goals (founder_key, goal_date, raw_text, parsed_goals) VALUES (?, ?, ?, ?)",
                ("hridesh", "2026-10-30", "still linked", "[]"),
            )
            await db.commit()


class TestScorecardRoster(unittest.IsolatedAsyncioTestCase):
    async def test_one_failure_keeps_the_other_cards(self):
        people = [
            ("hridesh", {"display_name": "Hridesh", "role": "CEO"}),
            ("yash", {"display_name": "Yash", "role": "Sales"}),
        ]

        async def score_one(key, info):
            if key == "yash":
                raise RuntimeError("missing row")
            return (
                {"founder_key": key, "name": info["display_name"], "final_score": 3.0, "description": "ok"},
                (key, info["display_name"], info["role"], 3.0),
            )

        cards, ranks = await collect_score_cards(people, score_one)
        self.assertEqual([card["founder_key"] for card in cards], ["hridesh", "yash"])
        self.assertFalse(cards[0].get("failed"))
        self.assertTrue(cards[1]["failed"])
        self.assertIn("did not save", cards[1]["description"])
        self.assertEqual(ranks[1][3], 0.0)

    def test_rep_above_every_founder_is_a_sentence_only(self):
        quiet = rep_beat_founders_line([("hridesh", 10.0), ("swarit", 8.0), ("rahul", 9.0), ("yash", 4.0)])
        self.assertEqual(quiet, "")
        loud = rep_beat_founders_line([
            ("hridesh", 10.0),
            ("swarit", 8.0),
            ("rahul", 9.0),
            ("yash", 14.2),
            ("shivang", 11.1),
        ])
        self.assertIn("Yash", loud)
        self.assertIn("4.2", loud)
        self.assertIn("Shivang", loud)
        self.assertIn("1.1", loud)
