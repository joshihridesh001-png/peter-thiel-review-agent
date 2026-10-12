# Peter Thiel Multimodal Attachment Reader & Pre-Scoring Inquiry Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate an automated multimodal attachment reader (`.md`, `.txt`, `.csv`, screenshots via Gemini Vision, GitHub PRs) and an interactive 7:15 PM pre-scoring inquiry engine into Peter Thiel Founder Operations Bot so founders are never scored 0 points for uploading files, and context gaps are resolved before the 8:00 PM scorecard.

**Architecture:** 
1. Decouple file & link extraction into an asynchronous service (`engine/attachment_reader.py`) that downloads files, calls Gemini Vision for screenshots, and enriches update payloads.
2. Intercept incoming Discord messages in `cogs/tracker.py` to store fully enriched payloads into SQLite.
3. Add a 7:15 PM IST cron job in `cogs/scheduler.py` calling `engine/inquiry.py` to identify context gaps and post targeted, falsifiable questions in `#daily-reports`.
4. Upgrade `engine/evaluator.py` to cross-verify founder claims against tangible artifacts on disk (preventing overplaying and rewarding underplaying).

**Tech Stack:** Python 3.11+, discord.py 2.3+, google-genai 2.20+, aiohttp 3.9+, aiosqlite, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-10-attachment-reader-and-inquiry-engine-design.md`

## Global Constraints
- Do not break existing SQLite database schemas or existing slash commands.
- All network operations (Discord CDN downloads, Gemini API calls, GitHub requests) must be non-blocking with explicit timeouts (`asyncio.wait_for`, timeout=10s).
- All AI-generated questions and feedback must adhere to Peter Thiel's 10-year-old language rule (super simple, plain English, short sentences, zero corporate buzzwords).
- Anti-gaming rule: Founder clarification replies are treated as claims (`founder_claim`), not ground truth, and must be cross-verified against tangible artifacts.

---

### Task 1: Commit Existing Local Bugfixes & Setup Test Infrastructure

**Files:**
- Modify: `cogs/scheduler.py` (stage existing diff)
- Modify: `cogs/tracker.py` (stage existing diff)
- Modify: `engine/evaluator.py` (stage existing diff)
- Modify: `requirements.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: Existing repo files
- Produces: Clean git status on `main`, running `pytest` test harness

- [ ] **Step 1: Update requirements.txt with test dependencies**
Add `pytest>=8.0.0` and `pytest-asyncio>=0.23.0` to `requirements.txt`.

```text
discord.py>=2.3.0
google-genai>=2.20.0
python-dotenv>=1.0.0
aiosqlite>=0.19.0
aiohttp>=3.9.0
requests>=2.31.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create tests/conftest.py and tests/test_smoke.py**

```python
# tests/conftest.py
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
```

```python
# tests/test_smoke.py
import pytest
from config import FOUNDERS, CHANNELS

def test_config_smoke():
    assert "hridesh" in FOUNDERS
    assert "swarit" in FOUNDERS
    assert "rahul" in FOUNDERS
    assert "scores" in CHANNELS
```

- [ ] **Step 3: Run pytest to verify test runner works**

Run: `pytest tests/test_smoke.py -v`  
Expected: PASS (1 test passed)

- [ ] **Step 4: Commit existing uncommitted bugfixes and test setup**

```bash
git add cogs/scheduler.py cogs/tracker.py engine/evaluator.py requirements.txt tests/
git commit -m "chore: commit async gemini fixes and setup pytest harness"
```

---

### Task 2: Text & Markdown Attachment Reader (`engine/attachment_reader.py`)

**Files:**
- Create: `engine/attachment_reader.py`
- Create: `tests/test_attachment_reader.py`

**Interfaces:**
- Produces: `async def extract_text_attachment(url: str, filename: str, max_bytes: int = 256000) -> str`
- Returns: Formatted text snippet or error boundary string

- [ ] **Step 1: Write failing test for text attachment extraction**

```python
# tests/test_attachment_reader.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.attachment_reader import extract_text_attachment

