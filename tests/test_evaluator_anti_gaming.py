import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.evaluator import evaluate_daily_execution_with_ai

@pytest.mark.asyncio
async def test_evaluator_caps_unsupported_claim():
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '''{
      "task_evaluations": [
        {
          "task": "Client onboarding integration",
          "completion": 0.4,
          "complexity": 4,
          "dharma_multiplier": 1.2,
          "evidence_snippet": "Founder claimed system is done, but only a 1-page wireframe exists with no code.",
          "score_reason": "Capped credit: claim exceeds tangible proof on disk."
        }
      ],
      "spontaneous_bonus": 0.0,
      "praise_text": "Good start on the wireframe.",
      "feedback_text": "Provide git commits or API proof to get full credit tomorrow.",
      "mentor_question": "Can you push the backend branch tomorrow?"
    }'''

    with patch("engine.evaluator._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_resp
        mock_get_client.return_value = mock_client

        res = await evaluate_daily_execution_with_ai(
            "hridesh",
            [{"task": "Client onboarding integration"}],
            "Clarification reply: Finished the entire client onboarding today.\n[File Attachment: wireframe.png] Just UI mock."
        )
        task = res["task_evaluations"][0]
        assert task["completion"] <= 0.5
        assert "capped" in task["score_reason"].lower() or "proof" in task["score_reason"].lower()

@pytest.mark.asyncio
async def test_evaluator_upgrades_modest_claim_with_heavy_artifacts():
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '''{
      "task_evaluations": [
        {
          "task": "Fix bank ledger reconciliation",
          "completion": 1.0,
          "complexity": 5,
          "dharma_multiplier": 1.2,
          "evidence_snippet": "Attached ledger spec proves 2,763 transactions ingested with zero drift.",
          "score_reason": "Full credit upgraded: quiet update backed by massive verified code output."
        }
      ],
      "spontaneous_bonus": 1.5,
      "spontaneous_reason": "Zero drift across thousands of live bank ledger transactions.",
      "praise_text": "You barely bragged, but you fixed thousands of transactions with zero drift! Huge engineering win.",
      "feedback_text": "Keep shipping code of this caliber.",
      "mentor_question": "Is this ledger ready for the client pilot demo?"
    }'''

    with patch("engine.evaluator._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_resp
        mock_get_client.return_value = mock_client

        res = await evaluate_daily_execution_with_ai(
            "swarit",
            [{"task": "Fix bank ledger reconciliation"}],
            "fixed a bug\n[File Attachment: gyros_reconcile.py] Verified 2,763 entries, 0 drift."
        )
        task = res["task_evaluations"][0]
        assert task["completion"] == 1.0
        assert task["complexity"] == 5
        assert "zero drift" in res["praise_text"].lower()
