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

from engine.attachment_reader import extract_image_summary

@pytest.mark.asyncio
async def test_extract_image_summary_success():
    fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=fake_png)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = "Terminal displaying a Vercel 500 server error on the auth webhook route."

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("engine.attachment_reader._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_gemini_resp
            mock_get_client.return_value = mock_client
            
            res = await extract_image_summary("https://cdn.discordapp.com/error.png", "error.png")
            assert "[Screenshot Analysis: error.png]" in res
            assert "Vercel 500 server error" in res

@pytest.mark.asyncio
async def test_extract_image_summary_no_client():
    with patch("engine.attachment_reader._get_client", return_value=None):
        res = await extract_image_summary("https://cdn.discordapp.com/test.png", "test.png")
        assert "Gemini API key not configured for vision" in res

@pytest.mark.asyncio
async def test_extract_image_summary_http_error():
    mock_resp = AsyncMock()
    mock_resp.status = 404

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("engine.attachment_reader._get_client", return_value=MagicMock()):
            res = await extract_image_summary("https://cdn.discordapp.com/notfound.png", "notfound.png")
            assert "HTTP 404 download error" in res
