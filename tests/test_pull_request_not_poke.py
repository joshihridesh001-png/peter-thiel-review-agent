"""The word inside "pull requests" is not a LinkedIn poke."""

from engine.impact import is_outreach, work_size


def test_opened_pull_requests_stay_size_two():
    note = "Opened 2 pull requests\nhttps://github.com/calcrum/app/pull/12"
    assert is_outreach(note) is False
    assert work_size(note) == 2


def test_connection_requests_stay_a_poke():
    note = "Sent 80 connection requests on LinkedIn"
    assert is_outreach(note) is True
    assert work_size(note) == 1


def test_a_bare_requests_line_stays_size_one():
    assert work_size("Sent 5 requests") == 1
