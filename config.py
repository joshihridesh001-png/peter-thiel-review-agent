"""
Central Configuration for the Krishna Engineering OS Founder Operations Bot.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

import zoneinfo

# Load .env if present
load_dotenv()

# Timezone (defaults to Asia/Kolkata for IST schedule)
TIMEZONE_STR = os.getenv("TZ", "Asia/Kolkata")
try:
    TIMEZONE = zoneinfo.ZoneInfo(TIMEZONE_STR)
except Exception:
    TIMEZONE = zoneinfo.ZoneInfo("Asia/Kolkata")

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "founder_ops.db"

# Discord Bot Token
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# ── Discord Channel Mapping ──────────────────────────────────────────────────
# Mapped directly from the send-to-discord skill configuration
CHANNELS = {
    # Development
    "dev-general": 1510083831405875391,        # Dev general discussion & engineering architecture
    "dev-updates": 1508293104371896330,        # CTO (Swarit) primary update feed
    "dev-ideas": 1508149700639985725,          # Architecture ideas & system designs
    # Sales
    "sales-updates": 1508301322695348415,      # Sales & onboarding feed (includes Peter Thiel assistant drops)
    "sales-general": 1510084020870975539,      # Sales pipeline & lead discussions
    "sales-ideas": 1508299264684724326,        # Sales strategies & pitches
    # Marketing
    "marketing-updates": 1508285631783108628,  # Marketing campaign & growth feed
    "marketing-general": 1510083922011099166,  # Marketing general discussions
    "marketing-ideas": 1508285422218772504,    # Content ideas & scripts
    # Finance
    "finance-updates": 1511995144117817404,    # Finance & ops feed
    "finance-general": 1510084175871348746,    # Finance discussions
    # Design
    "design-general": 1529324256796868689,     # UI/UX design general
    # Server-wide & Leadership
    "general": 1471340826977239216,            # Main server general chat
    "daily-reports": 1511606229951057921,      # Primary goal-setting & daily scoring thread/channel
    "leadership": 1512741480039714947,         # Weekly SWOT and monthly equity ledger announcements
    "scores": 1549488768585695355,             # Scores channel
}

# The channel where daily 9 PM goals and 8 PM digests are posted by default
PRIMARY_GOALS_CHANNEL_ID = CHANNELS["daily-reports"]
LEADERSHIP_CHANNEL_ID = CHANNELS["leadership"]
SCORES_CHANNEL_ID = CHANNELS["scores"]

# Channels monitored for daytime work updates
MONITORED_UPDATE_CHANNELS = set(CHANNELS.values())

# Automated bot embeds that should NOT be counted as work updates
SYSTEM_EMBED_TITLES = {
    "Daily Scorecard",
    "Commitment Lock",
    "Monthly Equity Evolution",
    "Strategic Executive SWOT",
    "Cloud Deployment Live",
}

# ── Founder Profiles & Initial Cap Table ──────────────────────────────────────
# CEO: Hridesh (45% fully vested)
# CTO: Swarit (25% target unvested, dynamic 24-month earnout)
# COO: Rahul (30% target unvested, dynamic 24-month earnout)
FOUNDERS = {
    "hridesh": {
        "display_name": "Hridesh",
        "role": "CEO",
        "vested_equity": 45.0,
        "unvested_target": 0.0,
        "dharma_focus": [
            "Company vision and strategy",
            "Fundraising and capital allocation",
            "Key enterprise partnerships & high-stakes negotiations",
            "Team direction, systems architecture & bottleneck removal",
        ],
        "discord_id": int(os.getenv("DISCORD_USER_HRIDESH", "1159464740788109312")),
        "usernames": ["hridesh_joshi", "hridesh"],
    },
    "swarit": {
        "display_name": "Swarit",
        "role": "CTO",
        "vested_equity": 0.0,
        "unvested_target": 25.0,
        "dharma_focus": [
            "Core code architecture & deep engineering execution",
            "Shipping product features & merging critical PRs",
            "System reliability, uptime, and database performance",
            "Technical documentation, refactoring & security",
        ],
        "discord_id": int(os.getenv("DISCORD_USER_SWARIT", "1419294391041921125")),
        "usernames": ["swarit_soni", "swarit"],
    },
    "rahul": {
        "display_name": "Rahul",
        "role": "COO",
        "vested_equity": 0.0,
        "unvested_target": 30.0,
        "dharma_focus": [
            "Operational throughput & SOP execution",
            "Sales pipeline, client outreach, and conversion tracking",
            "Marketing campaign rhythm & growth delivery",
            "Cross-functional blocker clearing & team coordination",
        ],
        "discord_id": int(os.getenv("DISCORD_USER_RAHUL", "1541842669922295980")),
        "usernames": ["2muchmotion__", "rahul", "rahul's bitch"],
    },
}

# ── Dynamic Earnout & Equity Parameters ───────────────────────────────────────
TOTAL_UNVESTED_POOL = 55.0         # 25% (Swarit) + 30% (Rahul)
VESTING_HORIZON_MONTHS = 24        # 2-Year horizon
MONTHLY_TRANCHE_EQUITY = TOTAL_UNVESTED_POOL / VESTING_HORIZON_MONTHS  # ~2.2916667%

# Baseline target weights within the unvested pool
TARGET_UNVESTED_WEIGHTS = {
    "swarit": 25.0 / TOTAL_UNVESTED_POOL,  # ~0.454545 (45.45%)
    "rahul": 30.0 / TOTAL_UNVESTED_POOL,   # ~0.545455 (54.55%)
}

# Safety Floor: minimum monthly performance threshold as ratio of peer baseline
PERFORMANCE_SAFETY_FLOOR = 0.60    # 60% of expected baseline

# ── Mathematical Scoring Weights & Bounds ─────────────────────────────────────
COMPLEXITY_RANGE = (1, 5)          # W_i complexity weights (1 to 5)
ROLE_DHARMA_RANGE = (0.8, 1.2)     # A_dharma alignment multiplier
PEER_FACTOR_RANGE = (0.8, 1.2)     # M_peer reaction multiplier clamp
BONUS_POINTS_MAX = 5.0             # I_bonus spontaneous firefighting bonus

# Peer emoji weights
PEER_EMOJIS = {
    "✅": 0.05,    # Verified execution
    "🔥": 0.10,    # Exceptional systems impact
    "⚠️": -0.15,   # Quality concern / dispute / low leverage
}

# ── Scheduled Timings (24-Hour Clock, Local Time) ─────────────────────────────
DAILY_SCORING_HOUR = 20            # 8:00 PM (Scoring, Praise, Daily Digest)
DAILY_GOALS_HOUR = 21              # 9:00 PM (Prompt for Tomorrow's Goals)
WEEKLY_SWOT_DAY = 6                # Sunday (0 = Monday, 6 = Sunday)
WEEKLY_SWOT_HOUR = 21              # Sunday 9:00 PM
MONTHLY_CLOSE_DAY = 1              # 1st day of month
MONTHLY_CLOSE_HOUR = 10            # 10:00 AM
