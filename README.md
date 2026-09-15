# 🕶️ Peter Thiel • Krishna Engineering OS Founder Operations Bot

> **Non-Technical Guide:** For non-technical founders, operators, or anyone who wants a plain-English troubleshooting manual, check out the [**Non-Tech Founder's Debugging Guide**](docs/NON_TECH_DEBUGGING_GUIDE.md).

An autonomous 24/7 Discord agent built for early-stage founders operating under **Hridesh's Systems Thinking Framework** and the **Krishna Engineering OS**.

---

## 🧭 Core Philosophy & Systems Design

> *"Reality is constantly changing. Therefore, a good system cannot be designed to be permanently correct. It must be perceptive enough to notice when reality is changing and adaptive enough to change with it."*

This bot solves founder operational friction:
1. **Zero Reporting Overhead**: Founders communicate naturally in `#dev-updates`, `#sales-updates`, etc. The bot ambiently listens.
2. **Asymmetric Work Normalization**: Standardizes code commits (CTO), operational throughput (COO), and strategic steering (CEO) into a unified power-law complexity rubric ($W_i \in [1, 5]$).
3. **High-Stakes Equity Evolution**: Implements a **24-month dynamic earnout (Slicing Pie)** releasing $\Delta E \approx 2.2917\%$ monthly, protected by a $60\%$ safety floor that diverts unearned equity into a Company Treasury rather than creating toxic zero-sum founder cannibalization.

---

## ⏰ Daily, Weekly & Monthly Cadence

| Time | Channel | Action |
| :--- | :--- | :--- |
| **8:00 PM Daily** | `#daily-reports` | Bot evaluates daytime updates against locked goals, computes $S_{\text{daily}}$, generates the **Win of the Day**, and posts the scorecard. |
| **9:00 PM Daily** | `#daily-reports` | Bot pings all 3 founders to declare 2-4 commitments for tomorrow before sleep. Gemini parses freeform text into structured JSON. |
| **Sunday 9:00 PM** | `#leadership` | Synthesizes 7-day scoring distributions into a depersonalized **Executive SWOT Report** (Strengths, Weaknesses, Opportunities, Threats). |
| **1st of Month 10:00 AM** | `#leadership` | Unlocks the monthly tranche ($\Delta E = 2.2917\%$) and posts the **Provisional Equity Evolution Report** requiring founder verification. |

---

## 🧮 The Krishna OS Mathematical Formulation

### 1. Daily Individual Score ($S_{\text{daily}}$)
$$S_{\text{daily}} = \left( \sum_{i=1}^n C_i \times W_i \times A_{\text{dharma}} \right) \times M_{\text{peer}} + I_{\text{bonus}}$$

* **Completion ($C_i \in [0.0, 1.0]$)**: Evaluated by Gemini 2.5 Flash from updates and commit links.
* **Complexity ($W_i \in [1, 5]$)**:
  * `1` = Quick chore / email (<15m) *(4th+ trivial task discounted by 75% to prevent task-stuffing)*.
  * `3` = Core feature milestone, partner pitch (2-3h).
  * `5` = Existential breakthrough, zero-day crisis, major deal close (>6h).
* **Role Dharma ($A_{\text{dharma}} \in [0.8, 1.2]$)**:
  * `1.2` = High-leverage execution on core role duty.
  * `1.0` = Standard cross-functional work.
  * `0.8` = Distracting busywork.
* **Peer Reaction Multiplier ($M_{\text{peer}} \in [0.8, 1.2]$)**:
  $$M_{\text{peer}} = \text{clamp}(1.0 + 0.05 \cdot N_{✅} + 0.10 \cdot N_{🔥} - 0.15 \cdot N_{⚠️}, 0.8, 1.2)$$
  *(Self-reactions are strictly filtered).*
* **Bonus Points ($I_{\text{bonus}} \in [0, 5]$)**: For unscripted firefighting or urgent wins.

---

### 2. Monthly 24-Month Dynamic Earnout Math
* **Cap Table Baseline**:
  * **Hridesh (CEO)**: $45.000\%$ (Fully vested, non-dilutable baseline).
  * **Swarit (CTO)**: $25.000\%$ unvested target (baseline weight $45.45\%$).
  * **Rahul (COO)**: $30.000\%$ unvested target (baseline weight $54.55\%$).
* **Monthly Tranche**:
  $$\Delta E = \frac{55.0\%}{24} \approx 2.2916667\%$$
* **Score Ratio**:
  $$\text{Ratio}_{\text{CTO}} = \frac{S_{\text{CTO}}}{S_{\text{CTO}} + S_{\text{COO}}}, \quad \text{Ratio}_{\text{COO}} = \frac{S_{\text{COO}}}{S_{\text{CTO}} + S_{\text{COO}}}$$
* **Safety Floor ($S_{\text{min}} = 60\%$)**: If a founder's output drops below $60\%$ of target baseline, the unearned difference flows into the **Company Treasury Reserve**, eliminating zero-sum competition.

---

## 🎮 Discord Slash Commands

* `/set-role [role: hridesh|swarit|rahul] [member]` — Link Discord account to founder role.
* `/goals [founder] [date]` — Inspect locked commitments for any date.
* `/score [founder] [date]` — View full score report, peer multipliers, and systems feedback.
* `/leaderboard` — View founder streaks and execution momentum.
* `/equity` — View current Cap Table, cumulative earned equity, and tranche progression.
* `/calculate-today` — Force-run 8:00 PM scoring calculation on demand.
* `/prompt-goals` — Force-run 9:00 PM goal declaration prompt on demand.
* `/confirm-equity [month_index]` — Ratify monthly dynamic earnout into permanent standing.

---

## 🧪 Running the Verification Test Suite

```bash
python -m unittest tests/test_engine.py
```
Verifies:
1. Peer multiplier clamping $[0.8, 1.2]$ and self-reaction filtering.
2. Daily scoring formula and anti-task-stuffing discounts.
3. Conservation of equity across all 24 months ($\sum E \equiv 100.0\%$).
4. Safety floor diversion to Company Treasury.
5. Async SQLite database persistence and schema migrations.
6. Fallback heuristic parsers for offline/resilient execution.

---

## 🚀 Running the Bot 24/7

```bash
# 1. Install dependencies
pip install discord.py google-genai python-dotenv aiosqlite

# 2. Launch the 24/7 bot daemon
python main.py
```
