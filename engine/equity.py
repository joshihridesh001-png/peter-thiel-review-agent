"""
Dynamic Earnout & Equity Evolution Engine.
Implements 24-Month Slicing Pie Tranches, Safety Floor, Treasury Diversion, and Strict Mathematical Conservation.
"""

from typing import Dict, Any, Tuple
from config import (
    TOTAL_UNVESTED_POOL,
    VESTING_HORIZON_MONTHS,
    MONTHLY_TRANCHE_EQUITY,
    TARGET_UNVESTED_WEIGHTS,
    PERFORMANCE_SAFETY_FLOOR,
    FOUNDERS,
)


def compute_monthly_equity_split(
    month_index: int,
    year_month: str,
    cto_score: float,
    coo_score: float,
    current_cto_equity: float,
    current_coo_equity: float,
) -> Dict[str, Any]:
    """
    Computes monthly equity award for Month M (1 to 24) from the monthly tranche Delta E (~2.2917%).

    Enforces:
    1. Continuous relative score ratio: Ratio_A = S_A / (S_A + S_B)
    2. Performance Safety Floor (60%): If a founder's output is below 60% of their target baseline,
       the unearned delta is diverted to the Company Treasury Reserve, NOT to the other founder.
    3. Mathematical conservation: CEO (45%) + CTO_cumulative + COO_cumulative + Treasury_cumulative = 100.0%
    """
    total_score = cto_score + coo_score

    # Default to baseline target weights if no scores recorded
    if total_score <= 0.001:
        ratio_cto = TARGET_UNVESTED_WEIGHTS["swarit"]
        ratio_coo = TARGET_UNVESTED_WEIGHTS["rahul"]
    else:
        ratio_cto = cto_score / total_score
        ratio_coo = coo_score / total_score

    # Expected baseline target shares for this month
    target_cto_share = MONTHLY_TRANCHE_EQUITY * TARGET_UNVESTED_WEIGHTS["swarit"]  # ~1.0417%
    target_coo_share = MONTHLY_TRANCHE_EQUITY * TARGET_UNVESTED_WEIGHTS["rahul"]   # ~1.2500%

    # Raw earned shares before floor check
    raw_cto_share = MONTHLY_TRANCHE_EQUITY * ratio_cto
    raw_coo_share = MONTHLY_TRANCHE_EQUITY * ratio_coo

    treasury_diverted = 0.0

    # Safety floor enforcement
    # If a founder achieves less than 60% of their target baseline, cap their peer's cannibalization
    min_cto_floor = target_cto_share * PERFORMANCE_SAFETY_FLOOR
    min_coo_floor = target_coo_share * PERFORMANCE_SAFETY_FLOOR

    awarded_cto = raw_cto_share
    awarded_coo = raw_coo_share

    if raw_cto_share < min_cto_floor:
        # CTO had a severe drop/absence; prevent COO from capturing all unearned shares
        deficit = min_cto_floor - raw_cto_share
        awarded_cto = raw_cto_share
        treasury_diverted += deficit
        awarded_coo -= deficit

    elif raw_coo_share < min_coo_floor:
        # COO had a severe drop/absence; prevent CTO from capturing all unearned shares
        deficit = min_coo_floor - raw_coo_share
        awarded_coo = raw_coo_share
        treasury_diverted += deficit
        awarded_cto -= deficit

    awarded_cto = max(0.0, awarded_cto)
    awarded_coo = max(0.0, awarded_coo)

    new_cumulative_cto = current_cto_equity + awarded_cto
    new_cumulative_coo = current_coo_equity + awarded_coo
    ceo_equity = FOUNDERS["hridesh"]["vested_equity"]  # Strictly 45.0%

    return {
        "month_index": month_index,
        "year_month": year_month,
        "monthly_tranche": round(MONTHLY_TRANCHE_EQUITY, 5),
        "cto_monthly_score": round(cto_score, 2),
        "coo_monthly_score": round(coo_score, 2),
        "ratio_cto": round(ratio_cto, 4),
        "ratio_coo": round(ratio_coo, 4),
        "equity_awarded_cto": round(awarded_cto, 5),
        "equity_awarded_coo": round(awarded_coo, 5),
        "treasury_diverted": round(treasury_diverted, 5),
        "cumulative_cto": round(new_cumulative_cto, 5),
        "cumulative_coo": round(new_cumulative_coo, 5),
        "ceo_equity": ceo_equity,
        "total_allocated": round(ceo_equity + new_cumulative_cto + new_cumulative_coo, 5),
    }
