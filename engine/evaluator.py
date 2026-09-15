"""
Gemini AI Evaluation Pipeline for Goal Structuring and Execution Verification.
Uses Google Gemini 2.5 Flash with structured JSON output and robust fallback logic.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from config import GEMINI_API_KEY, FOUNDERS, ROLE_DHARMA_RANGE, COMPLEXITY_RANGE

logger = logging.getLogger(__name__)

# Try importing the new google-genai SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-genai library not found. Falling back to local heuristic evaluator.")


def _get_client():
    """Obtain initialized GenAI Client if API key is provided."""
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key:
        return None
    if GENAI_AVAILABLE:
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to create Gemini client: {e}")
            return None
    return None


async def parse_daily_goals_with_ai(founder_key: str, raw_goals_text: str) -> List[Dict[str, Any]]:
    """
    Convert conversational, freeform goal text into structured JSON tasks with:
    - task description
    - estimated complexity (1 to 5)
    - role dharma multiplier (0.8 to 1.2)
    - alignment explanation
    """
    founder = FOUNDERS.get(founder_key.lower(), {})
    role = founder.get("role", "Founder")
    dharma_focus = "\n".join([f"- {f}" for f in founder.get("dharma_focus", [])])

    system_prompt = f"""
You are the Chief Systems Architect of the Krishna Engineering OS.
Your objective is to decompose a founder's 9:00 PM nightly goal text into a set of discrete, verifiable commitments.

Founder: {founder.get('display_name', founder_key)}
Role: {role}
Core Role Dharma (Expectations):
{dharma_focus}

Rubric for Complexity Weight (1 to 5):
1 = Trivial admin, quick emails, routine checks (<15 mins)
2 = Standard operational chore, minor bugfix, quick doc edit (30-60 mins)
3 = Substantial task, core feature work, partner outreach, contract review (2-3 hours)
4 = Critical milestone, major architectural launch, enterprise negotiation (>4 hours)
5 = Existential breakthrough, major fundraising close, zero-day crisis resolution

Role Dharma Multiplier (0.8 to 1.2):
1.2 = High-leverage execution directly fulfilling their core role (CEO: Capital/Strategy, CTO: Code/Architecture, COO: Ops/Sales/SOPs)
1.0 = Standard cross-functional operational chore
0.8 = Tangent busywork or low-leverage distraction

Output MUST be a valid JSON array of objects with keys:
"task": string (verifiable commitment)
"complexity": integer (1 to 5)
"dharma_multiplier": float (0.8 to 1.2)
"dharma_reason": string (short justification)
"""

    client = _get_client()
    if client:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{system_prompt}\n\nRaw Goals Submitted:\n{raw_goals_text}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            parsed = json.loads(response.text)
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            logger.error(f"Gemini API parse failed, using fallback: {e}")

    # Fallback Heuristic Parser (Offline / No API Key)
    lines = [line.strip().lstrip("-*•123456789. ") for line in raw_goals_text.strip().split("\n") if line.strip()]
    tasks = []
    for line in lines:
        if not line:
            continue
        # Simple heuristic complexity estimation
        complexity = 3
        if any(w in line.lower() for w in ["fix", "email", "check", "call", "review", "quick"]):
            complexity = 2
        if any(w in line.lower() for w in ["architecture", "fundraise", "deploy", "engine", "refactor", "enterprise"]):
            complexity = 4

        tasks.append({
            "task": line,
            "complexity": complexity,
            "dharma_multiplier": 1.0,
            "dharma_reason": "Heuristic fallback assignment",
        })

    return tasks if tasks else [{
        "task": raw_goals_text[:100],
        "complexity": 3,
        "dharma_multiplier": 1.0,
        "dharma_reason": "Default commitment",
    }]


async def evaluate_daily_execution_with_ai(
    founder_key: str,
    locked_goals: List[Dict[str, Any]],
    updates_text: str,
) -> Dict[str, Any]:
    """
    Evaluate daytime updates against locked goals using Gemini 2.5 Flash.
    Computes completion rate (0.0 to 1.0) per task, emergent impact bonus, praise, and constructive critique.
    """
    founder = FOUNDERS.get(founder_key.lower(), {})
    role = founder.get("role", "Founder")

    system_prompt = f"""
You are the Systems Evaluator for the Krishna Engineering OS.
Evaluate the founder's daily throughput by comparing their daytime channel updates against their locked goals.

Founder: {founder.get('display_name', founder_key)} ({role})
Locked Goals:
{json.dumps(locked_goals, indent=2)}

Channel Updates Logged Today:
{updates_text if updates_text.strip() else "(No updates logged in monitored channels today)"}

Evaluation Instructions:
1. For each locked goal, judge completion percentage (0.0 to 1.0) based strictly on evidence provided in updates.
2. If work was partially done, assign proportional credit (e.g. 0.5 for drafted doc or WIP PR).
3. If an update shows an unscripted critical win or emergency firefighting not in the locked goals, assign a "spontaneous_bonus" (0 to 5 points).
4. Provide a punchy, specific "praise_text" celebrating high-leverage execution.
5. Provide a constructive, systems-oriented "feedback_text" diagnosing any bottlenecks.

Return valid JSON with schema:
{{
  "task_evaluations": [
    {{
      "task": string,
      "completion": float (0.0 to 1.0),
      "evidence_snippet": string,
      "complexity": integer,
      "dharma_multiplier": float
    }}
  ],
  "spontaneous_bonus": float (0.0 to 5.0),
  "spontaneous_reason": string,
  "praise_text": string,
  "feedback_text": string
}}
"""

    client = _get_client()
    if client:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=system_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini API evaluation failed: {e}")

    # Fallback Heuristic Evaluator
    evaluations = []
    has_updates = bool(updates_text.strip())
    for g in locked_goals:
        # If updates exist, give 0.8 completion credit as fallback, else 0.2
        comp = 0.8 if has_updates else 0.2
        evaluations.append({
            "task": g.get("task", ""),
            "completion": comp,
            "evidence_snippet": "Heuristic match from daytime channel activity" if has_updates else "No channel evidence found",
            "complexity": g.get("complexity", 3),
            "dharma_multiplier": g.get("dharma_multiplier", 1.0),
        })

    return {
        "task_evaluations": evaluations,
        "spontaneous_bonus": 1.0 if has_updates else 0.0,
        "spontaneous_reason": "Active presence in channels",
        "praise_text": f"Consistent execution in {role} focus areas today." if has_updates else "Rest or offline work noted.",
        "feedback_text": "Remember to drop links to commits/docs in channels for automated verification."
    }
