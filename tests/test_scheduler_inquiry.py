import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from cogs.scheduler import SchedulerCog

@pytest.mark.asyncio
async def test_scheduler_runs_inquiry_callout():
    bot = MagicMock()
    channel = AsyncMock()
    bot.get_channel.return_value = channel

    cog = SchedulerCog(bot)
    with patch("engine.inquiry.generate_pre_scoring_inquiries", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "hridesh": "Did the Gyros client reply to the WhatsApp message?"
        }
        await cog.run_context_inquiry_callout("2026-10-12")
        assert channel.send.called
        call_args = channel.send.call_args[1]
        assert "embed" in call_args
        embed = call_args["embed"]
        assert "7:15 PM Quick Context Check" in embed.title
        assert "Gyros client" in embed.fields[0].value

@pytest.mark.asyncio
async def test_scheduler_skips_inquiry_when_no_gaps():
    bot = MagicMock()
    channel = AsyncMock()
    bot.get_channel.return_value = channel

    cog = SchedulerCog(bot)
    with patch("engine.inquiry.generate_pre_scoring_inquiries", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {}
        await cog.run_context_inquiry_callout("2026-10-12")
        assert not channel.send.called
