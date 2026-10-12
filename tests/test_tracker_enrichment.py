import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from engine.attachment_reader import enrich_discord_message

@pytest.mark.asyncio
async def test_enrich_discord_message_with_attachment():
    msg = MagicMock()
    msg.content = "Dropping our sprint review"
    msg.embeds = []
    att = MagicMock()
    att.filename = "review.md"
    att.url = "https://cdn.discordapp.com/review.md"
    msg.attachments = [att]

    with patch("engine.attachment_reader.extract_text_attachment", new_callable=AsyncMock) as mock_text:
        mock_text.return_value = "[File Attachment: review.md]\nAll tasks done"
        res = await enrich_discord_message(msg)
        assert "Dropping our sprint review" in res
        assert "[File Attachment: review.md]" in res
        assert "All tasks done" in res

@pytest.mark.asyncio
async def test_enrich_discord_message_with_image():
    msg = MagicMock()
    msg.content = "Look at this error"
    msg.embeds = []
    att = MagicMock()
    att.filename = "screenshot.png"
    att.url = "https://cdn.discordapp.com/screenshot.png"
    msg.attachments = [att]

    with patch("engine.attachment_reader.extract_image_summary", new_callable=AsyncMock) as mock_img:
        mock_img.return_value = "[Screenshot Analysis: screenshot.png]\nVisual Summary: Error 500"
        res = await enrich_discord_message(msg)
        assert "Look at this error" in res
        assert "[Screenshot Analysis: screenshot.png]" in res
        assert "Error 500" in res

@pytest.mark.asyncio
async def test_enrich_discord_message_with_embed():
    msg = MagicMock()
    msg.content = ""
    embed = MagicMock()
    embed.title = "Assistant Report"
    embed.description = "Generated 50 leads for sales pipeline."
    msg.embeds = [embed]
    msg.attachments = []

    res = await enrich_discord_message(msg)
    assert "[Embed: Assistant Report] Generated 50 leads for sales pipeline." in res

from cogs.tracker import TrackerCog

@pytest.mark.asyncio
async def test_tracker_cog_saves_enriched_update():
    bot = MagicMock()
    cog = TrackerCog(bot)

    msg = MagicMock()
    msg.author.bot = False
    msg.author.id = 12345
    msg.author.name = "swarit"
    msg.channel.id = 1508293104371896330  # dev-updates
    msg.content = ""
    msg.embeds = []
    
    att = MagicMock()
    att.filename = "spec.md"
    att.url = "https://cdn.discordapp.com/spec.md"
    msg.attachments = [att]

    with patch.object(cog, "_resolve_founder_key", return_value="swarit"):
        with patch("cogs.tracker.enrich_discord_message", new_callable=AsyncMock) as mock_enrich:
            mock_enrich.return_value = "[File Attachment: spec.md]\nDatabase schema ready"
            with patch("cogs.tracker.save_channel_update", new_callable=AsyncMock) as mock_save:
                await cog.on_message(msg)
                mock_save.assert_awaited_once()
                args, kwargs = mock_save.call_args
                assert kwargs["founder_key"] == "swarit"
                assert "[File Attachment: spec.md]" in kwargs["content"]
