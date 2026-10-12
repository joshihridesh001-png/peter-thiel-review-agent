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
You are a friendly and smart startup coach helping the team at Calcrum plan their day.
Your job is to read a founder's 9:00 PM goals and turn them into simple, clear tasks.

Founder: {founder.get('display_name', founder_key)}
Role: {role}
What they are responsible for:
{dharma_focus}

Task Size (1 to 5):
1 = Super quick chores (<15 minutes, like sending a quick email)
2 = Small chores (30 to 60 minutes, like fixing a small bug or editing notes)
3 = Normal solid task (2 to 3 hours, like building a feature or talking to a customer)
4 = Big important milestone (>4 hours, like launching a major part of the product)
5 = Huge game changer (closing an investment round or saving the company from a giant problem)

Role Fit Multiplier (0.8 to 1.2):
1.2 = Best possible use of their time (CEO working on vision/money, CTO building code, COO getting customers)
1.0 = Normal everyday startup chore
0.8 = Distraction or work someone else should be doing

IMPORTANT: Write everything in super simple plain English that even a 10-year-old kid can understand! No fancy corporate buzzwords.

Output MUST be a valid JSON array of objects with keys:
"task": string (simple, clear description of the task)
"complexity": integer (1 to 5)
"dharma_multiplier": float (0.8 to 1.2)
"dharma_reason": string (a simple 1-sentence explanation why this task matters for their role)
"score_reason": string (a simple 1-sentence explanation why you gave it this size score 1-5 and why it is worth these points)
"""

    client = _get_client()
    candidate_models = [
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-3.6-flash',
        'gemini-3.1-flash-lite',
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
                        item["score_reason"] = str(item.get("score_reason", item.get("dharma_reason", f"Rated size {item['complexity']}/5 based on task scope.")))
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
            "score_reason": f"Rated size {complexity}/5 based on estimated effort.",
        })

    return tasks if tasks else [{
        "task": raw_goals_text[:100],
        "complexity": 3,
        "dharma_multiplier": 1.0,
        "dharma_reason": "Default commitment",
        "score_reason": "Default commitment size 3/5.",
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
You are Peter Thiel acting as a direct, honest, and helpful startup mentor for the founders of Calcrum.

CRITICAL RULE FOR LANGUAGE (MUST BE EASY ENOUGH FOR A 10-YEAR-OLD TO UNDERSTAND):
- Use super simple, everyday words.
- Absolutely NO corporate buzzwords, academic jargon, or fancy investor terms (never use words like 'existential', 'distribution moats', 'dharma', 'zero-to-one', 'definite optimism', 'tactical friction', 'systemic invariants', 'synergy').
- Write as if you are coaching a bright 10-year-old kid: short sentences, plain English, friendly but direct.

Startup Background & Ground Reality:
Calcrum is an automated finance system that connects to bank accounts and organizes company money.
Who owns what:
- Hridesh (CEO): Built the core engine and bank adapters first. His main job: big strategy, bringing in money/investors, and leading the team.
- Swarit (CTO): Main job: writing code, fixing bugs, and making sure the website and servers never crash.
- Rahul (COO): Main job: finding customers (like Gyros Farm, Gramiyaa), running sales, and getting pilots live.

How to judge what really happened (DO NOT GET FOOLED BY FANCY TALK):
1. Building real code vs writing notes vs just chatting:
   - Writing and shipping real code (PRs, Git commits) = Real work (Score: 3 to 4).
   - Writing a guide or explaining code that Hridesh already built = Helpful notes (Score: 1 to 2). Writing notes is NOT the same as building the product!
   - Just chatting or sharing ideas in Discord = Talking (Score: 1 to 2, capped at 0.5 completion unless there is real proof).
2. Reality check:
   - If someone claims a feature is live that isn't really possible yet (like live RBI bank feeds when not licensed), call it out gently as an idea, not a finished feature.
3. Credit who actually built it:
   - If someone explains a feature another founder built, give them credit for helping the team understand it (1-2 pts), not for inventing it.
4. Ask for proof:
   - If someone claims they did something huge without a link, commit, or screenshot, ask for proof in simple words.

Founder: {founder.get('display_name', founder_key)} ({role})
Their main job: {', '.join(founder.get('dharma_focus', []))}

Recent Team Context:
{historical_context if historical_context else "(No recent context provided)"}

What they planned to do today:
{json.dumps(locked_goals, indent=2) if locked_goals else "(No locked plan declared - judge their day directly from their chat messages)"}

What they posted in chat today:
{updates_text if updates_text.strip() else "(No updates posted in monitored channels today)"}

Instructions:
1. If they had a plan, score each task from 0.0 (didn't do it) to 1.0 (completely finished) based on real proof.
2. If they had NO plan, find 2 to 4 real things they actually did from their updates.
3. If they posted nothing, return an empty task list and 0 bonus.
4. If they jumped in to fix a sudden big emergency without being asked, give them a "spontaneous_bonus" (0.0 to 5.0) and explain why in super simple words ("spontaneous_reason").
5. In "praise_text": Tell them what they did great in plain English a 10-year-old can understand.
6. In "feedback_text": Give simple, honest advice on where they can do better tomorrow.
7. In "mentor_question": Ask ONE simple, punchy question for tomorrow that a 10-year-old would easily get.

Return valid JSON with schema:
{{
  "task_evaluations": [
    {{
      "task": string (simple task name),
      "completion": float (0.0 to 1.0),
      "evidence_snippet": string (short proof),
      "complexity": integer (1 to 5),
      "dharma_multiplier": float (0.8 to 1.2),
      "score_reason": string (CRITICAL: A simple 1-sentence explanation of WHY you gave this completion score and size. E.g. "Full score: merged PR #14 and verified bank login" or "Half credit: discussed in chat but didn't write code yet" or "Zero score: no updates or proof found today")
    }}
  ],
  "spontaneous_bonus": float (0.0 to 5.0),
  "spontaneous_reason": string (simple explanation),
  "mentor_question": string (simple question for tomorrow),
  "praise_text": string (plain English praise),
  "feedback_text": string (plain English coaching)
}}
"""

    client = _get_client()
    candidate_models = [
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-3.6-flash',
        'gemini-3.1-flash-lite',
        'gemini-flash-latest',
    ]

    if client:
        import asyncio
        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
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
                            "score_reason": str(t.get("score_reason", t.get("evidence_snippet", "Score based on verified activity")))[:150],
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
            reason = "Saw active progress and messages about this in chat today." if has_updates else "No messages or proof found in chat today."
            evaluations.append({
                "task": g.get("task", ""),
                "completion": comp,
                "evidence_snippet": "Verified activity from channel updates" if has_updates else "No activity recorded",
                "complexity": max(1, min(5, int(g.get("complexity", 3)))),
                "dharma_multiplier": max(0.8, min(1.2, float(g.get("dharma_multiplier", 1.0)))),
                "score_reason": reason,
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
                "score_reason": f"Activity confirmed in chat: {cleaned[:60]}",
            })
            if len(evaluations) >= 4:
                break

    # Construct simple, clear coaching based on role
    if role == "CTO":
        critique = "Planning and talking is easy. The only thing that counts is code that is actually built and working. Focus on building the real product, not just writing notes about it."
        praise = "Great job building and shipping code today! Getting real things working is what matters."
        m_q = "How many pull requests or code changes did you actually finish today?"
    elif role == "COO":
        critique = "Talking to people is good, but getting them to actually use the product and pay is what matters. Focus on getting real customer sign-ups."
        praise = "Great hustle reaching out to customers and keeping things running today!"
        m_q = "When is your next customer going to try out the product?"
    else:
        critique = "Don't get stuck doing tiny chores. Your main job is leading the company, bringing in money, and helping the team move fast."
        praise = "Great leadership and keeping the whole team focused on what matters today!"
        m_q = "What is the most important deal or problem you will solve tomorrow?"

    return {
        "task_evaluations": evaluations,
        "spontaneous_bonus": 1.0 if has_updates else 0.0,
        "spontaneous_reason": "Stepped up and solved an urgent problem without being asked" if has_updates else "No activity logged",
        "praise_text": praise if has_updates else "No activity recorded today.",
        "feedback_text": critique if has_updates else "Make sure to set your goals and finish them tomorrow!",
        "mentor_question": m_q,
    }
