# 🕶️ Master Project Context & VPS Handoff Document
**Project:** Peter Thiel Review & Operations Agent (Calcrum Mainframe)  
**Framework:** Hridesh's Systems Thinking Framework & Krishna Engineering OS  
**Last Updated:** October 2026  
**Intended Audience:** Future AI Agents (Google Jules, Claude, GPT, Antigravity) & Core Engineering Team  

---

## 🧭 1. Executive Summary & Core Philosophy

The **Peter Thiel Review Agent** is an autonomous 24/7 Discord operations daemon built to keep high-velocity startup founders ruthlessly aligned, accountable, and transparent. It operates on Calcrum's internal company Discord.

### Core Tenets of the Krishna Engineering OS:
1. **Zero Reporting Overhead**: Founders do not fill out tedious status forms. They communicate ambiently in Discord text channels (`#dev-updates`, `#sales-updates`, `#dev-general`, threads). Peter Thiel passively ingests, parses attachments, and tracks work.
2. **Asymmetric Work Normalization**: Standardizes fundamentally different founder work into a unified power-law complexity rubric ($W_i \in [1, 5]$):
   - **Hridesh (CEO)**: Deal closing, investor steering, strategic distribution ($A_{\text{dharma}} = 1.2$ for high-leverage CEO moves).
   - **Swarit (CTO)**: Architecture, shipping code, fixing production bugs ($A_{\text{dharma}} = 1.2$ for backend/infra delivery).
   - **Rahul (COO)**: Customer pilots, operations, compliance ($A_{\text{dharma}} = 1.2$ for customer traction).
3. **Anti-Gaming Verification**: Unbacked verbal claims ("did great work today") are capped at **0.3–0.5** completion. Modest claims backed by tangible artifacts (GitHub PR diffs, commit hashes, CSVs, log screenshots) are rewarded with full **1.0**.
4. **24-Month Dynamic Earnout (Slicing Pie)**: Releases $\Delta E \approx 2.2917\%$ equity monthly from an unvested pool, protected by a **60% safety floor** that diverts unearned equity into the **Company Treasury** rather than causing toxic founder cannibalization.
5. **Language Rule (10-Year-Old Plain English)**: All AI-generated text presented to founders (praise, feedback, inquiries, mentor questions) **MUST** use simple, everyday English that a 10-year-old can easily understand. Never use corporate buzzwords (*"synergy"*, *"paradigm"*, *"zero-to-one"*, *"existential moats"*).

---

## 🧮 2. Mathematical Formulations & Scheduled Cadence

### A. Daily Individual Score Formula ($S_{\text{daily}}$)
$$S_{\text{daily}} = \left( \sum_{i=1}^n C_i \times W_i \times A_{\text{dharma}} \right) \times M_{\text{peer}} + I_{\text{bonus}}$$

* **Completion ($C_i \in [0.0, 1.0]$)**: Evaluated by Gemini from messages and verified artifacts.
* **Complexity Weight ($W_i \in [1, 5]$)**:
  - `1`: Quick chore / admin (<15m). *Anti-task-stuffing dampening: 4th+ trivial task discounted by 75% ($W_i \times 0.25$).*
  - `3`: Core feature milestone, partner pitch (2–3h).
  - `5`: Existential breakthrough, major deal close, critical infra launch (>6h).
* **Role Dharma ($A_{\text{dharma}} \in [0.8, 1.2]$)**:
  - `1.2`: Primary high-leverage duty for founder's role.
  - `1.0`: Standard cross-functional execution.
  - `0.8`: Distracting low-leverage busywork.
* **Peer Reaction Multiplier ($M_{\text{peer}} \in [0.8, 1.2]$)**:
  $$M_{\text{peer}} = \text{clamp}(1.0 + 0.05 \cdot N_{✅} + 0.10 \cdot N_{🔥} - 0.15 \cdot N_{⚠️}, 0.8, 1.2)$$
  *(Self-reactions are strictly filtered).*
* **Bonus Points ($I_{\text{bonus}} \in [0, 5]$)**: Urgent unscripted firefighting or emergency bug fixes.

---

