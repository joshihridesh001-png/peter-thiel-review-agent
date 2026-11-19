"""Talk about a person is not their work. A late report still counts."""

from datetime import date

from cogs.scheduler import keeps_update
from engine.credit import assign_credit


def _positive(result, key):
    return [task for task in result.get(key, []) if task["completion"] > 0]


def test_an_order_or_an_opinion_about_yash_is_not_his_work():
    # Real lines Rahul posted in #general on 2026-11-18.
    for line in (
        "Yash has nothing real to do right now",
        "Yash take care of the remaining 15 women leads tomorrow",
        "give yash PR access so he dosent need you",
        "we will have yash and shivang keep working on outreach",
    ):
        result = assign_credit([{"founder_key": "rahul", "content": line}])
        assert _positive(result, "yash") == [], line
        assert _positive(result, "shivang") == [], line


def test_saying_someone_finished_work_still_counts_for_them():
    result = assign_credit([{"founder_key": "hridesh", "content": "Swarit shipped the meta pixel"}])
    assert _positive(result, "swarit")[0]["completion"] == 0.4


def test_proof_about_someone_else_still_counts():
    result = assign_credit([{
        "founder_key": "hridesh",
        "content": "[GitHub PR: Add the meta pixel]\nAuthor: swarit-soni\nURL: https://github.com/a/b/pull/14",
    }])
    assert _positive(result, "swarit")[0]["completion"] == 1.0


def test_own_notes_are_unchanged():
    result = assign_credit([{"founder_key": "yash", "content": "Sent 30 whatsapp messages to leads"}])
    assert _positive(result, "yash")


def test_late_report_with_yesterdays_date_counts_on_the_next_card():
    card_day = date(2026, 11, 19)
    late_report = {
        "timestamp": "2026-11-18T21:05:00+05:30",
        "content": "Daily report 18 Nov: sent 30 whatsapp messages",
    }
    assert keeps_update(late_report, card_day) is True


def test_a_recap_of_yesterday_posted_today_stays_off():
    card_day = date(2026, 11, 19)
    recap = {
        "timestamp": "2026-11-19T10:00:00+05:30",
        "content": "Recap of 18 nov: shipped the pixel",
    }
    assert keeps_update(recap, card_day) is False


def test_todays_note_and_empty_notes():
    card_day = date(2026, 11, 19)
    assert keeps_update({"timestamp": "2026-11-19T12:00:00+05:30", "content": "Booked a call with Gyro"}, card_day)
    assert not keeps_update({"timestamp": "2026-11-19T12:00:00+05:30", "content": "   "}, card_day)
    assert not keeps_update({"timestamp": "2026-11-19T12:00:00+05:30", "content": "Commitments locked for tomorrow"}, card_day)
