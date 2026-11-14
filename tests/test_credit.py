"""Who gets the points when chat and proof disagree."""

from engine.credit import assign_credit, judge_doer


def _positive(result, key):
    return [task for task in result.get(key, []) if task["completion"] > 0]


def test_announcement_goes_to_the_person_who_did_the_work():
    pull_request = assign_credit([
        {
            "founder_key": "hridesh",
            "content": "The meta pixel thing is now done.",
        },
        {
            "founder_key": "swarit",
            "content": (
                "[GitHub PR: Add the meta pixel]\n"
                "Author: swarit-soni\n"
                "URL: https://github.com/calcrum/app/pull/12"
            ),
        },
    ])
    assert _positive(pull_request, "hridesh") == []
    assert len(_positive(pull_request, "swarit")) == 1
    assert pull_request["swarit"][0]["completion"] == 1.0
    assert pull_request["swarit"][0]["score_reason"] == (
        "Hridesh said this was done. Counted for Swarit because the pull request is his."
    )
    for field in ("task", "completion", "complexity", "dharma_multiplier", "score_reason", "evidence_snippet"):
        assert field in pull_request["swarit"][0]

    note = assign_credit([
        {"founder_key": "hridesh", "content": "The meta pixel thing is now done."},
        {"founder_key": "swarit", "content": "Shipped the meta pixel."},
    ])
    assert _positive(note, "hridesh") == []
    assert note["swarit"][0]["completion"] == 0.3


def test_naming_a_teammate_without_proof_is_capped():
    result = assign_credit([
        {"founder_key": "hridesh", "content": "Swarit finished the meta pixel."},
    ])
    assert result.get("hridesh", []) == []
    assert result["swarit"][0]["completion"] == 0.4


def test_a_lie_loses_to_the_commit_author():
    result = assign_credit([
        {"founder_key": "hridesh", "content": "I finished the meta pixel."},
        {
            "founder_key": "swarit",
            "content": (
                "[GitHub Commit: meta pixel]\n"
                "Author: swarit-soni\n"
                "URL: https://github.com/calcrum/app/commit/abc123"
            ),
        },
    ])
    assert result["swarit"][0]["completion"] == 1.0
    assert result["hridesh"][0]["completion"] == 0.0
    assert "claim" in result["hridesh"][0]["score_reason"].lower()


def test_artifact_beats_a_modest_line():
    result = assign_credit([
        {"founder_key": "swarit", "content": "Hridesh did the pixel."},
        {
            "founder_key": "swarit",
            "content": (
                "[GitHub Commit: meta pixel]\n"
                "Author: swarit-soni\n"
                "URL: https://github.com/calcrum/app/commit/abc999"
            ),
        },
    ])
    assert result["swarit"][0]["completion"] == 1.0
    assert _positive(result, "hridesh") == []


def test_two_claims_and_no_proof_score_nobody():
    result = assign_credit([
        {"founder_key": "hridesh", "content": "I finished the meta pixel."},
        {"founder_key": "swarit", "content": "I finished the meta pixel."},
    ])
    assert result["hridesh"][0]["completion"] == 0.0
    assert result["swarit"][0]["completion"] == 0.0
    assert "two claims" in result["hridesh"][0]["score_reason"].lower()
    assert "no proof" in result["hridesh"][0]["score_reason"].lower()
    assert result["swarit"][0]["score_reason"] == result["hridesh"][0]["score_reason"]


def test_pasting_a_pull_request_link_does_not_score_twice():
    url = "https://github.com/calcrum/app/pull/12"
    result = assign_credit([
        {
            "founder_key": "swarit",
            "content": f"[GitHub PR: Add the meta pixel]\nAuthor: swarit-soni\nURL: {url}",
        },
        {"founder_key": "hridesh", "content": f"Pasting the link {url}"},
    ])
    assert len(result["swarit"]) == 1
    assert result["swarit"][0]["completion"] == 1.0
    assert result.get("hridesh", []) == []