### B. Monthly Dynamic Earnout Formulation
* **Baseline Cap Table**:
  - **Hridesh (CEO)**: $45.000\%$ (Protected, fully vested founder baseline).
  - **Swarit (CTO)**: $25.000\%$ unvested target (baseline weight $45.45\%$).
  - **Rahul (COO)**: $30.000\%$ unvested target (baseline weight $54.55\%$).
* **Monthly Tranche**: $\Delta E = \frac{55.0\%}{24} \approx 2.2916667\%$
* **Score Ratio**: $\text{Ratio}_{\text{CTO}} = \frac{S_{\text{CTO}}}{S_{\text{CTO}} + S_{\text{COO}}}, \quad \text{Ratio}_{\text{COO}} = \frac{S_{\text{COO}}}{S_{\text{CTO}} + S_{\text{COO}}}$
* **60% Safety Floor**: If a founder's output drops below $60\%$ of target baseline, the unearned difference flows into the **Company Treasury Reserve**.

---

### C. 24/7 Operational Schedule (IST)

| Time (IST) | Channel | Function | Implementation |
| :--- | :--- | :--- | :--- |
| **7:15 PM Daily** | `#daily-reports` | **Context Gap Inquiry**: Scans today's work for ambiguities or bare file drops. Asks at most 1 question per founder to clarify before scoring. If work is clear, stays silent. | `engine/inquiry.py` |
| **8:00 PM Daily** | `#daily-reports` / `#dev-updates` | **Daily Scoring Calculation**: Evaluates daytime updates, computes $S_{\text{daily}}$, generates **Win of the Day**, and posts scorecards. | `engine/evaluator.py`, `engine/scoring.py` |
| **9:00 PM Daily** | `#daily-reports` | **Nightly Commitment Prompt**: Pings founders to declare 2–4 goals for tomorrow before sleeping. Gemini parses text into JSON. | `cogs/scheduler.py` |
| **9:30 PM Daily** | `#daily-reports` | **Commitment Nudge**: Flags founders who haven't declared goals yet. | `cogs/scheduler.py` |
| **Sunday 9:00 PM** | `#leadership` | **Executive SWOT Report**: Depersonalized sprint summary across Strengths, Weaknesses, Opportunities, and Threats. | `engine/swot.py` |
| **1st of Month 10:00 AM** | `#leadership` | **Monthly Equity Evolution**: Computes monthly tranche and posts provisional allocation for founder confirmation (`/confirm-equity`). | `engine/equity.py` |

---

## 📁 3. Repository Architecture & Codebase Map

```
peter-thiel-review-agent/
├── cogs/
│   ├── commands.py          # Discord slash commands (/set-role, /goals, /score, /leaderboard, /equity, etc.)
│   ├── scheduler.py         # 24/7 background cron loop (7:15 PM, 8:00 PM, 9:00 PM, Sunday, 1st of month)
│   └── tracker.py           # Ambient message listener (parses attachments, extracts GitHub links, stores to SQLite)
├── database/
│   ├── db.py                # aiosqlite async database connection & table schema initializers
│   └── models.py            # Async CRUD queries for users, goals, channel updates, scores, reactions, equity
├── engine/
│   ├── attachment_reader.py # Multi-modal parser (.md, .txt, .csv up to 250KB), Gemini Vision screenshots, GitHub link enrichment
│   ├── inquiry.py           # 7:15 PM pre-scoring context gap inquiry engine
│   ├── evaluator.py         # Gemini AI execution evaluator with Anti-Gaming Cross-Verification Matrix
│   ├── scoring.py           # Mathematical formulation of S_daily with anti-task-stuffing dampening
│   ├── equity.py            # Slicing Pie dynamic earnout ledger with 60% safety floor
│   └── swot.py              # Weekly executive SWOT analysis generator
├── scripts/
│   ├── post_dev_progress.py # Utility to format and dispatch rich progress embeds to Discord channels
│   └── rice_server.sh       # Cyberpunk terminal ricing suite (Starship, login MOTD, shutdown/reboot screens)
├── tests/
│   ├── test_attachment_reader.py # Tests for file downloads, size caps, and GitHub link parsing
│   ├── test_e2e_scoring.py       # End-to-end mathematical tests for daily scoring
│   ├── test_equity.py            # Dynamic earnout, safety floor, and treasury diversion tests
│   ├── test_evaluator_ai.py      # Mocked AI evaluation tests, boundary clamping, and error fallbacks
│   ├── test_inquiry.py           # Tests for 7:15 PM context gap detection
│   ├── test_scoring.py           # Unit tests for complexity discounts and peer multipliers
│   └── test_swot.py              # Tests for weekly SWOT generation and fallbacks
├── .github/workflows/
│   └── jules.yml            # CI test suite and Google Jules autonomous PR workflow
├── AGENTS.md                # Critical rules and invariants for AI agents (Jules, Claude, Antigravity)
├── config.py                # Environment configurations, channel IDs, founder weights, model names
├── main.py                  # Bot entry point, intent setup, cog loader, and slash tree sync
├── pytest.ini               # Pytest configuration filtering upstream deprecation noise
└── requirements.txt         # Production dependencies
```

