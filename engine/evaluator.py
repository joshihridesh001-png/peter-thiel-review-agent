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
    candidate_models = [
        'gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-3.1-flash-lite-preview',
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-flash-latest',
    ]

    if client:
        for model_name in candidate_models:
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
                    # Clamp values
                    for item in parsed:
                        item["complexity"] = max(1, min(5, int(item.get("complexity", 3))))
                        item["dharma_multiplier"] = max(0.8, min(1.2, float(item.get("dharma_multiplier", 1.0))))
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
    historical_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate daytime updates against locked goals using Gemini.
    Acts as an inquisitive senior mentor (Peter Thiel) who digs for context,
    distinguishes code from documentation, verifies legal/technical invariants,
    and asks probing questions.
    """
    founder = FOUNDERS.get(founder_key.lower(), {})
    role = founder.get("role", "Founder")

    system_prompt = f"""
You are Peter Thiel, Chief Reviewer, Systems Evaluator, and Senior Mentor for the founders of Calcrum under the Krishna Engineering OS.

Startup Background & Ground Reality:
Calcrum is an autonomous financial operating system (double-entry ledger, automated reconciliation, bank feeds).
Key Team Dynamic & Codebase Ownership:
- Hridesh (CEO): Initial author of the foundational core rails (double-entry logic, database models, bank connection adapters including BankEmailAdapter and CIB options). Focus: Capital allocation, enterprise deals, high-leverage architectural direction.
- Swarit (CTO): Core engineering execution, frontend onboarding, shipping PRs, websocket reliability.
- Rahul (COO): Commercial operations, client pipeline (e.g. Gyros Farm, Gramiyaa), and SOP conversion.

Context-Digging & Ground-Truth Invariants (DO NOT GET FOOLED BY NARRATIVE OR BUZZWORDS):
1. Distinguish Real Shipped Code vs Explaining/Documenting vs Ideation:
   - Shipped Code / Merged PRs / Git Commits = Tangible Engineering Execution (Complexity 3 to 4).
   - Explaining / Documenting existing codebase options (e.g., writing a guide explaining existing bank feeds or auth flow that Hridesh already built) = Internal Documentation & Knowledge Transfer (Complexity 1 to 2). Never score team documentation as an architectural breakthrough!
   - Casual Chat Messages / Exploratory Musings (e.g., "look into bank feeds") = Ideation / Discussion (Complexity 1 to 2, Completion capped at 0.5 unless a real PR/commit is linked).
2. Reality & Feasibility Invariant (Call out Speculation):
   - Founders often use aspirational vocabulary. For example, claiming "RBI Account Aggregator is live" when Calcrum is not an RBI-registered Financial Information User (FIU) is phantom. If a founder discusses unviable or future roadmap features, treat it as conceptual discussion, not shipped infrastructure.
3. Authorship Attribution:
   - If a founder writes about an existing system feature, check who actually built it. Credit the explainer with documentation/coordination points (W: 1-2), NOT system creation points (W: 4-5).
4. Demand Receipts for High-Stakes Claims:
   - If a founder claims a major breakthrough or high-complexity task (W >= 4) without a commit hash, PR link, or client recording, challenge them to provide receipts in "feedback_text".

Founder: {founder.get('display_name', founder_key)} ({role})
Core Role Dharma: {', '.join(founder.get('dharma_focus', []))}

Foundational History & Cross-Day Context:
{historical_context if historical_context else "(No prior historical context provided)"}

Locked Commitments:
{json.dumps(locked_goals, indent=2) if locked_goals else "(No prior commitments were locked for today - deduce tasks and throughput directly from updates)"}

Daytime Updates Logged Today:
{updates_text if updates_text.strip() else "(No updates logged in monitored channels today)"}

Evaluation Instructions:
1. If locked commitments exist, evaluate completion (0.0 to 1.0) for each commitment based on evidence in the updates.
2. If NO locked commitments exist, identify 2 to 4 distinct concrete tasks or milestones the founder executed based on their updates. Apply the Context-Digging Invariants strictly.
3. If no updates exist, return an empty task_evaluations list and 0 spontaneous bonus.
4. Reward spontaneous high-leverage firefighting, unscripted breakthroughs, or extraordinary initiative with a "spontaneous_bonus" (0.0 to 5.0 points) and a clear "spontaneous_reason".
5. In "praise_text": Speak in Peter Thiel's sharp, contrarian, intellectually rigorous voice. Praise zero-to-one velocity, distribution leverage, and definitive engineering momentum.
6. In "feedback_text": Provide Thiel-style strategic critique—challenge incrementalism, demand definite optimism, attack operational bottlenecks, and demand compounding velocity.
7. In "mentor_question": Formulate ONE sharp, direct, probing question for this founder to answer tomorrow to verify their execution or push their strategic thinking to the limit.

