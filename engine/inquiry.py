"""
Pre-scoring Context Inquiry Engine for Peter Thiel Review Agent.
Scans daytime updates and commitments at 7:15 PM IST to identify ambiguous work,
unbacked claims, or bare file drops, and generates at most 1 direct question per founder.
"""

import json
import logging
import asyncio
from typing import Dict, Any, List
from config import FOUNDERS
from database.models import get_goals_for_date, get_updates_for_date_range
from engine.evaluator import _get_client

logger = logging.getLogger(__name__)

AUDIT_PROMPT_TEMPLATE = """
You are Peter Thiel acting as a helpful, direct startup coach for Calcrum.
It is 7:15 PM IST. You are doing a quick check before the 8:00 PM scorecard.

CRITICAL LANGUAGE RULE (10-YEAR-OLD PLAIN ENGLISH):
- Super simple everyday words.
- Short sentences.
- NO corporate jargon.

Founder: {name} ({role})
Today's Commitments:
{goals}

Today's Logged Evidence & Files:
{evidence}

Task:
Compare commitments against the logged evidence.
Is there an ambiguous task, a bare uploaded file, or an unverified high-impact claim?
If YES, formulate EXACTLY ONE simple, direct question asking for a concrete, falsifiable fact (e.g. "Did the client join the call or was it delayed?" or "Did you send the emails from that CSV, or is it queued for tomorrow?").
If NO (everything is crystal clear, or founder did zero work), return needs_clarification: false.

Return JSON:
{{
  "needs_clarification": true/false,
  "question": "string"
}}
"""

async def generate_pre_scoring_inquiries(score_date: str) -> Dict[str, str]:
    """Scan day's updates and formulate at most 1 question per founder with context gaps."""
    client = _get_client()
    if not client:
        return {}

    start_time = f"{score_date}T05:00:00"
    end_time = f"{score_date}T19:15:00"

    candidate_models = [
        'gemini-3.8-flash',
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-flash-latest',
    ]

    inquiries = {}

    for key, info in FOUNDERS.items():
        goals_record = await get_goals_for_date(key, score_date)
        locked_goals = goals_record["parsed_goals"] if goals_record else []
        updates = await get_updates_for_date_range(key, start_time, end_time)

        if not updates and not locked_goals:
            continue

        evidence_text = "\n".join([f"- {u['content'][:300]}" for u in updates]) if updates else "(No daytime updates)"
        goals_text = "\n".join([f"- {g.get('task', '')}" for g in locked_goals]) if locked_goals else "(No locked goals)"

        prompt = AUDIT_PROMPT_TEMPLATE.format(
            name=info.get("display_name", key),
            role=info.get("role", "Founder"),
            goals=goals_text,
            evidence=evidence_text,
        )

        def _call_gemini():
            from google.genai import types
            for model_name in candidate_models:
                try:
                    return client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Inquiry model {model_name} failed: {e}")
            return None

        try:
            resp = await asyncio.to_thread(_call_gemini)
            if resp and resp.text:
                parsed = json.loads(resp.text)
                if parsed.get("needs_clarification") and parsed.get("question"):
                    inquiries[key] = parsed["question"].strip()
        except Exception as e:
            logger.warning(f"Inquiry gap check failed for {key}: {e}")

    return inquiries