---

## 🖥️ 4. VPS Production Infrastructure & Deployment

The bot runs 24/7 on an **Ubuntu VPS** hosted with OVHcloud (`calcrum-main-vps`).

### A. Server Specifications & Access Details
* **Host Identifier:** `calcrum-main-vps` (Ubuntu 22.04/24.04 LTS)
* **Hardware:** 1 vCPU, 4 GB RAM, 40 GB NVMe SSD
* **IPv4 Address:** `51.68.205.225` (SSH Port: **`20022`**)
* **IPv6 Address:** `2001:41d0:800:16e1::3a4` (SSH Port: `22`)

### ⚡ Recommended SSH Connection Command:
Always prefer the IPv4 command with port `20022` (works across all home broadband/ISPs without IPv6 drops):
```bash
ssh root@51.68.205.225 -p 20022
```

---

### B. Daemon Architecture (`systemd`)
The bot is managed by Linux `systemd`, meaning it starts on system boot and restarts automatically if it crashes.

* **Repository Location:** `/root/peter-thiel-review-agent`
* **Python Virtual Environment:** `/root/peter-thiel-review-agent/venv`
* **Service File:** `/etc/systemd/system/peter-thiel.service`
* **Environment File:** `/root/peter-thiel-review-agent/.env`

#### Key Operational Commands:
```bash
# Check bot status & uptime
sudo systemctl status peter-thiel.service

# View real-time live logs
sudo journalctl -u peter-thiel.service -f -n 50

# Restart bot after updating code or .env
sudo systemctl restart peter-thiel.service

# Stop bot
sudo systemctl stop peter-thiel.service
```

---

### C. Installed Server Ricing & Cyberpunk Aesthetics
The VPS terminal has been configured with an elite developer experience via `scripts/rice_server.sh`:
1. **Starship Prompt:** Minimal two-line Tokyo Night theme displaying current directory, Git branch (`🌱 main ?`), Python virtualenv (`🐍`), and command duration.
2. **SSH Login Banner (`/root/.banner/motd.sh`):**
   - Glowing Cyan Cyber Sunglasses mascot.
   - 3D ANSI Shadow **CALCRUM** logo in magenta.
   - Real-time hardware telemetry: CPU load average, RAM percentage, NVMe disk usage, and Uptime.
   - Bot status badge: `● ACTIVE & RUNNING (24/7)`.
   - Daily rotating Peter Thiel contrarian startup quote.
3. **Shutdown / Reboot Screen (`/root/.banner/shutdown_screen.sh`):**
   - Aliased to `poweroff`, `shutdown`, and `reboot`.
   - Plays a 4-step buffer/database flush sequence with a giant electric red **`POWER OFF`** or cyan **`REBOOT`** banner.
4. **SSH Logout Card (`/root/.banner/logout.sh`):**
   - Configured in `~/.bash_logout` to display a clean session sign-off card when exiting.
5. **Productivity Aliases:**
   - `ll` / `tree` $\to$ `eza` (modern icon-based `ls`)
   - `top` $\to$ `btop` (neon gaming-tier hardware monitor)
   - `cat` $\to$ `bat` (syntax-highlighted code viewer)
   - `bot-status`, `bot-logs`, `bot-restart`, `bot-cd`

---

## 🚀 5. How to Better Utilize This VPS (Future Roadmap)

