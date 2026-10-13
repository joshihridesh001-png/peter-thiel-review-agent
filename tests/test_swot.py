import pytest
from unittest.mock import patch, MagicMock
from engine.swot import generate_weekly_swot_with_ai

@pytest.mark.asyncio
async def test_generate_weekly_swot_with_ai_fallback():
    with patch("engine.swot._get_client", return_value=None):
        res = await generate_weekly_swot_with_ai({"some": "data"})
        assert "overall_summary" in res
        assert "founder_swot" in res
        assert "hridesh" in res["founder_swot"]

@pytest.mark.asyncio
async def test_generate_weekly_swot_with_ai_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"overall_summary": "AI summary", "founder_swot": {}}'
    mock_client.models.generate_content.return_value = mock_response
    with patch("engine.swot._get_client", return_value=mock_client):
        res = await generate_weekly_swot_with_ai({"some": "data"})
        assert res["overall_summary"] == "AI summary"

@pytest.mark.asyncio
async def test_generate_weekly_swot_with_ai_exception():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API Error")
    with patch("engine.swot._get_client", return_value=mock_client):
        res = await generate_weekly_swot_with_ai({"some": "data"})
        assert "7-Day Sprint completed" in res["overall_summary"]
