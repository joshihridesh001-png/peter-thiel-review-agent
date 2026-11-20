"""Harsh is on the daily card from both accounts. Rahul's bot posts count for Rahul."""

from cogs.scheduler import rep_beat_founders_line
from cogs.tracker import TrackerCog
from config import FOUNDERS, discord_ids_for
from engine.scoring import calculate_peer_multiplier

HARSH_MAIN = 1569234883988037652
HARSH_ALT = 1501813564699185174
RAHUL_BOT = 1543588738725052436


def test_harsh_is_an_engineer_on_the_daily_card_only():
    harsh = FOUNDERS["harsh"]
    assert harsh["role"] == "Engineer"
    assert harsh["on_cap_table"] is False
    assert harsh["unvested_target"] == 0.0
    assert discord_ids_for("harsh") == {HARSH_MAIN, HARSH_ALT}


def test_both_of_harshs_accounts_are_harsh():
    cog = TrackerCog(bot=None)
    assert cog._resolve_founder_key(HARSH_MAIN, "anything") == "harsh"
    assert cog._resolve_founder_key(HARSH_ALT, "anything") == "harsh"


def test_rahuls_bot_is_rahul_whatever_it_is_called():
    cog = TrackerCog(bot=None)
    # Named like a CEO or CTO helper. The account id still wins.
    assert cog._resolve_founder_key(RAHUL_BOT, "ceo helper", is_bot=True) == "rahul"
    assert cog._resolve_founder_key(RAHUL_BOT, "cto's assistant", is_bot=True) == "rahul"


def test_an_unknown_id_still_falls_back_to_names():
    cog = TrackerCog(bot=None)
    assert cog._resolve_founder_key(42, "harsh") == "harsh"
    assert cog._resolve_founder_key(42, "stranger") is None


def test_a_reaction_from_your_second_account_is_not_a_peer_boost():
    reactions = [
        {"reactor_discord_id": HARSH_ALT, "emoji": "🔥"},
        {"reactor_discord_id": HARSH_MAIN, "emoji": "✅"},
    ]
    multiplier, counts = calculate_peer_multiplier(reactions, discord_ids_for("harsh"))
    assert multiplier == 1.0
    assert counts["🔥"] == 0


def test_rahuls_bot_cannot_boost_rahul():
    reactions = [{"reactor_discord_id": RAHUL_BOT, "emoji": "🔥"}]
    multiplier, _ = calculate_peer_multiplier(reactions, discord_ids_for("rahul"))
    assert multiplier == 1.0


def test_a_teammate_still_boosts_harsh():
    swarit = FOUNDERS["swarit"]["discord_id"]
    multiplier, _ = calculate_peer_multiplier(
        [{"reactor_discord_id": swarit, "emoji": "🔥"}],
        discord_ids_for("harsh"),
    )
    assert multiplier == 1.1


def test_single_id_callers_still_work():
    multiplier, _ = calculate_peer_multiplier([{"reactor_discord_id": 5, "emoji": "✅"}], 5)
    assert multiplier == 1.0


def test_harsh_beating_every_founder_is_one_sentence():
    line = rep_beat_founders_line([("hridesh", 4.0), ("swarit", 5.0), ("rahul", 3.0), ("harsh", 6.0)])
    assert line == "Harsh finished 1.0 pts above every founder."
