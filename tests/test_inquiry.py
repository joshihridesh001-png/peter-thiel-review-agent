import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.inquiry import generate_pre_scoring_inquiries

@pytest.mark.asyncio
async def test_generate_inquiries_identifies_gap():
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '{"needs_clarification": true, "question": "Did the client join the 4 PM reschedule call, or was it delayed?"}'

    with patch("engine.inquiry._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_resp
        mock_get_client.return_value = mock_client
        
        with patch("engine.inquiry.get_goals_for_date", new_callable=AsyncMock) as mock_goals:
            mock_goals.return_value = {"parsed_goals": [{"task": "Deploy client portal"}]}
            with patch("engine.inquiry.get_updates_for_date_range", new_callable=AsyncMock) as mock_updates:
                mock_updates.return_value = [{"content": "[Screenshot Analysis: error.png] 500 error on deploy"}]
                
                res = await generate_pre_scoring_inquiries("2026-10-12")
                assert len(res) > 0
                first_q = list(res.values())[0]
                assert "client" in first_q.lower() or "delayed" in first_q.lower()

@pytest.mark.asyncio
async def test_generate_inquiries_no_client():
    with patch("engine.inquiry._get_client", return_value=None):
        res = await generate_pre_scoring_inquiries("2026-10-12")
        assert res == {}

@pytest.mark.asyncio
async def test_generate_inquiries_no_gap():
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '{"needs_clarification": false, "question": ""}'

    with patch("engine.inquiry._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_resp
        mock_get_client.return_value = mock_client
        
        with patch("engine.inquiry.get_goals_for_date", new_callable=AsyncMock) as mock_goals:
            mock_goals.return_value = {"parsed_goals": [{"task": "Code refactor"}]}
            with patch("engine.inquiry.get_updates_for_date_range", new_callable=AsyncMock) as mock_updates:
                mock_updates.return_value = [{"content": "Done with all tests"}]
                
                res = await generate_pre_scoring_inquiries("2026-10-12")
                assert res == {}
