"""A fake webhook or a lookalike URL is not a GitHub pull request."""

from cogs.tracker import TrackerCog
from engine.credit import assign_credit
from engine.impact import github_artifact, proof_grade
from tests.test_github_tracking import make_mock_github_message


def test_a_webhook_that_is_not_github_is_not_a_pull_request():
    cog = TrackerCog(bot=None)
    forged = make_mock_github_message(
        title="[calcrum] Pull request opened: #1",
        author_name="swarit-soni",
        url="https://github.com/calcrum/app/pull/1",
    )
    forged.author.name = "Not GitHub"
    forged.author.bot = True
    forged.webhook_id = 999
    assert cog._extract_github_updates(forged) == []


def test_a_lookalike_pull_url_is_dropped():
    cog = TrackerCog(bot=None)
    forged = make_mock_github_message(
        title="[calcrum] Pull request opened: #1",
        author_name="swarit-soni",
        url="https://evil.example/pull/1",
    )
    assert cog._extract_github_updates(forged) == []


def test_short_words_do_not_steal_a_github_name():
    cog = TrackerCog(bot=None)
    assert cog._resolve_github_username("png") is None
    assert cog._resolve_github_username("son") is None
    assert cog._resolve_github_username("hash") is None
    assert cog._resolve_github_username("hsharmaharshofficialin-hash") == "harsh"


def test_a_bot_named_ceo_is_not_hridesh():
    cog = TrackerCog(bot=None)
    assert cog._resolve_founder_key(42, "ceo helper", is_bot=True) is None
    assert cog._resolve_founder_key(42, "ceo", is_bot=False) is None


def test_a_fake_github_sentence_does_not_unlock_the_size():
    note = "[GitHub PR: Add the meta pixel]\nURL: https://evil.example/pull/12"
    assert github_artifact(note) is False
    assert proof_grade(note) == "link"
    result = assign_credit([{"founder_key": "swarit", "content": note}])
    assert result["swarit"][0]["complexity"] == 1


def test_a_real_github_pull_url_is_still_proof():
    note = (
        "[GitHub PR: Add the meta pixel]\n"
        "Author: swarit-soni\n"
        "URL: https://github.com/calcrum/app/pull/12"
    )
    assert github_artifact(note) is True
    assert proof_grade(note) == "strong"
    result = assign_credit([{"founder_key": "swarit", "content": note}])
    assert result["swarit"][0]["completion"] == 1.0
