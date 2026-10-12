import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.attachment_reader import extract_text_attachment

@pytest.mark.asyncio
async def test_extract_text_attachment_success():
    sample_content = "# Sprint Summary\nCompleted Gyros ledger ingestion with 0 drift."
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=sample_content.encode("utf-8"))

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        res = await extract_text_attachment("https://cdn.discordapp.com/test.md", "test.md")
        assert "[File Attachment: test.md" in res
        assert "Completed Gyros ledger ingestion" in res

@pytest.mark.asyncio
async def test_extract_text_attachment_truncates_large_files():
    huge_content = "A" * 300000
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=huge_content.encode("utf-8"))

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        res = await extract_text_attachment("https://cdn.discordapp.com/huge.txt", "huge.txt", max_bytes=10240)
        assert "[Truncated after 10.0 KB]" in res
