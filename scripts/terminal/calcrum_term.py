#!/usr/bin/env python3
"""
Calcrum terminal experience for the VPS.

Look and feel is taken from calcrum.com:
  - teal brand accent  #006878   (gear logo, bars, chips)
  - cream cards        #FAF7F0   (the floating "hcard" dashboard cards)
  - kept-green         #15803D   ("Matched", "Ready" chips)
  - leak-red           #D93829
  - the gear "C" logo mark, spinning like an engine on autopilot

Commands:
  calcrum login                 animated welcome dashboard (runs on SSH login)
  calcrum logout                short sign-off card
  calcrum poweroff [-y] [--dry-run]
  calcrum reboot   [--dry-run]

Env:
  CALCRUM_FAST=1   skip animation (also automatic when stdout is not a TTY)
  Ctrl+C during the animation skips straight to the finished screen.

Standard library only, so it works on a fresh Ubuntu box.
"""

import math
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SERVICE = "peter-thiel.service"

FAST = os.environ.get("CALCRUM_FAST") == "1" or not sys.stdout.isatty()

# ── Brand palette (from calcrum.com CSS variables) ──────────────────────────
TEAL = (0, 104, 120)          # --accent
TEAL_HI = (38, 166, 182)      # brighter teal so it reads on a dark terminal
CREAM = (250, 247, 240)       # --bg-page
CREAM_DIM = (170, 165, 152)
INK = (31, 31, 31)            # --text-main
INK_SOFT = (95, 99, 104)      # --text-secondary
BORDER = (232, 228, 218)      # --border
GREEN = (21, 128, 61)         # --green-kept
GREEN_HI = (52, 199, 89)
CHIP_BG = (220, 252, 231)
CHIP_FG = (22, 101, 52)
RED = (217, 56, 41)           # --red-leaks
RED_BG = (254, 226, 226)
RED_FG = (185, 28, 28)
AMBER_BG = (254, 243, 199)
AMBER_FG = (180, 83, 9)
TERM_BG = (24, 24, 24)        # what we fade towards on power-off

RESET = "\033[0m"
BOLD = "\033[1m"
NOBOLD = "\033[22m"
HIDE = "\033[?25l"
SHOW = "\033[?25h"
SPIN = "◐◓◑◒"

ANSI_RE = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

W = 62          # card width (recomputed from terminal size at runtime)
COMPACT = False  # narrow terminal: skip the big wordmark


def fg(c):
    return f"\033[38;2;{c[0]};{c[1]};{c[2]}m"


def bg(c):
    return f"\033[48;2;{c[0]};{c[1]};{c[2]}m"


