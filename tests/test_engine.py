"""
Automated Test Suite for the Krishna Engineering OS Founder Operations Bot.
Verifies scoring invariants, peer reaction clamping, dynamic 24-month earnout math,
safety floor treasury diversion, and database persistence.
"""

import asyncio
import os
import unittest
from datetime import datetime

from config import (
    TOTAL_UNVESTED_POOL,
    VESTING_HORIZON_MONTHS,
    MONTHLY_TRANCHE_EQUITY,
    TARGET_UNVESTED_WEIGHTS,
    FOUNDERS,
)
from engine.scoring import compute_daily_score, calculate_peer_multiplier
from engine.equity import compute_monthly_equity_split
from engine.evaluator import parse_daily_goals_with_ai, evaluate_daily_execution_with_ai
from database.db import init_db
from database.models import (
    get_all_users,
    save_daily_goals,
    get_goals_for_date,
    save_channel_update,
    get_updates_for_date_range,
    record_peer_reaction,
    get_reactions_for_messages,
    save_daily_score,
    get_daily_score,
    record_monthly_equity_tranche,
    ratify_monthly_ledger,
)


class TestScoringEngine(unittest.TestCase):
    def test_peer_multiplier_clamping_and_self_reaction_filter(self):
        author_id = 11111

        # Case 1: Reactions containing self-reaction (should be filtered)
        reactions = [
            {"reactor_discord_id": author_id, "emoji": "🔥"},  # Self reaction!
            {"reactor_discord_id": 22222, "emoji": "✅"},      # +0.05
            {"reactor_discord_id": 33333, "emoji": "🔥"},      # +0.10
        ]
        multiplier, counts = calculate_peer_multiplier(reactions, author_id)
        # Expected: 1.0 + 0.05 + 0.10 = 1.15
        self.assertEqual(multiplier, 1.15)
        self.assertEqual(counts["✅"], 1)
        self.assertEqual(counts["🔥"], 1)

        # Case 2: Extreme positive reactions clamped at 1.2
        many_fire = [{"reactor_discord_id": 22222, "emoji": "🔥"}] * 10
        mult_max, _ = calculate_peer_multiplier(many_fire, author_id)
        self.assertEqual(mult_max, 1.20)

        # Case 3: Extreme negative reactions clamped at 0.8
        many_warnings = [{"reactor_discord_id": 22222, "emoji": "⚠️"}] * 10
        mult_min, _ = calculate_peer_multiplier(many_warnings, author_id)
        self.assertEqual(mult_min, 0.80)

    def test_daily_score_formula_and_anti_task_stuffing(self):
        author_id = 100

        # 5 tasks: two weight-3 tasks, three weight-1 tasks, plus one 4th weight-1 task (should be discounted)
        tasks = [
            {"task": "Ship core API", "completion": 1.0, "complexity": 3, "dharma_multiplier": 1.2},  # 3 * 1.2 = 3.6
            {"task": "Write SOP", "completion": 0.5, "complexity": 2, "dharma_multiplier": 1.0},       # 1 * 1.0 = 1.0
            {"task": "Check email", "completion": 1.0, "complexity": 1, "dharma_multiplier": 1.0},     # 1.0
            {"task": "Clean folder", "completion": 1.0, "complexity": 1, "dharma_multiplier": 1.0},    # 1.0
            {"task": "Send receipt", "completion": 1.0, "complexity": 1, "dharma_multiplier": 1.0},    # 1.0
            {"task": "Organize bookmarks", "completion": 1.0, "complexity": 1, "dharma_multiplier": 1.0}, # 4th W1 -> 0.25
        ]
        # Expected raw sum: 3.6 + 1.0 + 1.0 + 1.0 + 1.0 + 0.25 = 7.85
        score_res = compute_daily_score(
            task_evaluations=tasks,
            reactions=[{"reactor_discord_id": 200, "emoji": "✅"}],  # M_peer = 1.05
            author_discord_id=author_id,
            spontaneous_bonus=2.0,
        )

        expected_raw = 7.85
        expected_final = round((expected_raw * 1.05) + 2.0, 2)
        self.assertEqual(score_res["raw_task_sum"], expected_raw)
        self.assertEqual(score_res["peer_multiplier"], 1.05)
        self.assertEqual(score_res["bonus_points"], 2.0)
        self.assertEqual(score_res["final_score"], expected_final)


