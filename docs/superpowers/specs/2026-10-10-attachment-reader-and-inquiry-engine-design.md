# Design Spec: Peter Thiel Multimodal Attachment Reader & Pre-Scoring Inquiry Engine

**Date:** 2026-10-10  
**Status:** Approved  
**Author:** Krishna Engineering OS Team  
**Scope:** Architectural Upgrade to Peter Thiel Founder Operations Bot  

---

## 1. Problem Statement & Motivation

During active sprints, founders frequently upload rich artifacts directly to Discord rather than typing lengthy text updates:
- **Markdown (`.md`) & Text (`.txt`, `.csv`) Files**: Complete sprint summaries (e.g. `DEPLOY_TRIAL.md`, `Cycle_1_Review_LinkedIn_DMs.md`, `01-email-outreach-summary.md`) and verified lead lists (`october_8_d2c_founders_verified.csv`).
- **Screenshots & Images (`.png`, `.jpg`)**: Over 100 screenshots depicting Vercel build logs, UI iterations, terminal errors, and WhatsApp client communications.
- **Cross-References**: GitHub PRs/commits, Discord message jump links, and Google Drive/Sheets links.

### Current Limitations
1. **Blind Ingestion**: `cogs/tracker.py` currently only stores `message.content` and basic embed descriptions. Attachments are completely ignored. When a founder uploads a file with no caption, the update is logged with blank text and receives zero credit.
2. **Passive Scoring with Missing Context**: The review bot acts as a passive observer until 8:00 PM IST. If an update is ambiguous or lacks verifiable proof, Peter Thiel makes conservative assumptions (capping scores at 50% or awarding 0 pts) without giving the founder a chance to clarify.

---

## 2. Proposed Architecture & System Components

The upgrade introduces two major subsystems:
1. **Multimodal Attachment & Link Reader (`engine/attachment_reader.py`)**
2. **Pre-Scoring Context Inquiry Engine (`engine/inquiry.py` + `cogs/scheduler.py`)**