def vlen(s):
    """Visible length of a string, ignoring ANSI escape codes."""
    return len(ANSI_RE.sub("", s))


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def out(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def pause(sec):
    """Sleep unless we are in fast mode. Ctrl+C switches to fast mode."""
    global FAST
    if FAST:
        return
    try:
        time.sleep(sec)
    except KeyboardInterrupt:
        FAST = True


def line(s, delay=0.012):
    out(s + "\n")
    pause(delay)


# ── Pixel art: gear logo + wordmark (rendered with half-blocks) ─────────────

def gear_bitmap(theta, size=18, teeth=8):
    """Gear with a 'C' opening on the right, like the Calcrum logo mark.

    Teeth rotate with theta; the C opening stays put, so it looks like an
    engine turning inside the logo.
    """
    c = (size - 1) / 2.0
    r_tooth = size / 2.0
    r_body = r_tooth * 0.74
    r_hole = r_tooth * 0.40
    rows = []
    for py in range(size):
        row = []
        for px in range(size):
            dx, dy = px - c, c - py
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            on = False
            if r_hole < r <= r_body:
                on = True
            elif r_body < r <= r_tooth:
                t = ((a - theta) * teeth / (2 * math.pi)) % 1.0
                on = t < 0.5
            if on and abs(a) < 0.38:
                on = False  # the "C" opening
            row.append(on)
        rows.append(row)
    return rows


FONT = {
    "C": [".#####.", "##...##", "##.....", "##.....", "##.....", "##.....", "##...##", ".#####."],
    "a": ["......", "......", "......", ".####.", "....##", ".#####", "##..##", ".#####"],
    "l": ["##", "##", "##", "##", "##", "##", "##", "##"],
    "c": [".....", ".....", ".....", ".####", "##...", "##...", "##...", ".####"],
    "r": [".....", ".....", ".....", "##.##", "###..", "##...", "##...", "##..."],
    "u": ["......", "......", "......", "##..##", "##..##", "##..##", "##..##", ".#####"],
    "m": ["........", "........", "........", "#######.", "##.##.##", "##.##.##", "##.##.##", "##.##.##"],
}


def word_bitmap(text):
    rows = [[] for _ in range(8)]
    for i, ch in enumerate(text):
        glyph = FONT[ch]
        for r in range(8):
            if i:
                rows[r].append(False)
            rows[r].extend(cell == "#" for cell in glyph[r])
    return rows


WORD = word_bitmap("Calcrum")


def halfblock(bitmap, color_fn):
    """Turn a pixel bitmap into terminal lines, 2 pixel rows per text row."""
    lines = []
    for y in range(0, len(bitmap), 2):
        top = bitmap[y]
        bot = bitmap[y + 1] if y + 1 < len(bitmap) else [False] * len(top)
        parts = []
        for x, (t, b) in enumerate(zip(top, bot)):
            if t and b:
                ch = "█"
            elif t:
                ch = "▀"
            elif b:
                ch = "▄"
            else:
                parts.append(" ")
                continue
            parts.append(fg(color_fn(x)) + ch)
        lines.append("".join(parts) + RESET)
    return lines


# ── Hero: gear + wordmark + tagline (mirrors the calcrum.com hero) ──────────

TAGLINE = [(ch, CREAM_DIM, False) for ch in "Your business's finance, "] + \
          [(ch, TEAL_HI, True) for ch in "on autopilot."]


def _fade(c, f):
    return lerp(c, TERM_BG, f)


def tagline(typed, fade=0.0):
    parts = []
    for ch, color, bold in TAGLINE[:typed]:
        parts.append((BOLD if bold else NOBOLD) + fg(_fade(color, fade)) + ch)
    if typed < len(TAGLINE):
        parts.append(fg(TEAL_HI) + "▌")
    return "".join(parts) + RESET


def badge_line(host, fade=0.0):
    return (fg(_fade(GREEN_HI, fade)) + "● " + fg(_fade(CREAM_DIM, fade)) +
            f"{host}  ·  Peter Thiel ops daemon" + RESET)


def hero_lines(theta, host, reveal=999, typed=999, badge=True, shimmer=None, fade=0.0):
    gear = halfblock(gear_bitmap(theta),
                     lambda x: _fade(lerp(TEAL_HI, TEAL, x / 22.0), fade))
    right = [""] * len(gear)
    if COMPACT:
        right[2] = BOLD + fg(_fade(CREAM, fade)) + "Calcrum" + RESET
    else:
        masked = [[px and x < reveal for x, px in enumerate(row)] for row in WORD]

        def wcol(x):
            c = CREAM
            if shimmer is not None:
                c = lerp(CREAM, TEAL_HI, 1 - abs(x - shimmer) / 5.0)
            return _fade(c, fade)

        for i, l in enumerate(halfblock(masked, wcol)):
            right[1 + i] = l
    right[6] = tagline(typed, fade)
    right[7] = badge_line(host, fade) if badge else ""
    return ["  " + gear[i] + "    " + right[i] for i in range(len(gear))]


def draw(lines, first):
    if not first:
        out(f"\033[{len(lines)}A")
    for l in lines:
        out("\r" + l + "\033[K\n")


def animate_hero(host):
    if FAST:
        draw(hero_lines(0.3, host), True)
        return
    theta = 0.0
    step = (2 * math.pi / 8) / 3
    width = len(WORD[0])
    first = True
    for f in range(15):  # spin up while the wordmark wipes in
        draw(hero_lines(theta, host, reveal=int(width * (f + 1) / 15), typed=0, badge=False), first)
        first = False
        theta += step
        pause(0.035)
    for k in range(0, len(TAGLINE) + 1, 2):  # type the tagline
        draw(hero_lines(theta, host, typed=k, badge=False), False)
        theta += step * 0.8
        pause(0.022)
    for f in range(14):  # shimmer across the wordmark, gear settles
        draw(hero_lines(theta, host, shimmer=-5 + (width + 10) * f / 13.0), False)
        theta += step * (1 - f / 14.0)
        pause(0.03)
    draw(hero_lines(theta, host), False)


# ── Cream dashboard cards (the "hcard" look from the website) ───────────────

def chip(text, chip_bg, chip_fg):
    return bg(chip_bg) + fg(chip_fg) + BOLD + f" {text} " + NOBOLD + bg(CREAM) + fg(INK)


def tag(text):
    return fg(INK_SOFT) + BOLD + text + NOBOLD + fg(INK)


def lbl(text):
    return fg(INK_SOFT) + text + fg(INK)


def val(text):
    return fg(INK) + BOLD + text + NOBOLD


def soft(text):
    return fg(INK_SOFT) + text + fg(INK)


def card_edge(top=True):
    return "  " + fg(CREAM) + ("▄" if top else "▀") * W + RESET


def card_row(left="", right=""):
    inner = W - 4
    pad = max(1, inner - vlen(left) - vlen(right))
    return ("  " + bg(CREAM) + fg(INK) + "  " + left + bg(CREAM) + " " * pad +
            right + bg(CREAM) + "  " + RESET)


def divider():
    return "  " + bg(CREAM) + "  " + fg(BORDER) + "─" * (W - 4) + "  " + RESET


def bar_row(pct, color):
    inner = W - 4
    n = int(round(inner * pct / 100.0))
    if pct > 0:
        n = max(1, n)
    n = min(inner, n)
    bar = fg(color) + "━" * n + fg(BORDER) + "━" * (inner - n)
    return "  " + bg(CREAM) + "  " + bar + "  " + RESET


# ── Server facts ────────────────────────────────────────────────────────────

def fmt_bytes(n):
    gib = 1024 ** 3
    if n >= gib:
        return f"{n / gib:.1f} GB"
    return f"{int(n / 1024 ** 2)} MB"


def fmt_uptime(secs):
    secs = int(secs)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} day{'s' if d != 1 else ''}, {h} hr{'s' if h != 1 else ''}"
    if h:
        return f"{h} hr{'s' if h != 1 else ''}, {m} min"
    return f"{m} min"


