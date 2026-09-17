"""
Krishna Engineering OS Mathematical Scoring Engine.
Calculates daily scores, applies peer reaction modifiers, and filters against task-stuffing.
"""

from typing import List, Dict, Any, Tuple
from config import PEER_FACTOR_RANGE, PEER_EMOJIS, BONUS_POINTS_MAX


def calculate_peer_multiplier(reactions: List[Dict[str, Any]], author_discord_id: int) -> Tuple[float, Dict[str, int]]:
    """
    Calculate M_peer multiplier based on co-founder emoji reactions.
    Self-reactions are strictly excluded.
    Clamped to [0.8, 1.2].
    """
    counts = {"✅": 0, "🔥": 0, "⚠️": 0}
    delta = 0.0

    for r in reactions:
        # Prevent self-reaction exploitation
        if r.get("reactor_discord_id") == author_discord_id:
            continue
        emoji = r.get("emoji", "")
        if emoji in PEER_EMOJIS:
            counts[emoji] = counts.get(emoji, 0) + 1
            delta += PEER_EMOJIS[emoji]

    raw_multiplier = 1.0 + delta
    min_factor, max_factor = PEER_FACTOR_RANGE
    clamped_multiplier = max(min_factor, min(max_factor, raw_multiplier))
    return round(clamped_multiplier, 3), counts


def compute_daily_score(
    task_evaluations: List[Dict[str, Any]],
    reactions: List[Dict[str, Any]],
    author_discord_id: int,
    spontaneous_bonus: float = 0.0,
) -> Dict[str, Any]:
    """
    Computes S_daily using the Krishna OS formula:
    S_daily = (SUM(C_i * W_i * A_dharma) * M_peer) + I_bonus

    Includes anti-task-stuffing: low-complexity tasks (W_i=1) capped at 3 with diminishing returns.
    """
    weighted_task_sum = 0.0
    task_details = []
    w1_count = 0

    for t in task_evaluations:
        c = float(t.get("completion", 0.0))
        w = float(t.get("complexity", 3))
        a = float(t.get("dharma_multiplier", 1.0))

        # Anti-task-stuffing rule: limit trivial tasks
        discount = 1.0
        if w <= 1.0:
            w1_count += 1
            if w1_count > 3:
                discount = 0.25  # 75% penalty on 4th+ trivial chore

        task_points = c * w * a * discount
        weighted_task_sum += task_points

        task_details.append({
            "task": t.get("task", ""),
            "completion": c,
            "complexity": w,
            "dharma_multiplier": a,
            "discount_applied": discount,
            "task_points": round(task_points, 2),
            "evidence": t.get("evidence_snippet", ""),
            "score_reason": t.get("score_reason", t.get("evidence_snippet", "")),
        })

    # Calculate peer factor
    peer_multiplier, emoji_counts = calculate_peer_multiplier(reactions, author_discord_id)

    # Clamp spontaneous bonus
    clamped_bonus = min(BONUS_POINTS_MAX, max(0.0, float(spontaneous_bonus)))

    # Final Krishna OS score
    final_score = (weighted_task_sum * peer_multiplier) + clamped_bonus

    return {
        "raw_task_sum": round(weighted_task_sum, 2),
        "peer_multiplier": peer_multiplier,
        "emoji_counts": emoji_counts,
        "bonus_points": round(clamped_bonus, 2),
        "final_score": round(final_score, 2),
        "task_breakdown": task_details,
    }
