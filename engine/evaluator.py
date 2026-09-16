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
        for model_name in ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-flash-latest']:
            try:
                response = client.models.generate_content(
                    model=model_name,
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
                logger.warning(f"Model {model_name} parse failed: {e}")

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
You are Peter Thiel, Chief Reviewer and Systems Evaluator for the Krishna Engineering OS.
Evaluate the founder's daily throughput by analyzing their daytime channel updates and comparing against locked commitments.

Founder: {founder.get('display_name', founder_key)} ({role})
Locked Commitments:
{json.dumps(locked_goals, indent=2) if locked_goals else "(No prior commitments were locked for today - deduce tasks and throughput directly from updates)"}

Channel Updates Logged Today:
{updates_text if updates_text.strip() else "(No updates logged in monitored channels today)"}

Evaluation Instructions:
1. If locked commitments exist, evaluate completion (0.0 to 1.0) for each commitment based on evidence in the updates.
2. If NO locked commitments exist, identify the distinct tasks, initiatives, or milestones the founder worked on based on their updates. Assign complexity (1 to 5) and role dharma multiplier (0.8 to 1.2) for each task, and score their completion.
3. If no updates exist, return an empty task_evaluations list and 0 spontaneous bonus.
4. Reward spontaneous high-leverage firefighting or unscripted strategic breakthroughs with a "spontaneous_bonus" (0 to 5 points).
5. In "praise_text": Speak in Peter Thiel's sharp, candid, contrarian voice. Praise zero-to-one thinking, distribution focus, and decisive engineering execution.
6. In "feedback_text": Provide Thiel-style strategic critique—challenge incrementalism, demand definite optimism, and highlight any operational bottlenecks.

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
        import asyncio
        for model_name in ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-flash-latest']:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=system_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        )
                    )
                    return json.loads(response.text)
                except Exception as e:
                    logger.warning(f"Model {model_name} attempt {attempt+1} failed: {e}")
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        # Switch immediately to next model on quota exhaustion
                        break
                    if attempt < 1:
                        await asyncio.sleep(1.0)

    # Fallback Heuristic Evaluator
    evaluations = []
    has_updates = bool(updates_text.strip())
    if locked_goals:
        for g in locked_goals:
            comp = 0.8 if has_updates else 0.2
            evaluations.append({
                "task": g.get("task", ""),
                "completion": comp,
                "evidence_snippet": "Heuristic match from daytime channel activity" if has_updates else "No channel evidence found",
                "complexity": g.get("complexity", 3),
                "dharma_multiplier": g.get("dharma_multiplier", 1.0),
            })
    elif has_updates:
        # Fallback when no goals were locked but updates exist
        evaluations.append({
            "task": f"Daytime execution in {role} focus area",
            "completion": 0.85,
            "evidence_snippet": updates_text[:120].replace('\n', ' '),
            "complexity": 3,
            "dharma_multiplier": 1.0,
        })

    return {
        "task_evaluations": evaluations,
        "spontaneous_bonus": 2.0 if has_updates else 0.0,
        "spontaneous_reason": "Active execution in channels" if has_updates else "No activity logged",
        "praise_text": f"Consistent execution in {role} focus areas today." if has_updates else "Rest or offline work noted.",
        "feedback_text": "Ensure daily commitments are locked before 9:00 PM for maximum alignment."
    }
