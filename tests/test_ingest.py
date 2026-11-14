"""Yash and Shivang's daily notes have to land on the card."""

from datetime import date, datetime
from types import SimpleNamespace

from cogs.scheduler import score_window
from cogs.tracker import TrackerCog
from config import CHANNELS, TIMEZONE
from engine.credit import assign_credit


def test_real_discord_handles_match_even_without_the_snowflake():
    cog = TrackerCog(bot=None)
    assert cog._resolve_founder_key(42, "yy4sh") == "yash"
    assert cog._resolve_founder_key(42, "someone", global_name="yyash") == "yash"
    assert cog._resolve_founder_key(42, "other", nick="yyash𐕣") == "yash"
    assert cog._resolve_founder_key(42, "shivang2468") == "shivang"


def test_a_thread_uses_the_parent_channel():
    cog = TrackerCog(bot=None)
    channel = SimpleNamespace(id=999, parent_id=CHANNELS["sales-updates"])
    assert cog._logged_channel_id(channel) == CHANNELS["sales-updates"]
    assert cog._logged_channel_id(SimpleNamespace(id=CHANNELS["daily-reports"])) == CHANNELS["daily-reports"]
    assert cog._logged_channel_id(SimpleNamespace(id=123, parent_id=456)) is None


def test_a_daytime_sales_log_is_work_not_a_goal():
    cog = TrackerCog(bot=None)
    when = datetime(2026, 11, 14, 16, 0, tzinfo=TIMEZONE)
    text = "Today I sent 40 linkedin requests\n- Booked a call with Gyro Farms"
    assert cog._is_goal_declaration(text, CHANNELS["daily-reports"], when, True) is False


def test_a_night_plan_stays_a_goal():
    cog = TrackerCog(bot=None)
    when = datetime(2026, 11, 14, 21, 10, tzinfo=TIMEZONE)
    text = "Tomorrow\n- Send linkedin requests\n- Follow up farms"
    assert cog._is_goal_declaration(text, CHANNELS["daily-reports"], when, True) is True


def test_a_night_sales_log_is_work():
    cog = TrackerCog(bot=None)
    when = datetime(2026, 11, 14, 21, 10, tzinfo=TIMEZONE)
    text = "Sent 30 whatsapp messages\nBooked a call with Gyro"
    assert cog._is_goal_declaration(text, CHANNELS["daily-reports"], when, True) is False


def test_a_night_list_without_a_finished_verb_stays_a_goal():
    cog = TrackerCog(bot=None)
    when = datetime(2026, 11, 14, 21, 10, tzinfo=TIMEZONE)
    text = "- Linkedin requests\n- Follow up farms"
    assert cog._is_goal_declaration(text, CHANNELS["daily-reports"], when, True) is True


def test_the_card_window_keeps_last_night_and_one_am():
    start, end = score_window(date(2026, 11, 14))
    assert start == "2026-11-13T20:00:00"
    assert end == "2026-11-14T23:59:59"


def test_whatsapp_and_connects_count_for_yash():
    result = assign_credit([
        {"founder_key": "yash", "content": "Sent 30 whatsapp messages"},
        {"founder_key": "shivang", "content": "Sent 12 connects"},
    ])
    assert result["yash"][0]["complexity"] == 1
    assert result["yash"][0]["completion"] == 0.3
    assert result["shivang"][0]["complexity"] == 1
    assert result["shivang"][0]["completion"] == 0.3


def test_a_voice_note_with_no_transcript_scores_zero():
    result = assign_credit([
        {"founder_key": "shivang", "content": "[Voice note with no transcript]"},
    ])
    task = result["shivang"][0]
    assert task["completion"] == 0.0
    assert "no transcript" in task["score_reason"].lower()
    assert "scores 0" in task["score_reason"].lower()