def _run_ok(cmd):
    """True/False from a command's exit code, None if it can't run here."""
    try:
        return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=3).returncode == 0
    except Exception:
        return None


def _failed_units():
    try:
        res = subprocess.run(["systemctl", "--failed", "--no-legend", "--plain"],
                             capture_output=True, text=True, timeout=3)
        return len([l for l in res.stdout.splitlines() if l.strip()])
    except Exception:
        return 0


def _pending_updates():
    try:
        with open("/var/lib/update-notifier/updates-available") as f:
            for l in f:
                m = re.search(r"(\d+)\s+updates? can be applied", l)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 0


def collect_metrics():
    m = {"host": socket.gethostname(), "uptime": "unknown",
         "mem_used": 0, "mem_total": 0, "disk_used": 0, "disk_total": 0, "load": None}
    try:
        with open("/proc/uptime") as f:
            m["uptime"] = fmt_uptime(float(f.read().split()[0]))
    except Exception:
        pass
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for l in f:
                k, v = l.split(":", 1)
                info[k] = int(v.strip().split()[0]) * 1024
        m["mem_total"] = info["MemTotal"]
        m["mem_used"] = info["MemTotal"] - info.get("MemAvailable", info.get("MemFree", 0))
    except Exception:
        pass
    try:
        du = shutil.disk_usage("/")
        m["disk_used"], m["disk_total"] = du.used, du.total
    except Exception:
        pass
    try:
        m["load"] = os.getloadavg()
    except Exception:
        pass
    m["bot_active"] = _run_ok(["systemctl", "is-active", "--quiet", SERVICE])
    m["failed_units"] = _failed_units()
    m["reboot_required"] = os.path.exists("/var/run/reboot-required")
    m["updates"] = _pending_updates()
    return m


