# 🛠️ The Non-Tech Founder's Complete Troubleshooting & Debugging Guide

> **"If you can send a message on WhatsApp and open a browser, you can debug this bot."**
> This guide is written in plain English for CEOs, COOs, and operators. No computer science degree required.

---

## 🧭 The 30-Second Mental Model: How Peter Thiel Actually Works

Think of Peter Thiel as an invisible team assistant sitting in your Discord server:

```text
[Daytime]
You talk & work in channels (#dev-updates, #sales-updates)
        │
        ▼
[8:00 PM Daily] ──> Peter Thiel reads everything, grades your output, and posts your Scorecard & Praise
        │
        ▼
[9:00 PM Daily] ──> Peter Thiel pings you: "Declare tomorrow's goals before sleep"
        │
        ▼
[End of Month] ───> Peter Thiel calculates the dynamic equity split between CTO & COO (Month by Month)
```

---

## 🚨 Emergency Troubleshooting Cheat Sheet (Common Issues)

| What Happened | Why It Happened | The 10-Second Fix |
| :--- | :--- | :--- |
| **"The bot is offline / gray icon"** | The computer running it went to sleep or the server restarted. | Open terminal, type `python main.py`, hit Enter. (Or check Render.com status). |
| **"It's 8:05 PM and no score was posted"** | No updates were posted in monitored channels, or time zone mismatch. | Run `/calculate-today` in Discord to force Peter Thiel to calculate scores immediately. |
| **"I posted goals at 9 PM but didn't get a lock confirmation"** | You posted in the wrong channel or didn't use bullet points. | Post them in `#daily-reports` or start your message with `Goal: ` or `Tomorrow: `. |
| **"My co-founder reacted with 🔥 but my score didn't change"** | Did you react to *your own* message? Self-reactions are blocked to prevent cheating! | Have another co-founder react. Only *peer* reactions count. |
| **"The bot says 'Unknown Command'"** | Slash commands take up to 60 seconds to sync when restarted. | Restart Discord (Ctrl + R on Windows/Mac) or wait 1 minute. |
| **"Someone was sick and their equity didn't go to the other founder"** | **By design!** The 60% safety floor sent it to the Company Treasury so founders don't profit off each other's illness. | Check the Treasury line in the monthly report. This is fair systems engineering. |

---

## 🔍 Deep-Dive Diagnostic Scenarios

---

### Scenario 1: The Bot Went Offline (How to Revive It)

#### Step 1: Check if the program is running
If you are running the bot locally on your laptop/PC:
1. Open PowerShell or Command Prompt.
2. Navigate to the bot directory:
   ```bash
   cd "D:\Review agent"
   ```
3. Type:
   ```bash
   python main.py
   ```
4. If you see:
   ```text
   🚀 Bot connected as Peter Thiel (ID: 1511743022222540810)
   ✨ Synced 8 application slash commands.
   ```
   **Congratulations, he is back online!** Keep that window open (or minimized).