class TestEquityEngine(unittest.TestCase):
    def test_conservation_of_equity_across_24_months(self):
        """Simulate 24 months of steady performance and verify equity sums to 100%."""
        cumulative_cto = 0.0
        cumulative_coo = 0.0

        for month in range(1, 25):
            res = compute_monthly_equity_split(
                month_index=month,
                year_month=f"2026-{month:02d}",
                cto_score=100.0,
                coo_score=120.0,  # ~45.45% CTO vs 54.55% COO
                current_cto_equity=cumulative_cto,
                current_coo_equity=cumulative_coo,
            )
            cumulative_cto = res["cumulative_cto"]
            cumulative_coo = res["cumulative_coo"]

            # Total unvested pool distributed so far
            expected_released = round(MONTHLY_TRANCHE_EQUITY * month, 4)
            actual_released = round(cumulative_cto + cumulative_coo + res["treasury_diverted"], 4)
            self.assertAlmostEqual(actual_released, expected_released, places=3)

        # After 24 months, CEO (45%) + CTO + COO + Treasury must sum to 100%
        final_total = 45.0 + cumulative_cto + cumulative_coo
        self.assertAlmostEqual(final_total, 100.0, places=3)

    def test_safety_floor_prevents_zero_sum_cannibalization(self):
        """When COO is sick/inactive (score=0), their unearned equity must go to Treasury, not CTO."""
        res = compute_monthly_equity_split(
            month_index=1,
            year_month="2026-09",
            cto_score=100.0,
            coo_score=0.0,  # Below 60% floor
            current_cto_equity=0.0,
            current_coo_equity=0.0,
        )
        # Treasury must capture the deficit
        self.assertGreater(res["treasury_diverted"], 0.0)
        # CTO must NOT receive the entire 2.2917% tranche
        self.assertLess(res["equity_awarded_cto"], MONTHLY_TRANCHE_EQUITY)


class TestDatabaseAndPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_full_database_lifecycle(self):
        await init_db()
        users = await get_all_users()
        self.assertEqual(len(users), 3)

        # 1. Goal saving
        await save_daily_goals(
            founder_key="swarit",
            goal_date="2026-09-16",
            raw_text="• Ship websocket handler\n• Optimize SQL queries",
            parsed_goals=[
                {"task": "Ship websocket handler", "complexity": 3, "dharma_multiplier": 1.2},
                {"task": "Optimize SQL queries", "complexity": 4, "dharma_multiplier": 1.2}
            ]
        )
        goals = await get_goals_for_date("swarit", "2026-09-16")
        self.assertIsNotNone(goals)
        self.assertEqual(len(goals["parsed_goals"]), 2)

        # 2. Update logging
        await save_channel_update(
            message_id=999888,
            founder_key="swarit",
            discord_user_id=12345,
            channel_id=1508293104371896330,
            content="Merged PR #12 for websocket connection",
            timestamp="2026-09-16T14:30:00"
        )
        updates = await get_updates_for_date_range("swarit", "2026-09-16T00:00:00", "2026-09-16T23:59:59")
        self.assertEqual(len(updates), 1)

        # 3. Peer Reaction
        await record_peer_reaction(
            message_id=999888,
            reactor_discord_id=67890,
            reactor_founder_key="rahul",
            emoji="🔥",
            weight=0.10
        )
        rx = await get_reactions_for_messages([999888])
        self.assertEqual(len(rx), 1)
        self.assertEqual(rx[0]["emoji"], "🔥")

        # 4. Save Score
        await save_daily_score(
            founder_key="swarit",
            score_date="2026-09-16",
            completion_score=7.2,
            complexity_score=7.0,
            dharma_score=1.2,
            peer_multiplier=1.10,
            bonus_points=1.0,
            final_score=8.92,
            breakdown_json={"status": "verified"},
            praise_text="Crushed the websocket architecture!",
            feedback_text="Remember to add documentation."
        )
        score = await get_daily_score("swarit", "2026-09-16")
        self.assertIsNotNone(score)
        self.assertEqual(score["final_score"], 8.92)


class TestEvaluatorPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_goal_parsing(self):
        raw_text = "1. Deploy authentication engine\n2. Call 10 enterprise leads\n3. Quick fix for header bug"
        parsed = await parse_daily_goals_with_ai("swarit", raw_text)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 3)
        self.assertIn("complexity", parsed[0])
        self.assertIn("dharma_multiplier", parsed[0])

    async def test_fallback_execution_evaluation(self):
        goals = [
            {"task": "Deploy authentication engine", "complexity": 4, "dharma_multiplier": 1.2},
            {"task": "Call 10 leads", "complexity": 3, "dharma_multiplier": 1.0}
        ]
        updates = "[2026-09-16T15:00:00] Deployed auth engine to staging with zero downtime."
        eval_res = await evaluate_daily_execution_with_ai("swarit", goals, updates)
        self.assertIn("task_evaluations", eval_res)
        self.assertEqual(len(eval_res["task_evaluations"]), 2)
        self.assertIn("praise_text", eval_res)
        self.assertIn("feedback_text", eval_res)


if __name__ == "__main__":
    unittest.main()
