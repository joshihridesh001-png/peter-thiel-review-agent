"""
Post today's development progress update to Discord #dev-general (ID: 1510083831405875391).
Can be run on VPS or locally.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Channel mapping
CHANNEL_MAP = {
    "dev-updates": "1508293104371896330",
    "dev-general": "1510083831405875391",
}
CHANNEL_ID = CHANNEL_MAP["dev-updates"]

for arg in sys.argv[1:]:
    clean_arg = arg.strip()
    if clean_arg in CHANNEL_MAP:
        CHANNEL_ID = CHANNEL_MAP[clean_arg]
    elif clean_arg.isdigit():
        CHANNEL_ID = clean_arg
    elif len(clean_arg) > 40:
        TOKEN = clean_arg



if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN is not set.")
    sys.exit(1)

payload = {
    "embeds": [
        {
            "title": "🚀 Peter Thiel 2.0 • Autonomous 24/7 Operations Live!",
            "description": (
                "Today we successfully upgraded the **Peter Thiel Review & Operations Agent** "
                "from a local prototype into an autonomous, 24/7 server daemon with multi-modal intelligence, "
                "anti-gaming validation, and automated GitHub PR reviews via Google Jules."
            ),
            "color": 0x5865F2,
            "fields": [
                {
                    "name": "👁️ Multi-Modal Engine & Gemini Vision",
                    "value": (
                        "• **File Reading**: Automatically parses `.md`, `.txt`, and `.csv` attachments up to 250KB.\n"
                        "• **Gemini Vision**: Scans terminal logs, architecture diagrams, UI mockups, and metrics screenshots into plain English summaries.\n"
                        "• **Link Enrichment**: Expands GitHub PRs, commits, and Discord links into structured diff stats."
                    ),
                    "inline": False,
                },
                {
                    "name": "🔍 7:15 PM Pre-Scoring Context Check",
                    "value": (
                        "• Autonomous inquiry engine running daily at **19:15 IST** in `#daily-reports`.\n"
                        "• Scans all founder updates before the 8:00 PM cutoff.\n"
                        "• Asks at most 1 targeted question to clarify missing links or unbacked claims before final scoring."
                    ),
                    "inline": False,
                },
                {
                    "name": "⚖️ Anti-Gaming Verification Matrix",
                    "value": (
                        "• **Tangible Proof > Words**: Unbacked verbal claims capped at **0.3–0.5** completion.\n"
                        "• **Artifact Rewards**: Modest claims supported by PRs, commit diffs, or logs upgraded to full **1.0**."
                    ),
                    "inline": False,
                },
                {
                    "name": "🌐 24/7 Autonomous VPS Daemon",
                    "value": (
                        "• Live on `calcrum-main-vps` as an active `systemd` service (`peter-thiel.service`).\n"
                        "• Fully self-healing with automatic restarts on system reboot.\n"
                        "• Zero dependency on local dev machines."
                    ),
                    "inline": False,
                },
                {
                    "name": "🐙 Google Jules Connected & PR #1 Merged",
                    "value": (
                        "• Integrated Google Jules AI reviewer via `AGENTS.md` and GitHub Actions.\n"
                        "• Merged automated PR #1 with audited test suites and math fixes.\n"
                        "• **All 37/37 unit tests passing green** (`pytest tests/ -v`)."
                    ),
                    "inline": False,
                },
                {
                    "name": "⏱️ Tonight's Operational Schedule (IST)",
                    "value": (
                        "• **7:15 PM**: Context Gap Inquiry in `#daily-reports`\n"
                        "• **8:00 PM**: Daily Scorecards & Win of the Day\n"
                        "• **9:00 PM**: Nightly Commitment Lock for Tomorrow"
                    ),
                    "inline": False,
                },
            ],
            "footer": {
                "text": "Krishna Engineering OS • Systems Thinking Framework • 24/7 Operations"
            },
        }
    ]
}

url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (https://github.com/joshihridesh001-png/peter-thiel-review-agent, 2.0)",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode("utf-8"))
        print(f"SUCCESS: Message posted to Discord! Message ID: {res.get('id')}")
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"FAILED: HTTP {e.code} - {err_body}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