```
                     ┌────────────────────────────────────────┐
                     │          Incoming Discord Post         │
                     └───────────────────┬────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
          [Plain Text Message]                        [Attachments & Links]
                   │                                           │
                   │                               ┌───────────┴───────────┐
                   │                               ▼                       ▼
                   │                     [.md / .txt / .csv]         [.png / .jpg]
                   │                               │                       │
                   │                        [Raw Text Read]        [Gemini Vision]
                   │                               │                       │
                   │                               └───────────┬───────────┘
                   │                                           │
                   ▼                                           ▼
             ┌───────────────────────────────────────────────────────┐
             │  Enriched Update Payload Saved to SQLite (updates)   │
             └───────────────────────────┬───────────────────────────┘
                                         │
                              [Daytime Sprint: 05:00 - 19:15]
                                         │
                                         ▼
             ┌───────────────────────────────────────────────────────┐
             │         7:15 PM IST: Pre-Scoring Gap Audit            │
             │   Detects ambiguous goals, bare files, missing proof  │
             └───────────────────────────┬───────────────────────────┘
                                         │
                                         ▼
             ┌───────────────────────────────────────────────────────┐
             │       Targeted Question Ping in #daily-reports        │
             │   "Hey @Hridesh, did PORT_LIST unblock deployment?"   │
             └───────────────────────────┬───────────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
       [Founder Replies by 7:55 PM]                [No Reply by 8:00 PM]
                   │                                           │
         Tagged as Clarification                     Score on Extracted
         Added to Evidence Pool                      Files with Note
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         │
                                         ▼
             ┌───────────────────────────────────────────────────────┐
             │        8:00 PM IST: Final Accurate Daily Scorecard    │
             └───────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Specifications

### 3.1 Multimodal Attachment Reader (`engine/attachment_reader.py`)

A standalone asynchronous utility responsible for downloading and extracting content from message attachments and URLs.

#### Supported Types & Behaviors
1. **Text & Markdown (`.md`, `.markdown`, `.txt`, `.csv`, `.json`, `.py`)**:
   - Downloads file stream via `aiohttp` from Discord CDN URL.
   - Caps payload extraction at **250 KB** (truncates cleanly if exceeded).
   - Formats content as:
     ```text
     [File Attachment: filename.md (Size: 4.2 KB)]
     ----------------------------------------
     <Extracted Text Content>
     ----------------------------------------
     ```
2. **Images (`.png`, `.jpg`, `.jpeg`, `.webp`)**:
   - Fetches image bytes.
   - Passes image to Google Gemini Vision (`gemini-2.5-flash` or `gemini-3.5-flash-lite`).
   - Prompt: *"Analyze this technical startup screenshot. In 1 to 2 simple plain English sentences, explain what code, build error, dashboard metric, terminal log, or conversation is displayed."*
   - Formats content as:
     ```text
     [Screenshot Analysis: filename.png]
     Visual Summary: Terminal displays a Vercel 500 server error on the auth webhook route with a timeout on Supabase connection.
     ```
3. **GitHub Links (`github.com/org/repo/pull/X` or `/commit/X`)**:
   - Detects GitHub URLs using regex.
   - Fetches PR/commit metadata (title, status, changed files) via GitHub public API or unauthenticated preview headers.
4. **Discord Jump Links (`discord.com/channels/...`)**:
   - Parses guild, channel, and message ID.
   - If in the same guild, fetches the referenced message content and appends it to resolve context.

#### Error Handling & Performance Invariants
- **Non-blocking Execution**: Network extraction is wrapped in timeouts (`asyncio.wait_for(..., timeout=10.0)`).
- **Graceful Fallback**: If an image or file fails to download or parse, the system logs a fallback identifier: `[Attachment: filename.ext (Failed to extract: error details)]` without dropping the message.

---

### 3.2 Tracker Integration (`cogs/tracker.py`)

1. **On Message Receive (`on_message`)**:
   - Calls `attachment_reader.enrich_message_payload(message)` concurrently.
   - Merges message text with parsed attachment text and visual summaries.
   - Saves enriched content to SQLite `updates` table.
2. **Capture Clarification Answers**:
   - If a message in `#daily-reports` is a reply to Peter Thiel's 7:15 PM inquiry (or mentions the bot and occurs between 7:15 PM and 8:00 PM IST), it is flagged with `is_clarification = 1` in the database.

---

### 3.3 Pre-Scoring Context Inquiry Engine (`engine/inquiry.py`)

Runs automatically at **7:15 PM IST** every day via `cogs/scheduler.py`.

#### Step 1: Gap Detection Algorithm
For each founder:
1. Fetch today's locked commitments from `daily_goals`.
2. Fetch all enriched updates logged between 05:00 and 19:15 IST today.
3. Pass to Gemini with a lightweight audit prompt:
   - *"Compare these goals against the evidence collected so far. Is there any task that has high importance but zero or ambiguous proof? Or did the founder drop a file/screenshot without explaining what happened?"*
4. Output: Returns either `needs_clarification: false` or `question: "..."` (maximum 1 question per founder, strictly formatted in casual, friendly, 10-year-old approachable language).

#### Step 2: Interactive Prompt Dispatch
- If questions are generated, Peter Thiel posts a clean check-in message in `#daily-reports`:
  ```markdown
  🔍 **7:15 PM Quick Context Check • Before Tonight's Scores**

  Hey team! Taking a quick look at today's work before the 8:00 PM scorecard drops. Got a couple of quick questions to make sure you get full credit:

  • **@Hridesh**: Saw you uploaded `PORT_LIST_FOR_COIL.md`—did this unblock the staging deployment or is it still in review?
  • **@Rahul**: You shared the verified D2C list with 30 brands—were any cold emails sent today, or is this ready for tomorrow's blast?

  Drop a quick reply in this channel before 8:00 PM so I can count it! 🚀
  ```