def _pct(used, total):
    return used / total * 100.0 if total else 0.0


def rank_issues(m):
    """'What to fix first', ranked by impact, like the website's fix list."""
    issues = []
    disk = _pct(m.get("disk_used", 0), m.get("disk_total", 0))
    mem = _pct(m.get("mem_used", 0), m.get("mem_total", 0))
    if m.get("bot_active") is False:
        issues.append((100, "Peter Thiel is stopped", "bot-restart", "red"))
    if disk >= 85:
        issues.append((90, f"Disk is {disk:.0f}% full", "ncdu /", "red"))
    if m.get("failed_units"):
        n = m["failed_units"]
        issues.append((80, f"{n} service{'s' if n != 1 else ''} failed", "systemctl --failed", "red"))
    if mem >= 85:
        issues.append((70, "Memory is running tight", "top", "amber"))
    if m.get("reboot_required"):
        issues.append((60, "Reboot to finish updates", "reboot", "amber"))
    if m.get("updates"):
        n = m["updates"]
        issues.append((40, f"{n} package update{'s' if n != 1 else ''} waiting", "apt upgrade", "amber"))
    issues.sort(key=lambda i: -i[0])
    return [{"title": t, "hint": h, "tone": tone} for _, t, h, tone in issues]


# ── Login dashboard ─────────────────────────────────────────────────────────

def _countup_row(label, used, total):
    if total <= 0:
        line(card_row(lbl(label), val("n/a")))
        return
    frames = 1 if FAST else 12
    for i in range(1, frames + 1):
        e = 1 - (1 - i / frames) ** 3
        out("\r" + card_row(lbl(label), val(f"{fmt_bytes(used * e)} / {fmt_bytes(total)}")))
        pause(0.025)
    out("\n")


def card_health(m, issues):
    line(card_edge(True))
    line(card_row(tag("TODAY'S SERVER HEALTH"), chip("● LIVE", TEAL, CREAM)))
    line(card_row())
    label = lbl("Peter Thiel daemon")
    if not FAST:
        for i in range(6):
            out("\r" + card_row(label, soft("checking " + SPIN[i % 4])))
            pause(0.05)
    if m["bot_active"] is True:
        right = chip("Running ✓", CHIP_BG, CHIP_FG)
    elif m["bot_active"] is False:
        right = chip("Stopped ✕", RED_BG, RED_FG)
    else:
        right = chip("Unknown", AMBER_BG, AMBER_FG)
    out("\r" + card_row(label, right) + "\n")
    line(card_row(lbl("Uptime"), val(m["uptime"])))
    _countup_row("Memory", m["mem_used"], m["mem_total"])
    _countup_row("Disk", m["disk_used"], m["disk_total"])
    load = m["load"]
    line(card_row(lbl("Load average"),
                  val("  ·  ".join(f"{x:.2f}" for x in load) if load else "n/a")))
    line(divider())
    if issues:
        line(card_row(fg(AMBER_FG) + "● " + fg(INK) + "Needs a look. See what to fix below."))
    else:
        line(card_row(fg(GREEN) + "● " + fg(INK) + "Systems reconciled today"))
    line(card_edge(False))