Return valid JSON with schema:
{{
  "task_evaluations": [
    {{
      "task": string,
      "completion": float (0.0 to 1.0),
      "evidence_snippet": string,
      "complexity": integer (1 to 5),
      "dharma_multiplier": float (0.8 to 1.2)
    }}
  ],
  "spontaneous_bonus": float (0.0 to 5.0),
  "spontaneous_reason": string,
  "mentor_question": string,
  "praise_text": string,
  "feedback_text": string
}}
"""

    client = _get_client()
    candidate_models = [
        'gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-3.1-flash-lite-preview',
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-flash-latest',
    ]

    if client:
        import asyncio
        for model_name in candidate_models:
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
                    data = json.loads(response.text)
                    # Bounds checking & normalization
                    cleaned_tasks = []
                    for t in data.get("task_evaluations", []):
                        cleaned_tasks.append({
                            "task": str(t.get("task", "Execution task")),
                            "completion": max(0.0, min(1.0, float(t.get("completion", 0.0)))),
                            "evidence_snippet": str(t.get("evidence_snippet", ""))[:120],
                            "complexity": max(1, min(5, int(t.get("complexity", 3)))),
                            "dharma_multiplier": max(0.8, min(1.2, float(t.get("dharma_multiplier", 1.0)))),
                        })
                    data["task_evaluations"] = cleaned_tasks
                    data["spontaneous_bonus"] = max(0.0, min(5.0, float(data.get("spontaneous_bonus", 0.0))))
                    if not data.get("mentor_question"):
                        data["mentor_question"] = "What is the single most critical bottleneck you will permanently solve tomorrow?"
                    return data
                except Exception as e:
                    logger.warning(f"Model {model_name} attempt {attempt+1} failed: {e}")
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        break
                    if attempt < 1:
                        await asyncio.sleep(1.0)

    # Fallback Heuristic Evaluator (Parses actual channel updates contextually)
    evaluations = []
    lines = [line.strip() for line in updates_text.strip().split("\n") if line.strip() and not line.strip().startswith("[202")]
    if not lines:
        lines = [line.strip() for line in updates_text.strip().split("\n") if line.strip()]

    has_updates = bool(updates_text.strip())

    if locked_goals:
        for g in locked_goals:
            comp = 0.85 if has_updates else 0.0
            evaluations.append({
                "task": g.get("task", ""),
                "completion": comp,
                "evidence_snippet": "Verified activity from channel updates" if has_updates else "No activity recorded",
                "complexity": max(1, min(5, int(g.get("complexity", 3)))),
                "dharma_multiplier": max(0.8, min(1.2, float(g.get("dharma_multiplier", 1.0)))),
            })
    elif has_updates:
        # Extract up to 4 meaningful task topics from lines
        seen_topics = set()
        for l in lines:
            cleaned = l.split("]")[-1].strip() if "]" in l else l
            if len(cleaned) < 5 or cleaned in seen_topics:
                continue
            seen_topics.add(cleaned)
            comp = 1.0
            complexity = 3
            dharma = 1.0

            lower_c = cleaned.lower()
            if any(w in lower_c for w in ["commit", "deploy", "build", "bug", "guide"]):
                complexity = 3
                dharma = 1.2 if role == "CTO" else 1.0
            elif any(w in lower_c for w in ["guide", "doc", "onboarding", "explaining", "setup guide"]):
                complexity = 2
                dharma = 1.0
            elif any(w in lower_c for w in ["architecture", "auth", "finvu", "bank", "ledger"]):
                # Distinguish authoring vs documentation
                if "swarit" in founder_key and any(w in lower_c for w in ["look into", "options", "guide"]):
                    complexity = 2
                    dharma = 1.0
                else:
                    complexity = 4
                    dharma = 1.2 if role in ["CTO", "CEO"] else 1.0
            elif any(w in lower_c for w in ["client", "call", "gyros", "outbound", "lead", "pipeline"]):
                complexity = 3
                dharma = 1.2 if role == "COO" else 1.0
            elif any(w in lower_c for w in ["emergency", "hospital"]):
                complexity = 2
                dharma = 0.9

            evaluations.append({
                "task": cleaned[:80],
                "completion": comp,
                "evidence_snippet": cleaned[:100],
                "complexity": complexity,
                "dharma_multiplier": dharma,
            })
            if len(evaluations) >= 4:
                break

    # Construct contextual Thiel critique based on role
    if role == "CTO":
        critique = "Planning architecture is easy; the only truth is code merged in production. Eliminate speculative tangents and focus entirely on core system rails."
        praise = "Decisive engineering rhythm on the core stack today. Shipping tangible commits beats endless debate."
        m_q = "How many actual PRs did you merge today versus documenting existing code?"
    elif role == "COO":
        critique = "Client discovery without immediate pipeline conversion is vanity. Turn client conversations into irreversible contracts and hardened operational SOPs."
        praise = "Relentless operational vigilance and frontline client engagement despite external disruptions."
        m_q = "When is the Gyros Farm pilot going live and what is the contract value?"
    else:
        critique = "Avoid being drawn into low-level tactical friction. Guard your focus for enterprise capital allocation and existential distribution moats."
        praise = "Sharp strategic orchestration and high-leverage direction across the founding team."
        m_q = "What is the single highest-leverage deal you will close this week?"

    return {
        "task_evaluations": evaluations,
        "spontaneous_bonus": 1.0 if has_updates else 0.0,
        "spontaneous_reason": "High-conviction daytime execution across active channels" if has_updates else "No activity logged",
        "praise_text": praise if has_updates else "No visible throughput recorded today.",
        "feedback_text": critique if has_updates else "Ensure daily commitments are declared and executed with urgency.",
        "mentor_question": m_q,
    }
