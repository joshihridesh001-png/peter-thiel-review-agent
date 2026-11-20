"""Who is allowed to change identity, equity, and the nightly run."""

import pytest

from cogs.commands import CommandsCog, can_run_sensitive_command
from config import FOUNDERS

HRIDESH = FOUNDERS["hridesh"]["discord_id"]
YASH = FOUNDERS["yash"]["discord_id"]


def test_only_the_cap_table_can_rewrite_identity_or_equity():
    assert can_run_sensitive_command(HRIDESH) is True
    assert can_run_sensitive_command(FOUNDERS["swarit"]["discord_id"]) is True
    assert can_run_sensitive_command(FOUNDERS["rahul"]["discord_id"]) is True
    assert can_run_sensitive_command(YASH) is False
    assert can_run_sensitive_command(FOUNDERS["shivang"]["discord_id"]) is False
    assert can_run_sensitive_command(FOUNDERS["harsh"]["discord_id"]) is False
    assert can_run_sensitive_command(0) is False
    assert can_run_sensitive_command(None) is False


class _User:
    def __init__(self, uid, bot=False):
        self.id = uid
        self.bot = bot


class _Response:
    def __init__(self):
        self.sent = None

    async def send_message(self, content, ephemeral=False):
        self.sent = (content, ephemeral)


class _Interaction:
    def __init__(self, uid, bot=False):
        self.user = _User(uid, bot)
        self.response = _Response()


@pytest.mark.asyncio
async def test_yash_cannot_rebind_a_role_or_ratify_equity():
    cog = CommandsCog(bot=None)
    blocked = _Interaction(YASH)
    assert await cog._blocked(blocked) is True
    assert blocked.response.sent[1] is True
    assert "Hridesh" in blocked.response.sent[0]

    allowed = _Interaction(HRIDESH)
    assert await cog._blocked(allowed) is False
    assert allowed.response.sent is None

    bot_user = _Interaction(HRIDESH, bot=True)
    assert await cog._blocked(bot_user) is True
