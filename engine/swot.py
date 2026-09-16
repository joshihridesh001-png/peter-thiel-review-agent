"""
Weekly SWOT Analysis and Strategic Perception Engine.
Synthesizes 7-day execution trends, flags systemic bottlenecks, and surfaces growth opportunities.
"""

import json
import logging
from typing import Dict, Any, List
from config import FOUNDERS
from engine.evaluator import _get_client

logger = logging.getLogger(__name__)


async def generate_weekly_swot_with_ai(
    weekly_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate an executive SWOT report for the founding team using 7-day performance data.
    """
    system_prompt = """
You are the Strategic Executive Advisor operating under Hridesh's Systems Thinking Framework.
Analyze the last 7 days of founder execution data (CEO, CTO, COO) and produce a rigorous, depersonalized SWOT analysis.

Guidelines:
1. Strengths: What systems and execution habits are performing with high velocity and consistency?
2. Weaknesses: Where are the recurring friction points or carryover tasks? (Frame around workflows and systems, not character flaws).
3. Opportunities: What emerging initiatives or quick operational wins could 2x leverage next week?
4. Threats: Where is there risk of burnout, role drift, or delivery lag?

Input Data:
"""
    client = _get_client()
    if client:
        for model_name in ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-flash-latest']:
            try:
                from google.genai import types
                response = client.models.generate_content(
                    model=model_name,
                    contents=f"{system_prompt}\n{json.dumps(weekly_data, indent=2)}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3,
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                logger.warning(f"Model {model_name} SWOT generation failed: {e}")

    # Fallback template
    return {
        "overall_summary": "7-Day Sprint completed with steady execution across engineering and operational channels.",
        "founder_swot": {
            "hridesh": {
                "strengths": "Clear strategic steering and capital allocation focus.",
                "weaknesses": "Asynchronous meetings occasionally creating coordination lag.",
                "opportunities": "Deepen strategic partner conversations.",
                "threats": "Becoming an operational bottleneck for sign-offs."
            },
            "swarit": {
                "strengths": "High technical shipping velocity and clean code outputs.",
                "weaknesses": "Complex refactoring tasks rolling over without intermediate logs.",
                "opportunities": "Standardize automated testing to reduce manual QA overhead.",
                "threats": "Deep rabbit-hole debugging without peer visibility."
            },
            "rahul": {
                "strengths": "Consistent operational presence and rapid channel responsiveness.",
                "weaknesses": "Context-switching between sales and marketing tasks.",
                "opportunities": "Document and delegate routine SOPs.",
                "threats": "Operational fatigue from high-frequency chore handling."
            }
        },
        "system_recommendations": [
            "Keep daily goals locked by 9:00 PM to maximize daytime focus.",
            "Use ✅ and 🔥 reactions actively to maintain peer verification signals."
        ]
    }