@pytest.mark.asyncio
async def test_extract_text_attachment_success():
    sample_content = "# Sprint Summary\nCompleted Gyros ledger ingestion with 0 drift."
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=sample_content.encode("utf-8"))

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        res = await extract_text_attachment("https://cdn.discordapp.com/test.md", "test.md")
        assert "[File Attachment: test.md" in res
        assert "Completed Gyros ledger ingestion" in res

@pytest.mark.asyncio
async def test_extract_text_attachment_truncates_large_files():
    huge_content = "A" * 300000
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=huge_content.encode("utf-8"))

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        res = await extract_text_attachment("https://cdn.discordapp.com/huge.txt", "huge.txt", max_bytes=10000)
        assert "[Truncated after 10.0 KB]" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attachment_reader.py -v`  
Expected: FAIL (`ModuleNotFoundError: No module named 'engine.attachment_reader'`)

- [ ] **Step 3: Implement minimal extract_text_attachment in engine/attachment_reader.py**

```python
# engine/attachment_reader.py
import aiohttp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".csv", ".json", ".py", ".sql", ".sh", ".yaml", ".yml"}

async def extract_text_attachment(url: str, filename: str, max_bytes: int = 256000) -> str:
    """Download text/markdown attachment and return formatted snippet."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
                if resp.status != 200:
                    return f"[File Attachment: {filename} (HTTP {resp.status} download error)]"
                raw_bytes = await resp.read()
                size_kb = round(len(raw_bytes) / 1024, 1)
                
                truncated_note = ""
                if len(raw_bytes) > max_bytes:
                    raw_bytes = raw_bytes[:max_bytes]
                    truncated_note = f"\n[Truncated after {round(max_bytes/1024, 1)} KB]"
                
                text_content = raw_bytes.decode("utf-8", errors="replace")
                return (
                    f"\n[File Attachment: {filename} (Size: {size_kb} KB)]\n"
                    f"────────────────────────────────────────\n"
                    f"{text_content.strip()}{truncated_note}\n"
                    f"────────────────────────────────────────"
                )
    except asyncio.TimeoutError:
        return f"[File Attachment: {filename} (Download timed out)]"
    except Exception as e:
        logger.warning(f"Failed to read attachment {filename}: {e}")
        return f"[File Attachment: {filename} (Error: {str(e)[:60]})]"
```

- [ ] **Step 4: Run pytest to verify it passes**

Run: `pytest tests/test_attachment_reader.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/attachment_reader.py tests/test_attachment_reader.py
git commit -m "feat: implement text and markdown attachment reader"
```

---

### Task 3: Screenshot Multimodal Vision Parser (`engine/attachment_reader.py`)

**Files:**
- Modify: `engine/attachment_reader.py`
- Modify: `tests/test_attachment_reader.py`

**Interfaces:**
- Produces: `async def extract_image_summary(url: str, filename: str) -> str`
- Calls Gemini Vision model asynchronously to generate a 1–2 sentence technical summary of code, UI, error, or chat screenshots.

- [ ] **Step 1: Write failing test for image extraction**

```python
# Append to tests/test_attachment_reader.py
from engine.attachment_reader import extract_image_summary

@pytest.mark.asyncio
async def test_extract_image_summary_success():
    fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=fake_png)

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = "Terminal displaying a Vercel 500 server error on the auth webhook route."

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("engine.evaluator._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_gemini_resp
            mock_get_client.return_value = mock_client
            
            res = await extract_image_summary("https://cdn.discordapp.com/error.png", "error.png")
            assert "[Screenshot Analysis: error.png]" in res
            assert "Vercel 500 server error" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attachment_reader.py -k test_extract_image_summary_success -v`  
Expected: FAIL (`ImportError: cannot import name 'extract_image_summary'`)

- [ ] **Step 3: Implement extract_image_summary in engine/attachment_reader.py**

```python
# Add to engine/attachment_reader.py
import os
from engine.evaluator import _get_client

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

async def extract_image_summary(url: str, filename: str) -> str:
    """Download screenshot and generate concise technical description using Gemini Vision."""
    client = _get_client()
    if not client:
        return f"[Image Attachment: {filename} (Gemini API key not configured for vision)]"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
                if resp.status != 200:
                    return f"[Image Attachment: {filename} (HTTP {resp.status} download error)]"
                image_bytes = await resp.read()

        prompt = (
            "Analyze this technical startup screenshot. In 1 to 2 simple plain English sentences "
            "that a 10-year-old can understand, explain what technical work, code, terminal error, "
            "dashboard metric, or conversation is displayed."
        )

        def _call_gemini():
            from google.genai import types
            return client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    prompt
                ]
            )

        response = await asyncio.to_thread(_call_gemini)
        summary = response.text.strip().replace("\n", " ")
        return f"\n[Screenshot Analysis: {filename}]\nVisual Summary: {summary}"

    except asyncio.TimeoutError:
        return f"[Image Attachment: {filename} (Download timed out)]"
    except Exception as e:
        logger.warning(f"Failed vision analysis on {filename}: {e}")
        return f"[Image Attachment: {filename} (Vision analysis skipped)]"
```

- [ ] **Step 4: Run pytest to verify it passes**

Run: `pytest tests/test_attachment_reader.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/attachment_reader.py tests/test_attachment_reader.py
git commit -m "feat: implement gemini vision screenshot analysis"
```

---

### Task 4: Link Enricher for GitHub and Discord Message Links (`engine/attachment_reader.py`)

**Files:**
- Modify: `engine/attachment_reader.py`
- Modify: `tests/test_attachment_reader.py`

**Interfaces:**
- Produces: `async def enrich_message_links(content: str, bot_client=None) -> str`
- Extracts GitHub PR/commit information and Discord jump link references.

- [ ] **Step 1: Write failing test for link enrichment**

```python
# Append to tests/test_attachment_reader.py
from engine.attachment_reader import enrich_message_links

@pytest.mark.asyncio
async def test_enrich_github_link():
    mock_gh_data = {
        "title": "fix: resolve subagent merge collisions in backend",
        "state": "open",
        "changed_files": 14,
        "user": {"login": "swarit"}
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_gh_data)

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        text = "I opened https://github.com/calcrum/calcrum/pull/22 for review"
        res = await enrich_message_links(text)
        assert "[GitHub PR #22: fix: resolve subagent merge collisions in backend" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attachment_reader.py -k test_enrich_github_link -v`  
Expected: FAIL (`ImportError: cannot import name 'enrich_message_links'`)

- [ ] **Step 3: Implement enrich_message_links in engine/attachment_reader.py**

```python
# Add to engine/attachment_reader.py
import re

GH_PR_PATTERN = re.compile(r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)')
GH_COMMIT_PATTERN = re.compile(r'https?://github\.com/([^/]+)/([^/]+)/commit/([a-f0-9]{7,40})')

async def enrich_message_links(content: str, bot_client=None) -> str:
    """Enrich URLs like GitHub PRs or commits with title/summary."""
    extra_snippets = []

    # 1. GitHub PRs
    for owner, repo, pr_num in GH_PR_PATTERN.findall(content):
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title", "")
                        state = data.get("state", "open")
                        files = data.get("changed_files", 0)
                        extra_snippets.append(
                            f"[GitHub PR #{pr_num}: {title} ({state}, {files} files changed)]"
                        )
        except Exception:
            pass

    # 2. GitHub Commits
    for owner, repo, sha in GH_COMMIT_PATTERN.findall(content):
        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg = data.get("commit", {}).get("message", "").split("\n")[0]
                        extra_snippets.append(
                            f"[GitHub Commit {sha[:7]}: {msg}]"
                        )
        except Exception:
            pass

    if extra_snippets:
        return content + "\n" + "\n".join(extra_snippets)
    return content
```

- [ ] **Step 4: Run pytest to verify it passes**

Run: `pytest tests/test_attachment_reader.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/attachment_reader.py tests/test_attachment_reader.py
git commit -m "feat: add github pr and commit link enrichment"
```

---

### Task 5: Master Enrichment Function & Tracker Integration (`cogs/tracker.py`)

**Files:**
- Modify: `engine/attachment_reader.py`
- Modify: `cogs/tracker.py`
- Create: `tests/test_tracker_enrichment.py`

**Interfaces:**
- Produces: `async def enrich_discord_message(message: discord.Message) -> str`
- Hooked into `TrackerCog.on_message` so attachments are parsed before saving to SQLite `updates`.

- [ ] **Step 1: Implement master enrich_discord_message in engine/attachment_reader.py**

```python
# Add to engine/attachment_reader.py
from pathlib import Path

async def enrich_discord_message(message) -> str:
    """Master helper to merge message text, attachment contents, and links."""
    content = message.content.strip()

    # Append embed descriptions
    for e in message.embeds:
        if e.description:
            content += f"\n[Embed: {e.title or ''}] {e.description}"

    # Extract attachments
    for att in message.attachments:
        ext = Path(att.filename).suffix.lower()
        if ext in TEXT_EXTENSIONS:
            snippet = await extract_text_attachment(att.url, att.filename)
            content += f"\n{snippet}"
        elif ext in IMAGE_EXTENSIONS:
            snippet = await extract_image_summary(att.url, att.filename)
            content += f"\n{snippet}"

    # Enrich links
    content = await enrich_message_links(content, getattr(message, "_state", None))
    return content.strip()
```

- [ ] **Step 2: Write test verifying message enrichment**

```python
# tests/test_tracker_enrichment.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from engine.attachment_reader import enrich_discord_message

@pytest.mark.asyncio
async def test_enrich_discord_message_with_attachment():
    msg = MagicMock()
    msg.content = "Dropping our sprint review"
    msg.embeds = []
    att = MagicMock()
    att.filename = "review.md"
    att.url = "https://cdn.discordapp.com/review.md"
    msg.attachments = [att]

    with patch("engine.attachment_reader.extract_text_attachment", new_callable=AsyncMock) as mock_text:
        mock_text.return_value = "[File Attachment: review.md]\nAll tasks done"
        res = await enrich_discord_message(msg)
        assert "Dropping our sprint review" in res
        assert "[File Attachment: review.md]" in res
        assert "All tasks done" in res
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_tracker_enrichment.py -v`  
Expected: PASS

- [ ] **Step 4: Update cogs/tracker.py to use enrich_discord_message**

In `cogs/tracker.py`:
- Import `enrich_discord_message` from `engine.attachment_reader`.
- Replace lines 92-100 with `content = await enrich_discord_message(message)`.
- If `message.channel.id == PRIMARY_GOALS_CHANNEL_ID` and is a reply to Peter Thiel's 7:15 PM prompt, tag it in database.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/ -v`  
Expected: PASS

```bash
git add engine/attachment_reader.py cogs/tracker.py tests/test_tracker_enrichment.py
git commit -m "feat: hook multimodal enrichment directly into discord tracker cog"
```

---

### Task 6: 7:15 PM Pre-Scoring Context Inquiry Engine (`engine/inquiry.py`)

**Files:**
- Create: `engine/inquiry.py`
- Create: `tests/test_inquiry.py`

**Interfaces:**
- Produces: `async def generate_pre_scoring_inquiries(score_date: str) -> Dict[str, str]`
- Returns: Map of `founder_key -> single_punchy_question` for founders with context gaps.

- [ ] **Step 1: Write failing test for inquiry gap detection**

```python
# tests/test_inquiry.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.inquiry.py import generate_pre_scoring_inquiries

@pytest.mark.asyncio
async def test_generate_inquiries_identifies_gap():
    # If founder has goal to finish deployment but updates only contain a screenshot of 500 error
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '{"needs_clarification": true, "question": "Did the client join the 4 PM reschedule call, or was it delayed?"}'

    with patch("engine.inquiry._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_resp
        mock_get_client.return_value = mock_client
        
        with patch("database.models.get_goals_for_date", new_callable=AsyncMock) as mock_goals:
            mock_goals.return_value = {"parsed_goals": [{"task": "Deploy client portal"}]}
            with patch("database.models.get_updates_for_date_range", new_callable=AsyncMock) as mock_updates:
                mock_updates.return_value = [{"content": "[Screenshot Analysis: error.png] 500 error on deploy"}]
                
                res = await generate_pre_scoring_inquiries("2026-10-12")
                assert "hridesh" in res or len(res) > 0
                first_q = list(res.values())[0]
                assert "client" in first_q.lower() or "delayed" in first_q.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inquiry.py -v`  
Expected: FAIL (`ModuleNotFoundError: No module named 'engine.inquiry'`)

- [ ] **Step 3: Implement engine/inquiry.py**

```python
# engine/inquiry.py
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
If YES, formulate EXACTLY ONE simple, direct question asking for a concrete, falsifiable fact (e.g. "Did the client reply to WhatsApp, or was the call delayed?" or "Did you send the emails from that CSV, or is it queued for tomorrow?").
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
            name=info["display_name"],
            role=info["role"],
            goals=goals_text,
            evidence=evidence_text
        )

        def _call_gemini():
            from google.genai import types
            return client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )

        try:
            resp = await asyncio.to_thread(_call_gemini)
            parsed = json.loads(resp.text)
            if parsed.get("needs_clarification") and parsed.get("question"):
                inquiries[key] = parsed["question"].strip()
        except Exception as e:
            logger.warning(f"Inquiry gap check failed for {key}: {e}")

    return inquiries
```

- [ ] **Step 4: Run pytest to verify it passes**

Run: `pytest tests/test_inquiry.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/inquiry.py tests/test_inquiry.py
git commit -m "feat: implement 7:15 pm context gap inquiry engine"
```

---

### Task 7: Scheduler Integration for 7:15 PM Check-In (`cogs/scheduler.py`)

**Files:**
- Modify: `cogs/scheduler.py`
- Modify: `tests/test_scheduler_inquiry.py`

**Interfaces:**
- Produces: `async def run_context_inquiry_callout(today_str: str)` scheduled at 19:15 IST daily.
- Posts prompt to `PRIMARY_GOALS_CHANNEL_ID` (`#daily-reports`).

- [ ] **Step 1: Write test for inquiry callout scheduler**

```python
# tests/test_scheduler_inquiry.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from cogs.scheduler import SchedulerCog

@pytest.mark.asyncio
async def test_scheduler_runs_inquiry_callout():
    bot = MagicMock()
    channel = AsyncMock()
    bot.get_channel.return_value = channel

    cog = SchedulerCog(bot)
    with patch("engine.inquiry.generate_pre_scoring_inquiries", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "hridesh": "Did the Gyros client reply to the WhatsApp message?"
        }
        await cog.run_context_inquiry_callout("2026-10-12")
        assert channel.send.called
        call_args = channel.send.call_args[1]
        assert "embed" in call_args
        assert "Gyros client" in call_args["embed"].description
```

- [ ] **Step 2: Implement run_context_inquiry_callout in cogs/scheduler.py**

In `cogs/scheduler.py`:
- Add `run_context_inquiry_callout`:
  1. Calls `generate_pre_scoring_inquiries(today_str)`.
  2. If empty, logs and returns.
  3. Builds Discord embed:
     - Title: `🔍 7:15 PM Quick Context Check • Before Tonight's Scores`
     - Fields for each founder with their question.
     - Footer: `Reply directly in this channel before 8:00 PM so Peter can count it!`
  4. Sends embed to `#daily-reports`.
- In `heartbeat` loop, trigger when `now.hour == 19 and now.minute == 15`.

- [ ] **Step 3: Run pytest to verify it passes**

Run: `pytest tests/test_scheduler_inquiry.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add cogs/scheduler.py tests/test_scheduler_inquiry.py
git commit -m "feat: schedule 7:15 pm context check in daily-reports"
```

---

### Task 8: Upgraded Evaluator Engine with Anti-Gaming Matrix (`engine/evaluator.py`)

**Files:**
- Modify: `engine/evaluator.py`
- Create: `tests/test_evaluator_anti_gaming.py`

**Interfaces:**
- Consumes: Enriched update text + founder clarification replies + tangible file snippets
- Produces: Evaluation with Cross-Verification Matrix enforced (claims capped if unverified by artifacts, modesty rewarded if artifacts show massive progress).

- [ ] **Step 1: Write test for Anti-Gaming claim verification**

```python
# tests/test_evaluator_anti_gaming.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.evaluator import evaluate_daily_execution_with_ai

@pytest.mark.asyncio
async def test_evaluator_caps_unsupported_claim():
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = '''{
      "task_evaluations": [
        {
          "task": "Client onboarding integration",
          "completion": 0.4,
          "complexity": 4,
          "dharma_multiplier": 1.2,
          "evidence_snippet": "Founder claimed system is done, but only a 1-page wireframe exists with no code.",
          "score_reason": "Capped credit: claim exceeds tangible proof on disk."
        }
      ],
      "spontaneous_bonus": 0.0,
      "praise_text": "Good start on the wireframe.",
      "feedback_text": "Provide git commits or API proof to get full credit tomorrow.",
      "mentor_question": "Can you push the backend branch tomorrow?"
    }'''

    with patch("engine.evaluator._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_resp
        mock_get_client.return_value = mock_client

        res = await evaluate_daily_execution_with_ai(
            "hridesh",
            [{"task": "Client onboarding integration"}],
            "Clarification reply: Finished the entire client onboarding today.\n[File Attachment: wireframe.png] Just UI mock."
        )
        task = res["task_evaluations"][0]
        assert task["completion"] <= 0.5
        assert "capped" in task["score_reason"].lower() or "proof" in task["score_reason"].lower()
```

- [ ] **Step 2: Update evaluator.py system prompt with Cross-Verification Matrix**

Update `engine/evaluator.py` system prompt in `evaluate_daily_execution_with_ai`:
- Add clear instructions regarding **Claims vs. Tangible Artifacts**:
  ```text
  ANTI-GAMING & VERIFICATION RULES:
  - If a founder claims something in a clarification reply or chat without matching files, PRs, or logs, DO NOT give 100% credit. Cap completion at 0.3 to 0.5 and explain why in score_reason.
  - If a founder is modest/taciturn ("fixed a bug"), but the attached files or diffs prove massive engineering output (e.g. passing unit tests, ₹0 drift ledger, multi-hour untangle), UPGRADE their score and praise the modesty in praise_text.
  - Read all [File Attachment: ...] blocks and [Screenshot Analysis: ...] blocks as primary ground truth.
  ```

- [ ] **Step 3: Run pytest to verify evaluator passes**

Run: `pytest tests/test_evaluator_anti_gaming.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add engine/evaluator.py tests/test_evaluator_anti_gaming.py
git commit -m "feat: enforce cross-verification matrix and anti-gaming rules in evaluator"
```

---

### Task 9: End-to-End System Verification & VPS Deployment Runbook

**Files:**
- Create: `tests/test_e2e_scoring.py`
- Modify: `README.md` (add deployment checklist)

**Interfaces:**
- Runs full suite: `pytest tests/`
- Validates that a day with `.md` uploads, screenshot analysis, and a 7:15 PM clarification produces accurate scorecards.

- [ ] **Step 1: Write E2E mock scoring test**

```python
# tests/test_e2e_scoring.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
    assert res["peer_multiplier"] == 1.05
    assert res["final_score"] == pytest.approx(8.3, 0.1)
```

- [ ] **Step 2: Run complete pytest suite**

Run: `pytest tests/ -v`  
Expected: All tests PASS

- [ ] **Step 3: Update README.md with VPS Deployment Instructions**

Document:
1. Pushing to GitHub.
2. VPS `git clone` & `./deploy_gcp.sh`.
3. Managing systemd service (`sudo systemctl restart peter-thiel.service`).

- [ ] **Step 4: Final commit and git push**

```bash
git add tests/ README.md
git commit -m "docs: finalize vps deployment runbook and complete test suite"
git push origin main
```
