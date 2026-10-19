"""
Tests for GitHub Webhook Parsing, PR/Commit Attribution, and Channel History Synchronization.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from cogs.tracker import TrackerCog
from config import CHANNELS, FOUNDERS


def make_mock_github_message(title, author_name, url="", description=""):
    msg = MagicMock()
    msg.id = 1561708215383752707
    msg.author.bot = True
    msg.author.name = "GitHub"
    msg.author.id = 1508293185095598120
    msg.webhook_id = 1508293185095598120
    msg.channel.id = CHANNELS["dev-updates"]
    msg.created_at = datetime(2026, 10, 19, 11, 50, 53, tzinfo=timezone.utc)
    msg.content = ""

    embed = MagicMock()
    embed.title = title
    embed.description = description
    embed.url = url
    if author_name:
        embed.author.name = author_name
    else:
        embed.author = None
    embed.fields = []

    msg.embeds = [embed]
    msg.attachments = []
    return msg


def test_extract_github_updates_pr_opened():
    bot = MagicMock()
    cog = TrackerCog(bot)
    msg = make_mock_github_message(
        title="[swarit-soni/calcrum] Pull request opened: #79 Overnight dev-team system (Night Runner), source only",
        author_name="joshihridesh001-png",
        url="https://github.com/swarit-soni/calcrum/pull/79",
        description="Night Runner system implementation with tests."
    )

    updates = cog._extract_github_updates(msg)
    assert len(updates) == 1
    founder_key, content = updates[0]
    assert founder_key == "hridesh"
    assert "[GitHub PR:" in content
    assert "#79" in content
    assert "joshihridesh001-png" in content
    assert "https://github.com/swarit-soni/calcrum/pull/79" in content
    assert "Night Runner system implementation" in content


def test_extract_github_updates_commit():
    bot = MagicMock()
    cog = TrackerCog(bot)
    msg = make_mock_github_message(
        title="[calcrum:fix/admin-impersonation-workspace-load] 1 new commit",
        author_name="swarit-soni",
        url="https://github.com/swarit-soni/calcrum/commit/3901152",
        description="fix(web): resolve admin impersonation workspace load timeout"
    )

    updates = cog._extract_github_updates(msg)
    assert len(updates) == 1
    founder_key, content = updates[0]
    assert founder_key == "swarit"
    assert "[GitHub Commit:" in content
    assert "swarit-soni" in content


def test_extract_github_updates_filters_ci_bots():
    bot = MagicMock()
    cog = TrackerCog(bot)

    # 1. Vercel bot comment
    msg_vercel = make_mock_github_message(
        title="[swarit-soni/calcrum] New comment on pull request #79",
        author_name="vercel[bot]",
        description="Deployment complete at https://calcrum-preview.vercel.app"
    )
    assert cog._extract_github_updates(msg_vercel) == []

    # 2. Automated unresolved feedback embed
    msg_feedback = make_mock_github_message(
        title="[calcrum] ✅ No unresolved feedback on pull request #79",
        author_name="",
        description="💬 0 unresolved, 0 resolved."
    )
    assert cog._extract_github_updates(msg_feedback) == []


@pytest.mark.asyncio
async def test_tracker_cog_saves_github_webhook_message():
    bot = MagicMock()
    cog = TrackerCog(bot)

    msg = make_mock_github_message(
        title="[swarit-soni/calcrum] Pull request opened: #79 Overnight dev-team system (Night Runner), source only",
        author_name="joshihridesh001-png",
        url="https://github.com/swarit-soni/calcrum/pull/79",
        description="Night Runner system implementation."
    )

    with patch("cogs.tracker.save_channel_update", new_callable=AsyncMock) as mock_save:
        await cog.on_message(msg)
        mock_save.assert_awaited_once()
        args, kwargs = mock_save.call_args
        assert kwargs["founder_key"] == "hridesh"
        assert kwargs["discord_user_id"] == FOUNDERS["hridesh"]["discord_id"]
        assert kwargs["channel_id"] == CHANNELS["dev-updates"]
        assert "[GitHub PR:" in kwargs["content"]


@pytest.mark.asyncio
async def test_sync_recent_channel_updates():
    bot = MagicMock()
    cog = TrackerCog(bot)

    channel = MagicMock()
    msg = make_mock_github_message(
        title="[swarit-soni/calcrum] Pull request opened: #79 Overnight dev-team system (Night Runner)",
        author_name="joshihridesh001-png",
        url="https://github.com/swarit-soni/calcrum/pull/79",
        description="Full PR description."
    )

    async def fake_history(limit=100):
        yield msg

    channel.history = fake_history
    bot.get_channel.return_value = channel

    with patch("cogs.tracker.save_channel_update", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = 42
        synced = await cog.sync_recent_channel_updates(limit=10)
        assert synced > 0
        mock_save.assert_awaited()
        args, kwargs = mock_save.call_args
        assert kwargs["founder_key"] == "hridesh"