def card_capacity(m):
    line(card_edge(True))
    line(card_row(tag("OUT OF EVERY 100% OF CAPACITY")))
    line(card_row())
    rows = [("Memory in use", _pct(m["mem_used"], m["mem_total"]), TEAL),
            ("Disk in use", _pct(m["disk_used"], m["disk_total"]), GREEN)]
    for idx, (label, pct, color) in enumerate(rows):
        line(card_row(lbl(label), val(f"{pct:.1f}%")))
        frames = 1 if FAST else 14
        for i in range(1, frames + 1):
            e = 1 - (1 - i / frames) ** 3
            out("\r" + bar_row(pct * e, color))
            pause(0.02)
        out("\n")
        if idx < len(rows) - 1:
            line(card_row())
    line(divider())
    free = 100 - rows[0][1]
    line(card_row(lbl("Headroom: ") + fg(GREEN) + BOLD + f"{free:.0f}% of memory" + NOBOLD +
                  lbl(" free to build on")))
    line(card_edge(False))


def card_fix(issues):
    line(card_edge(True))
    line(card_row(tag("WHAT TO FIX FIRST")))
    line(card_row())
    if not issues:
        line(card_row(val("Nothing to fix. Books are clean."), chip("0 left ✓", CHIP_BG, CHIP_FG)))
    else:
        for i, issue in enumerate(issues[:3], start=1):
            if issue["tone"] == "red":
                c = chip(f"#{i}", RED_BG, RED_FG)
            elif i == 1:
                c = chip(f"#{i}", AMBER_BG, AMBER_FG)
            else:
                c = chip(f"#{i}", BORDER, INK_SOFT)
            line(card_row(c + " " + val(issue["title"]), soft("run: " + issue["hint"])))
    line(divider())
    line(card_row(soft("Ranked by impact")))
    line(card_edge(False))


def _setup_layout():
    global W, COMPACT
    cols = shutil.get_terminal_size((80, 24)).columns
    W = max(40, min(62, cols - 4))
    COMPACT = cols < 72


def login():
    _setup_layout()
    m = collect_metrics()
    issues = rank_issues(m)
    out(HIDE)
    try:
        out("\033[2J\033[H\n")
        animate_hero(m["host"])
        out("\n")
        card_health(m, issues)
        out("\n")
        card_capacity(m)
        out("\n")
        card_fix(issues)
        out("\n")
        sep = fg(TEAL_HI) + "  ·  " + fg(CREAM_DIM)
        line("  " + fg(CREAM_DIM) + sep.join(
            ["bot-status", "bot-logs", "bot-restart", "top", "motd"]) + RESET)
        line("  " + fg(INK_SOFT) + "Calcrum Technologies  ·  Jaipur, India" + RESET)
        out("\n")
    finally:
        out(RESET + SHOW)


# ── Logout ──────────────────────────────────────────────────────────────────

def logout():
    host = socket.gethostname()
    gear = halfblock(gear_bitmap(0.2, size=10, teeth=6), lambda x: TEAL_HI)
    right = ["",
             BOLD + fg(CREAM) + "Session closed" + NOBOLD + fg(CREAM_DIM) + f"  ·  {host}" + RESET,
             fg(GREEN_HI) + "● " + fg(CREAM_DIM) + "Peter keeps watching 24/7." + RESET,
             "", ""]
    out("\n")
    for i, g in enumerate(gear):
        out("  " + g + "   " + right[i] + "\n")
    out(RESET + "\n")


# ── Power off / reboot: "closing the books" ─────────────────────────────────

def _stop_bot():
    try:
        return subprocess.run(["systemctl", "stop", SERVICE], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=25).returncode == 0
    except Exception:
        return False


def _sync():
    try:
        return subprocess.run(["sync"], timeout=25).returncode == 0
    except Exception:
        return False


def _sessions():
    try:
        res = subprocess.run(["who"], capture_output=True, text=True, timeout=3)
        return str(len([l for l in res.stdout.splitlines() if l.strip()]))
    except Exception:
        return "1"


