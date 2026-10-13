import pytest
from engine.scoring import compute_daily_score

def test_full_scoring_math():
    task_evals = [
        {
            "task": "Ingest Gyros Farm ledger from .md spec",
            "completion": 1.0,
            "complexity": 5,
            "dharma_multiplier": 1.2,
            "evidence_snippet": "Posted 2,763 entries with 0 drift verified in attached spec."
        }
    ]
    reactions = [{"reactor_discord_id": 999, "emoji": "🔥"}]
    res = compute_daily_score(task_evals, reactions, author_discord_id=111, spontaneous_bonus=2.0)
    
    assert res["raw_task_sum"] == 6.0
    assert res["peer_multiplier"] == 1.1
    assert res["final_score"] == pytest.approx(8.6, 0.1)