Currently, the VPS uses only **~90 MB out of 4,000 MB RAM (~2.2% utilization)** and **<5% disk space**. There is massive unused compute available for Calcrum infrastructure!

Here are the highest-leverage ways other LLMs and developers should utilize this VPS:

### 1. Host Staging / Internal API Webhooks (FastAPI or Next.js)
* **Current State:** Peter Thiel listens to Discord, but cannot currently receive incoming webhooks directly from third parties.
* **Upgrade:** Deploy a lightweight **FastAPI** or **Node.js** daemon listening on port `8000` or `3000`.
* **Use Cases:**
  - Ingest real-time GitHub PR/push webhooks.
  - Ingest bank/credit webhooks (Finvu Account Aggregator).
  - Razorpay / Cashfree payment and billing webhooks.

### 2. Reverse Proxy & Free SSL via Caddy or Nginx
* Install **Caddy** (zero-config automated SSL via Let's Encrypt):
  ```bash
  sudo apt-get install -y caddy
  ```
* Map a domain (e.g. `api.calcrum.com` or `ops.calcrum.com`) directly to `51.68.205.225:20022` to expose HTTPS endpoints securely.

### 3. Automated Offsite Database Backups
* SQLite (`data/founder_ops.db`) holds irreplaceable founder review history and earnout ledgers.
* **Task:** Create a cron job (`/etc/cron.daily/backup-calcrum-db`) that dumps and encrypts `founder_ops.db` and pushes it to **Cloudflare R2**, **AWS S3**, or **Google Drive**.

### 4. WhatsApp & Telegram Operations Bridges
* Calcrum's backend architecture references a WhatsApp Baileys engine.
* The VPS can easily host a persistent Node.js/Python headless WhatsApp listener to let founders send receipts, voice notes, and quick commits directly into the Calcrum ledger via WhatsApp.

### 5. Dockerized Microservices
* Docker is not currently running. Installing `docker.io` and `docker-compose` will allow spinning up:
  - **PostgreSQL / Redis** (if migrating off SQLite for high-concurrency event queues).
  - Self-hosted analytical dashboards (e.g., Metabase or Grafana).

---

## 🛡️ 6. Critical Invariants for Autonomous AI Agents

When modifying this repository, any LLM **MUST** respect these four rules:

1. **Language Invariant (10-Year-Old Plain English)**:
   - Founder-facing text (praise, bottlenecks, inquiries, score summaries) must be clear, conversational, and direct.
   - Absolutely no corporate jargon (*"synergies"*, *"paradigms"*, *"moats"*).
2. **Anti-Gaming Invariant**:
   - Chat claims without artifacts = capped at `0.3–0.5`.
   - Modest claims backed by tangible PRs, commits, and logs = rewarded with `1.0`.
3. **Async / Non-Blocking Discipline**:
   - Never run blocking I/O or synchronous HTTP calls on the Discord event loop.
   - Wrap heavy external calls in `await asyncio.to_thread(...)`.
4. **100% Test Coverage Requirement**:
   - All 37 unit tests must remain green:
     ```bash
     python -m pytest tests/ -v
     ```
   - Any new feature, route, or formula change must include unit tests in `tests/`.

---

## 🔑 7. Environment Variables (`.env`)

Secrets are stored in `/root/peter-thiel-review-agent/.env` on the VPS and `d:\Review agent\.env` locally:

```env
# Discord Bot Token (Stored securely in VPS .env)
DISCORD_BOT_TOKEN="your_active_discord_bot_token_from_vps_env"

# Google Gemini API Key (Multimodal parsing & evaluation)
GEMINI_API_KEY="your_active_gemini_api_key_from_vps_env"

# Local Server Settings
PORT=10000
TZ=Asia/Kolkata
```

### Discord Monitored Channels:
* `#daily-reports`: `1511606229951057921` (Daily check-ins, inquiries, scoring digests)
* `#dev-updates`: `1508293104371896330` (Technical updates, commits, architecture)
* `#dev-general`: `1510083831405875391` (General engineering discussion)
* `#leadership`: `1512741480039714947` (SWOT reports & monthly equity ratifications)
* `#marketing-updates`: `1508285631783108628`
* `#sales-updates`: `1508301322695348415`
* `#finance-updates`: `1511995144117817404`