def _run_step(label, fn):
    """Spin while fn runs in the background, then show its result chip."""
    result = {}
    t = threading.Thread(target=lambda: result.setdefault("v", fn()), daemon=True)
    t.start()
    i = 0
    while t.is_alive():
        out("\r" + card_row(lbl(label), soft("working " + SPIN[i % 4])))
        i += 1
        time.sleep(0.08)
    t.join()
    return result.get("v")


def power(action, assume_yes=False, dry_run=False):
    _setup_layout()
    host = socket.gethostname()

    if action == "poweroff" and not assume_yes:
        out("\n  " + fg(RED) + BOLD + f"● Power off {host}?" + NOBOLD + RESET + "\n")
        out("  " + fg(CREAM_DIM) + "Peter goes offline until you start the VPS again from your hosting dashboard." + RESET + "\n")
        out("  " + fg(CREAM_DIM) + "Just leaving? Type " + fg(TEAL_HI) + "exit" + fg(CREAM_DIM) +
            " instead. Peter keeps running." + RESET + "\n\n")
        try:
            answer = input("  Type yes to power off: ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() not in ("yes", "y"):
            out("  " + fg(GREEN_HI) + "● " + fg(CREAM_DIM) + "Cancelled. Nothing changed." + RESET + "\n\n")
            return 0

    out(HIDE + "\033[2J\033[H\n")
    try:
        title = "CLOSING THE BOOKS" if action == "poweroff" else "RESTARTING THE ENGINE"
        line(card_edge(True))
        line(card_row(tag(title), chip("● " + host, TEAL, CREAM)))
        line(card_row())

        steps = [
            ("Saving Peter's ledger", (lambda: True) if dry_run else _stop_bot, "Saved ✓"),
            ("Flushing disk writes", (lambda: True) if dry_run else _sync, "Done ✓"),
        ]
        for label, fn, ok_text in steps:
            ok = _run_step(label, fn)
            right = chip(ok_text, CHIP_BG, CHIP_FG) if ok else chip("Skipped", AMBER_BG, AMBER_FG)
            out("\r" + card_row(lbl(label), right) + "\n")
            pause(0.08)
        line(card_row(lbl("Open sessions"), val(_sessions())))
        line(card_row(lbl("Manual fixes"), val("0 left")))
        line(divider())
        line(card_row(fg(GREEN) + "● " + fg(INK) + "Clean books handed over"))
        line(card_edge(False))
        out("\n")

        # The gear winds down and fades into the dark.
        theta = 0.0
        speed = (2 * math.pi / 8) / 2.5
        frames = 1 if FAST else 26
        first = True
        for f in range(frames):
            fade = 0.0 if FAST else max(0.0, (f - 10) / 15.0)
            draw(hero_lines(theta, host, fade=fade * 0.85), first)
            first = False
            theta += speed * (1 - f / frames) ** 2
            pause(0.045)

        out("\n")
        if action == "poweroff":
            msg = "Powered off. Start it again from your VPS dashboard. Peter starts by himself."
        else:
            msg = "Rebooting. Back in about a minute. Peter starts by himself, SSH back in the same way."
        out("  " + fg(CREAM_DIM) + msg + RESET + "\n\n")
    finally:
        out(RESET + SHOW)

    if dry_run:
        out("  " + fg(AMBER_FG) + "(dry run: nothing was actually turned off)" + RESET + "\n\n")
        return 0
    return subprocess.run(["systemctl", action]).returncode


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    cmd, flags = argv[0], set(argv[1:])
    try:
        if cmd in ("login", "motd", "preview"):
            login()
        elif cmd == "logout":
            logout()
        elif cmd in ("poweroff", "shutdown"):
            return power("poweroff", assume_yes=bool(flags & {"-y", "--yes"}),
                         dry_run="--dry-run" in flags)
        elif cmd == "reboot":
            return power("reboot", dry_run="--dry-run" in flags)
        else:
            print(__doc__)
            return 1
    except KeyboardInterrupt:
        out(RESET + SHOW + "\n")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
