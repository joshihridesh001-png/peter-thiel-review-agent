# 🕶️ Autonomous Agent Guidelines • Peter Thiel Review Bot

Welcome, autonomous agent (Google Jules / Antigravity). This document contains critical context, conventions, and invariants for working on this repository.

## 🧭 Project Overview
- **Core Purpose**: 24/7 Discord Operations & Review Bot for founders operating under Hridesh's Systems Thinking Framework and the Krishna Engineering OS.
- **Tech Stack**: Python 3.12+, `discord.py` (Cogs architecture), `google-genai` (Gemini API), `aiosqlite`, `aiohttp`, `pytest`.

## 📁 Repository Structure
- `cogs/`: Discord bot cogs (`tracker.py` for ambient message logging, `scheduler.py` for 24/7 cron loops, `commands.py` for slash commands).
- `engine/`:
  - `attachment_reader.py`: Multi-modal parser for `.md`, `.txt`, `.csv` attachments, Gemini Vision screenshot summaries, and GitHub PR/commit links.
  - `inquiry.py`: 7:15 PM pre-scoring context gap inquiry engine.
  - `evaluator.py`: Gemini AI execution evaluator with Anti-Gaming Cross-Verification Matrix.
  - `scoring.py`: Mathematical formulation of daily score ($S_{\text{daily}}$) with anti-task-stuffing dampening.
  - `equity.py`: 24-month dynamic earnout ledger (Slicing Pie) with 60% safety floor.
  - `swot.py`: Weekly executive SWOT analysis.
- `database/`: Async SQLite persistence (`db.py`, `models.py`).
- `tests/`: Comprehensive pytest test suite (`pytest tests/ -v`).

## 🛡️ Critical Invariants & Rules
1. **Language Invariant (10-Year-Old Plain English)**:
   All AI-generated text presented to founders (praise, feedback, inquiries, mentor questions) MUST use simple, everyday English that a 10-year-old can easily understand. Never use corporate buzzwords ("synergy", "paradigm", "zero-to-one", "existential moats").
2. **Anti-Gaming Rule**:
   Founder chat replies and claims must NOT be accepted as ground truth without artifact cross-verification. Unbacked claims are capped at 0.3–0.5 completion. Modest claims backed by tangible artifacts (PRs, code diffs, logs) are upgraded to 1.0.
3. **Async / Non-Blocking**:
   Never make synchronous, blocking network or API calls on Discord's event loop. Wrap heavy synchronous tasks in `await asyncio.to_thread(...)`.
4. **Testing Mandatory**:
   Any new feature or bugfix MUST include unit tests in `tests/`. All tests must pass: `python -m pytest tests/ -v`.