---

### 3.4 Upgraded Evaluator Engine (`engine/evaluator.py`)

At 8:00 PM IST:
1. Gathers all daytime text updates + parsed `.md` contents + screenshot summaries + clarification replies.
2. Evaluates task execution with full awareness of uploaded documents and founder answers.
3. If a founder answered Peter's 7:15 PM inquiry, Peter explicitly references it in `What Went Great` or `Score Details`.
4. If a founder did not answer, Peter scores based on extracted attachments and adds a brief encouraging note in `Advice from Peter`.

---

### 3.5 The Anti-Gaming & Verification Principle (Handling Overplaying vs. Underplaying)

Founder replies to 7:15 PM check-ins are **context claims**, never unverified gospel. People naturally overplay or underplay their contributions:
- **Overplaying (Exaggeration)**: *"Finished the whole onboarding system"* when they only drew a wireframe.
- **Underplaying (Humility/Brevity)**: *"Just fixed a deploy bug"* when they actually rescued a broken database and untangled 3 hours of merge conflicts.

To prevent gaming or unfair penalties, the Evaluator enforces a strict **Cross-Verification Matrix**:

| Scenario | Founder Reply | Tangible Evidence on Disk/Chat | Peter Thiel's Scoring Rule |
| :--- | :--- | :--- | :--- |
| **Claim Matches Evidence** | *"Sent emails to the top 15 brands on the CSV"* | Screenshot of sent mail or CSV with status column | **Full Credit (100%)**: Claim verified by tangible artifact. |
| **Overplaying (No Proof)** | *"Finished all client integrations today"* | No PR, no commit, only a 1-page note | **Capped Credit (30–50%)**: Peter gently calls it out: *"You mentioned the integrations are done, but without code or API logs, I'm scoring this as a spec doc."* |
| **Underplaying (Taciturn)** | *"Fixed a few bugs"* | Extracted `.md` shows 672 unit tests passing and ₹0 drift ledger | **Upgraded Score (100% + Bonus)**: Peter calls out the modesty: *"You said you just fixed bugs, but your actual commit files show you resolved ₹16.66L with zero drift! Upgrading your points."* |

#### Inquiry Question Design Rule
Peter Thiel's 7:15 PM questions must **never be vague** (e.g. *"What did you do today?"*). They must ask for **falsifiable, binary, or metric-based facts**:
- ❌ Bad: *"How did the Gyros Farm work go?"*
- ✅ Good: *"Did Yogesh reply to your WhatsApp reschedule message, or is the call still pending?"*
- ❌ Bad: *"Tell me about the sales list."*
- ✅ Good: *"Did you already fire off outreach to that 30-brand CSV, or is it queued for tomorrow morning?"*

---

## 4. Database Schema Adjustments

No destructive migrations needed. SQLite `updates` table will support:
- `raw_content`: Original text content
- `enriched_content`: Full text with attachment dumps and vision summaries
- `is_clarification`: Integer boolean flag (1 if posted in response to 7:15 PM check)

---

## 5. Verification & Test Plan

1. **Attachment Extraction Tests**:
   - Upload sample `.md` file to `#dev-general` $\rightarrow$ verify SQLite stores full markdown text.
   - Upload sample screenshot `.png` $\rightarrow$ verify Gemini Vision returns accurate 1-2 sentence description.
   - Upload raw `.csv` file $\rightarrow$ verify row count and column headers are parsed.
2. **Inquiry Engine Dry Run**:
   - Trigger inquiry audit manually via slash command `/test_inquiry` or mock script $\rightarrow$ verify Peter Thiel drafts 1 plain-English question per founder with gaps.
   - Post reply $\rightarrow$ verify reply is captured and incorporated into the 8:00 PM scorecard.
3. **End-to-End Scoring Run**:
   - Compare scoring accuracy before vs. after attachment extraction $\rightarrow$ verify founder score reflects actual document deliverables without penalty.