#### Step 2: If running in the cloud (Render / Koyeb)
1. Go to your dashboard at [render.com](https://dashboard.render.com).
2. Click on **Peter Thiel Bot**.
3. Look at the status pill:
   * **Green ("Live")**: Everything is fine.
   * **Red ("Failed")** or **Gray ("Suspended")**: Click the **Manual Deploy** button $\to$ **Deploy latest commit**.

---

### Scenario 2: "My Score Looks Too Low or Didn't Calculate"

#### Why this happens:
1. **Peter Thiel couldn't find evidence of your work**: If you spent 6 hours on a phone call or writing a private document, Peter Thiel has no way of knowing unless you drop a 1-sentence message in Discord (e.g. *"Finished 2hr partner call with Acme Corp; contract agreed"*).
2. **You logged 15 tiny chores**: If you logged 15 tasks like *"replied to an email"*, Peter Thiel's **Anti-Task-Stuffing Filter** gave you diminishing returns. High scores come from **Tier 3–5 milestones** (shipping code, closing a client, launching an SOP).

#### How to fix it in 5 seconds:
1. In Discord, type `/score founder:yourname` (e.g. `/score founder:hridesh`).
2. Read the **Systems Feedback** field. Peter Thiel will tell you exactly why points were awarded or docked.
3. Need to recalculate? Type:
   ```text
   /calculate-today
   ```
   This forces Peter Thiel to re-scan all channel messages from the last 24 hours.

---

### Scenario 3: Linking a New Discord Account (`/set-role`)

If Swarit, Rahul, or Hridesh gets a new Discord account, or the bot doesn't recognize who you are:

1. Go to any channel where Peter Thiel has access (e.g. `#daily-reports`).
2. Type:
   ```text
   /set-role
   ```
3. Select your role (`hridesh`, `swarit`, or `rahul`).
4. Select the Discord user (`@YourName`).
5. Hit **Enter**.
6. Peter Thiel will respond:
   ```text
   ✅ Founder Identity Linked
   Assigned @Hridesh as Hridesh (CEO) in the Krishna Engineering OS.
   ```

---

### Scenario 4: "I Want to Change the Channels Peter Thiel Listens To"

You don't need to touch complex code. Everything is stored in one simple settings file: [`config.py`](file:///d:/Review%20agent/config.py).

#### How to find channel IDs in Discord:
1. Open Discord Settings $\to$ **Advanced** $\to$ Turn on **Developer Mode**.
2. Right-click any channel in your server $\to$ click **Copy Channel ID**.
3. Open `config.py` in any text editor (Notepad, VS Code):
   ```python
   CHANNELS = {
       "dev-updates": 1508293104371896330,        # Paste new ID here
       "marketing-updates": 1508285631783108628,  # Paste new ID here
       "daily-reports": 1511606229951057921,      # Goal channel ID
   }
   ```
4. Save the file.
5. Restart the bot (`python main.py`).

---

### Scenario 5: Understanding the Monthly Equity Math (Without a Math Degree)

Here is how the dynamic earnout works in plain English:

1. **Hridesh (CEO)** already owns **45%**. His shares are **vested** and **never drop**.
2. **Swarit (CTO)** and **Rahul (COO)** have **55% unvested equity** to earn over **24 months**.
3. Every single month, a slice of **~2.29%** is released:
   $$\text{Monthly Slice} = \frac{55\%}{24} \approx 2.2917\%$$
4. **Who gets how much of that 2.29%?**
   * If Swarit earned 100 points and Rahul earned 100 points, they split that month's 2.29% equally ($50\% / 50\%$).
   * If Swarit crushed it with 150 points and Rahul got 50 points, Swarit gets $75\%$ of that month's slice and Rahul gets $25\%$.
5. **The "What if someone gets sick?" Rule (Safety Floor)**:
   * If Rahul is sick or travelling and scores very low (below 60% of normal), Swarit does **not** get to steal all his equity.
   * Rahul's unearned slice goes into the **Company Treasury Reserve**.
   * Why? **Because founders should never profit from their partner's misfortune.**

---

### Scenario 6: How to Ratify Monthly Equity (`/confirm-equity`)

On the 1st of every month at 10:00 AM:
1. Peter Thiel posts a **Draft Monthly Equity Evolution Report** in `#leadership`.
2. All 3 founders review the scores.
3. If everyone agrees, any founder types:
   ```text
   /confirm-equity month_index:1
   ```
4. Peter Thiel permanently locks the equity into the database ledger. It can never be silently modified or corrupted.

---

## 🧪 Self-Healing Test: How to Verify Everything Works in 1 Command

If you ever feel something is broken, run this in your terminal:

```bash
python -m unittest tests/test_engine.py
```

* If it outputs `OK` at the end:
  ```text
  .......
  ----------------------------------------------------------------------
  Ran 7 tests in 0.221s

  OK
  ```
  **The entire system is 100% healthy.** The database, formulas, peer reaction clamps, and AI fallbacks are all operating normally.

---

## 📞 Quick Reference: Channel ID Aliases

* `#dev-updates`: `1508293104371896330` (CTO Primary Feed)
* `#marketing-updates`: `1508285631783108628` (COO Growth Feed)
* `#sales-updates`: `1508301322695348415` (COO Sales Feed)
* `#daily-reports`: `1511606229951057921` (9 PM Goal Lock & 8 PM Scorecard)
* `#leadership`: `1512741480039714947` (Sunday SWOT & Monthly Equity Ledger)
