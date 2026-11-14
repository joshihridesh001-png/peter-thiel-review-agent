"""Same work gets the same size. A count is not the size."""

from engine.credit import assign_credit, prior_from_scores
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


def test_different_customers_are_separate_calls_and_the_fourth_is_quartered():
    notes = [
        "Booked a call with Gyro\nhttps://example.com/gyro.mp4",
        "Booked a call with Acme\nhttps://example.com/acme.mp4",
        "Booked a call with Northwind\nhttps://example.com/northwind.mp4",
        "Booked a call with Contoso\nhttps://example.com/contoso.mp4",
    ]
    result = assign_credit([
        {"founder_key": "yash", "content": note} for note in notes
    ])
    calls = result["yash"]
    assert len(calls) == 4
    assert calls[0]["complexity"] == 2
    assert calls[3]["stack_discount"] == 0.25
    assert "quarter" in calls[3]["score_reason"].lower()
    scored = compute_daily_score(calls, reactions=[], author_discord_id=0)
    assert scored["task_breakdown"][0]["task_points"] == 2.0
    assert scored["task_breakdown"][3]["task_points"] == 0.5


def test_the_same_customer_is_one_call():
    result = assign_credit([
        {"founder_key": "yash", "content": "Booked a call with Jay"},
        {"founder_key": "yash", "content": "Booked Jay again"},
    ])
    assert len(result["yash"]) == 1
    assert "same customer" in result["yash"][0]["score_reason"].lower()


def test_a_win_from_last_week_does_not_score_again():
    url = "https://github.com/calcrum/app/pull/12"
    first = assign_credit([{
        "founder_key": "swarit",
        "content": f"[GitHub PR: Add the meta pixel]\nAuthor: swarit-soni\nURL: {url}\nmerged",
    }])
    again = assign_credit(
        [{
            "founder_key": "swarit",
            "content": f"[GitHub PR: Add the meta pixel]\nAuthor: swarit-soni\nURL: {url}\nmerged",
        }],
        prior=[{
            "founder_key": "swarit",
            "text": first["swarit"][0]["task"] + " " + url,
        }],
    )
    assert again["swarit"][0]["completion"] == 0.0
    assert "7 days" in again["swarit"][0]["score_reason"].lower()


def test_the_same_customer_does_not_score_again_this_week():
    again = assign_credit(
        [{"founder_key": "yash", "content": "Booked a call with Gyro Farms"}],
        prior=[{"founder_key": "yash", "text": "Booked a call with Gyro"}],
    )
    assert again["yash"][0]["completion"] == 0.0
    assert "7 days" in again["yash"][0]["score_reason"].lower()
    other_rep = assign_credit(
        [{"founder_key": "shivang", "content": "Booked a call with Gyro Farms"}],
        prior=[{"founder_key": "yash", "text": "Booked a call with Gyro"}],
    )
    assert other_rep["shivang"][0]["completion"] == 0.3


def test_a_zero_line_from_last_week_does_not_block_today():
    prior = prior_from_scores([{
        "founder_key": "yash",
        "breakdown_json": {
            "task_breakdown": [
                {"task": "Booked a call with Gyro", "completion": 0.0, "evidence": "Booked a call with Gyro"},
            ]
        },
    }])
    assert prior == []
    today = assign_credit(
        [{"founder_key": "yash", "content": "Booked a call with Gyro"}],
        prior=prior,
    )
    assert today["yash"][0]["completion"] == 0.3


def test_a_new_poke_still_scores_the_next_day():
    again = assign_credit(
        [{"founder_key": "rahul", "content": "Sent 80 connection requests on LinkedIn"}],
        prior=[{"founder_key": "rahul", "text": "Sent 5 connection requests on LinkedIn"}],
    )
    assert again["rahul"][0]["completion"] == 0.3
    assert again["rahul"][0]["complexity"] == 1


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
