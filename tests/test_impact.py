"""Same work gets the same size. A count is not the size."""

from engine.credit import assign_credit
from engine.impact import work_size
from engine.scoring import compute_daily_score


def _points(tasks):
    return compute_daily_score(tasks, reactions=[], author_discord_id=0)["final_score"]


def test_five_linkedin_requests_are_size_one_every_time():
    five = "Sent 5 connection requests on LinkedIn"
    fifty = "Sent 50 connection requests on LinkedIn"
    assert work_size(five) == 1
    assert work_size(fifty) == 1
    assert work_size(five) == work_size("Sent 1 connection request on LinkedIn")

    day_one = assign_credit([{"founder_key": "rahul", "content": five}])
    day_two = assign_credit([{"founder_key": "rahul", "content": five}])
    assert day_one == day_two
    assert day_one["rahul"][0]["complexity"] == 1
    assert day_one["rahul"][0]["completion"] == 0.3
    assert _points(day_one["rahul"]) == 0.3
    assert "count is not the size" in day_one["rahul"][0]["score_reason"].lower()


def test_a_linkedin_screenshot_is_one_point_not_five():
    note = "Sent 5 connection requests on LinkedIn\nhttps://www.linkedin.com/messaging/thread/abc"
    result = assign_credit([{"founder_key": "rahul", "content": note}])
    assert result["rahul"][0]["completion"] == 1.0
    assert result["rahul"][0]["complexity"] == 1
    assert _points(result["rahul"]) == 1.0


def test_five_outreach_notes_are_one_chore():
    result = assign_credit([
        {"founder_key": "rahul", "content": "I did linkedin for restaurants"},
        {"founder_key": "rahul", "content": "I did cold email for clinics"},
    ])
    assert len(result["rahul"]) == 1
    assert result["rahul"][0]["complexity"] == 1
    assert _points(result["rahul"]) == 0.3


def test_a_merged_feature_outranks_connection_requests():
    linkedin = assign_credit([{
        "founder_key": "rahul",
        "content": "Sent 5 connection requests on LinkedIn\nhttps://www.linkedin.com/messaging/thread/abc",
    }])
    feature = assign_credit([{
        "founder_key": "swarit",
        "content": (
            "[GitHub PR: Add the meta pixel]\n"
            "Author: swarit-soni\n"
            "URL: https://github.com/calcrum/app/pull/12\n"
            "merged"
        ),
    }])
    assert feature["swarit"][0]["complexity"] == 3
    assert _points(feature["swarit"]) > _points(linkedin["rahul"])


def test_money_in_is_size_five_only_with_proof():
    sentence = assign_credit([{
        "founder_key": "rahul",
        "content": "I got it, the customer paid the invoice",
    }])
    proven = assign_credit([{
        "founder_key": "rahul",
        "content": "I got it, the customer paid the invoice\nhttps://example.com/invoice.pdf",
    }])
    assert sentence["rahul"][0]["complexity"] == 1
    assert _points(sentence["rahul"]) == 0.3
    assert "size 5" in sentence["rahul"][0]["score_reason"].lower()
    assert proven["rahul"][0]["complexity"] == 5
    assert _points(proven["rahul"]) == 5.0


def test_a_booked_call_beats_a_poke():
    assert work_size("Booked a call from a LinkedIn lead") == 2
    assert work_size("Had a demo call with Gyro Farms") == 3


def test_a_bare_link_does_not_prove_a_sale_or_the_word_commit():
    from engine.impact import praise_for_scored_lines, proof_grade, size_label

    sale = assign_credit([{
        "founder_key": "rahul",
        "content": "I got it, the customer paid the invoice\nhttps://example.com/pay",
    }])
    task = sale["rahul"][0]
    assert proof_grade(task["evidence_snippet"]) == "link"
    assert task["completion"] == 0.3
    assert task["complexity"] == 1
    assert task["rubric_size"] == 5
    assert _points(sale["rahul"]) == 0.3
    assert "bare link is not proof" in task["score_reason"].lower()
    assert size_label(task["complexity"], task["rubric_size"]) == "1/5 (would be 5/5 with proof)"

    commit_word = assign_credit([{
        "founder_key": "swarit",
        "content": "I commit to the meta pixel",
    }])
    assert commit_word["swarit"][0]["completion"] == 0.3
    assert proof_grade("I commit to the meta pixel") == "none"

    screenshot = assign_credit([{
        "founder_key": "rahul",
        "content": "I got it, the customer paid the invoice. Screenshot of the receipt.",
    }])
    assert screenshot["rahul"][0]["completion"] == 1.0
    assert screenshot["rahul"][0]["complexity"] == 5
    assert _points(screenshot["rahul"]) == 5.0


def test_praise_names_only_lines_that_scored():
    from engine.impact import praise_for_scored_lines

    text = praise_for_scored_lines([
        {"task": "Sent 5 connection requests on LinkedIn", "completion": 0.3},
        {"task": "I finished the meta pixel", "completion": 0.0},
    ])
    assert text == "Counted today: Sent 5 connection requests on LinkedIn."
    assert "pixel" not in text.lower()
    assert praise_for_scored_lines([{"task": "Nope", "completion": 0}]) == (
        "Nothing here counted as finished work."
    )