def test_a_named_closer_gets_the_customer_note():
    result = assign_credit([
        {"founder_key": "yash", "content": "Rahul closed Gyro Farms."},
        {"founder_key": "rahul", "content": "Gyro Farms call: they want a pilot next Tuesday."},
    ])
    assert result.get("yash", []) == []
    assert result["rahul"][0]["completion"] == 0.4


def test_your_own_booking_note_stays_yours():
    result = assign_credit([
        {"founder_key": "yash", "content": "Booked two calls"},
    ])
    assert list(result) == ["yash"]
    assert result["yash"][0]["completion"] == 0.3


def test_a_bare_done_with_no_task_scores_nobody():
    assert assign_credit([{"founder_key": "hridesh", "content": "done"}]) == {}
    assert assign_credit([{"founder_key": "hridesh", "content": "shipped"}]) == {}


def test_future_and_unfinished_work_scores_nobody():
    assert assign_credit([
        {"founder_key": "hridesh", "content": "Swarit will do the pixel."},
    ]) == {}
    assert assign_credit([
        {"founder_key": "hridesh", "content": "The pixel is not done."},
    ]) == {}


def test_two_names_in_one_sentence_do_not_move():
    result = assign_credit([
        {"founder_key": "hridesh", "content": "Swarit and Rahul finished the meta pixel."},
    ])
    assert result["hridesh"][0]["completion"] == 0.0
    assert "unclear" in result["hridesh"][0]["score_reason"].lower()
    assert "swarit" not in result
    assert "rahul" not in result


def test_one_note_splits_into_separate_jobs():
    result = assign_credit([{
        "founder_key": "rahul",
        "content": "Sent 5 requests, booked 2 calls, and Gyro paid",
    }])
    tasks = result["rahul"]
    assert len(tasks) == 3
    blob = " ".join(task["task"].lower() for task in tasks)
    assert "request" in blob
    assert "booked" in blob
    assert "paid" in blob
    paid = next(task for task in tasks if "paid" in task["task"].lower())
    booked = next(task for task in tasks if "booked" in task["task"].lower())
    assert paid["rubric_size"] == 5
    assert paid["completion"] == 0.3
    assert booked["rubric_size"] == 2


def test_not_done_drops_only_that_clause():
    result = assign_credit([{
        "founder_key": "rahul",
        "content": "Pixel is not done, but I sent 5 requests",
    }])
    assert len(result["rahul"]) == 1
    assert "request" in result["rahul"][0]["task"].lower()
    assert "pixel" not in result["rahul"][0]["task"].lower()
    assert result["rahul"][0]["completion"] == 0.3


def test_sent_does_not_glue_unrelated_notes():
    result = assign_credit([
        {"founder_key": "rahul", "content": "Sent the deck to investors"},
        {"founder_key": "rahul", "content": "Sent 5 connection requests on LinkedIn"},
    ])
    assert len(result["rahul"]) == 2


def test_a_bullet_list_scores_each_customer():
    result = assign_credit([{
        "founder_key": "rahul",
        "content": "- Booked a call with Gyro Farms\n- Booked a call with Acme Foods",
    }])
    assert len(result["rahul"]) == 2
    blob = " ".join(task["task"].lower() for task in result["rahul"])
    assert "gyro" in blob
    assert "acme" in blob


def test_judge_doer_reads_names_and_i():
    roster = {
        "yash": ["yash", "yy4sh"],
        "shivang": ["shivang", "shivang2468"],
        "swarit": ["swarit"],
    }
    assert judge_doer("yy4sh shipped the booking sheet", roster, []) == "yash"
    assert judge_doer("shivang2468 booked the follow up", roster, []) == "shivang"
    assert judge_doer("I finished the export", roster, []) == "speaker"
    assert judge_doer("hello team", roster, []) == "unknown"
