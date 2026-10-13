import pytest
from unittest.mock import patch, MagicMock
from engine.evaluator import parse_daily_goals_with_ai, evaluate_daily_execution_with_ai

@pytest.mark.asyncio
async def test_parse_daily_goals_with_ai_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Provide a valid JSON string simulating Gemini response
    mock_response.text = '''[
        {
            "task": "Test task",
            "complexity": 3,
            "dharma_multiplier": 1.2,
            "dharma_reason": "Good alignment",
            "score_reason": "Because it's a core task"
        }
    ]'''
    mock_client.models.generate_content.return_value = mock_response

    with patch("engine.evaluator._get_client", return_value=mock_client):
        result = await parse_daily_goals_with_ai("swarit", "Test task")
        assert len(result) == 1
        assert result[0]["task"] == "Test task"
        assert result[0]["complexity"] == 3
        assert result[0]["dharma_multiplier"] == 1.2

@pytest.mark.asyncio
async def test_parse_daily_goals_with_ai_clamp_values():
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Provide out of bounds values to test clamping
    mock_response.text = '''[
        {
            "task": "Out of bounds task",
            "complexity": 10,
            "dharma_multiplier": 2.0,
            "dharma_reason": "Too good"
        }
    ]'''
    mock_client.models.generate_content.return_value = mock_response

    with patch("engine.evaluator._get_client", return_value=mock_client):
        result = await parse_daily_goals_with_ai("swarit", "Out of bounds task")
        assert result[0]["complexity"] == 5  # clamped to max 5
        assert result[0]["dharma_multiplier"] == 1.2  # clamped to max 1.2

@pytest.mark.asyncio
async def test_evaluate_daily_execution_with_ai_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '''{
        "task_evaluations": [
            {
                "task": "Build feature X",
                "completion": 1.0,
                "evidence_snippet": "PR #1",
                "complexity": 4,
                "dharma_multiplier": 1.1,
                "score_reason": "Completed and merged"
            }
        ],
        "spontaneous_bonus": 2.0,
        "spontaneous_reason": "Helped debug prod",
        "mentor_question": "What next?",
        "praise_text": "Great work!",
        "feedback_text": "None"
    }'''
    mock_client.models.generate_content.return_value = mock_response

    with patch("engine.evaluator._get_client", return_value=mock_client):
        goals = [{"task": "Build feature X", "complexity": 4, "dharma_multiplier": 1.1}]
        result = await evaluate_daily_execution_with_ai("swarit", goals, "Shipped PR #1")
        assert len(result["task_evaluations"]) == 1
        assert result["spontaneous_bonus"] == 2.0
        assert result["praise_text"] == "Great work!"

@pytest.mark.asyncio
async def test_evaluate_daily_execution_with_ai_clamp_values():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '''{
        "task_evaluations": [
            {
                "task": "Crazy claims",
                "completion": 2.0,
                "complexity": 10,
                "dharma_multiplier": 5.0
            }
        ],
        "spontaneous_bonus": 10.0
    }'''
    mock_client.models.generate_content.return_value = mock_response

    with patch("engine.evaluator._get_client", return_value=mock_client):
        goals = []
        result = await evaluate_daily_execution_with_ai("swarit", goals, "Fixed everything")
        evals = result["task_evaluations"]
        assert evals[0]["completion"] == 1.0 # Clamped 0-1
        assert evals[0]["complexity"] == 5 # Clamped 1-5
        assert evals[0]["dharma_multiplier"] == 1.2 # Clamped 0.8-1.2
        assert result["spontaneous_bonus"] == 5.0 # Clamped max 5.0

@pytest.mark.asyncio
async def test_evaluate_daily_execution_with_ai_fallback_on_exception():
    mock_client = MagicMock()
    # Force exception
    mock_client.models.generate_content.side_effect = Exception("API error")
    with patch("engine.evaluator._get_client", return_value=mock_client):
        goals = [{"task": "Build feature X", "complexity": 4, "dharma_multiplier": 1.1}]
        result = await evaluate_daily_execution_with_ai("swarit", goals, "Shipped PR #1")
        # Should fallback to heuristic, with 1 item from goals
        assert len(result["task_evaluations"]) == 1
        assert result["task_evaluations"][0]["task"] == "Build feature X"

@pytest.mark.asyncio
async def test_evaluate_daily_execution_with_ai_fallback_on_exception_no_goals():
    mock_client = MagicMock()
    # Force exception
    mock_client.models.generate_content.side_effect = Exception("API error")
    with patch("engine.evaluator._get_client", return_value=mock_client):
        goals = []
        result = await evaluate_daily_execution_with_ai("swarit", goals, "Merged PR #12 and wrote a setup guide for the finvu integration")
        # Should fallback to heuristic
        assert len(result["task_evaluations"]) >= 1
        assert "Merged PR #12" in result["task_evaluations"][0]["task"]
