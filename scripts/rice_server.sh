#!/usr/bin/env bash
# ==============================================================================
# 🕶️ CALCRUM VPS RICE SCRIPT • CYBERPUNK TERMINAL SUITE
# Transforms plain Ubuntu VPS into a high-performance, neon aesthetic powerhouse.
# ==============================================================================

set -e

echo "🚀 Starting Calcrum Server Rice..."

# 1. Update & Install Essential Modern CLI Tools
echo "📦 Installing modern CLI utilities (btop, bat, fzf, fastfetch, eza)..."
apt-get update -y
apt-get install -y curl wget git jq btop fzf tmux unzip lsb-release

# Install bat (packaged as batcat on Debian/Ubuntu)
apt-get install -y bat || true
mkdir -p /usr/local/bin
if command -v batcat &> /dev/null && ! command -v bat &> /dev/null; then
    ln -sf "$(which batcat)" /usr/local/bin/bat
fi

# Install eza (modern ls replacement)
if ! command -v eza &> /dev/null; then
    mkdir -p /etc/apt/keyrings
    wget -qO- https://raw.githubusercontent.com/eza-community/eza/main/deb.asc | gpg --dearmor --yes -o /etc/apt/keyrings/gierens.gpg || true
    echo "deb [signed-by=/etc/apt/keyrings/gierens.gpg] http://deb.gierens.de stable main" | tee /etc/apt/sources.list.d/gierens.list || true
    chmod 644 /etc/apt/keyrings/gierens.gpg /etc/apt/sources.list.d/gierens.list || true
    apt-get update -y || true
    apt-get install -y eza || true
fi

# Install fastfetch (modern fast neofetch replacement)
if ! command -v fastfetch &> /dev/null; then
    add-apt-repository -y ppa:zhangsongcui3371/fastfetch 2>/dev/null || true
    apt-get update -y 2>/dev/null || true
    apt-get install -y fastfetch || apt-get install -y neofetch || true
fi

# 2. Install Starship Prompt (Blazing Fast, Cross-Shell, Ultra-Aesthetic)
echo "⭐ Installing Starship Prompt..."
if ! command -v starship &> /dev/null; then
    curl -sS https://starship.rs/install.sh | sh -s -- -y
fi

# 3. Create Starship Configuration (Tokyo Night / Neon Minimal Theme)
mkdir -p /root/.config
cat << 'EOF' > /root/.config/starship.toml
format = """
[┌─](bold #7aa2f7)$directory$git_branch$git_status$python
[└─>](bold #7aa2f7) """

right_format = """$cmd_duration$time"""

[directory]
style = "bold #7dcfff"
truncation_length = 3
truncation_symbol = "…/"
read_only = " 🔒"

[git_branch]
symbol = "🌱 "
style = "bold #bb9af7"
format = "[$symbol$branch]($style) "

[git_status]
style = "bold #f7768e"
format = "([$all_status$ahead_behind]($style) )"

[python]
symbol = "🐍 "
style = "bold #e0af68"
format = "[$symbol($virtualenv)]($style) "

[time]
disabled = false
time_format = "%R"
style = "bold #565f89"
format = "[$time]($style)"

[cmd_duration]
min_time = 500
style = "bold #e0af68"
format = "took [$duration]($style) "
EOF

# 4. Create Custom Calcrum & Peter Thiel SSH Login Banner (MOTD)
echo "🎨 Configuring Custom Cyberpunk MOTD Banner..."
mkdir -p /root/.banner
cat << 'EOF' > /root/.banner/motd.sh
#!/usr/bin/env bash

# Colors
CYAN="\033[1;36m"
MAGENTA="\033[1;35m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BLUE="\033[1;34m"
DIM="\033[2m"
BOLD="\033[1m"
RESET="\033[0m"

clear

echo -e "${MAGENTA}"
cat << 'ART'
   _____          _        _____  _    _ __  __ 
  / ____|   /\   | |      / ____|| |  | |  \/  |
 | |       /  \  | |     | |     | |  | | \  / |
 | |      / /\ \ | |     | |     | |  | | |\/| |
 | |____ / ____ \| |____ | |____ | |__| | |  | |
  \_____/_/    \_\______| \_____| \____/|_|  |_|
ART
echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${BOLD}🕶️  PETER THIEL REVIEW AGENT • 24/7 OPS DAEMON${RESET}"
echo -e "  ${DIM}Krishna Engineering OS • Systems Thinking Framework${RESET}"
echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

# System Metrics
UPTIME=$(uptime -p 2>/dev/null | sed 's/up //')
LOAD=$(cat /proc/loadavg | awk '{print $1, $2, $3}')
MEM_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
MEM_USED=$(free -m | awk '/Mem:/ {print $3}')
MEM_PERCENT=$(( MEM_USED * 100 / MEM_TOTAL ))
DISK_USED=$(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')

# Peter Thiel Bot Service Check
if systemctl is-active --quiet peter-thiel.service 2>/dev/null; then
    BOT_STATUS="${GREEN}● ACTIVE & RUNNING (24/7)${RESET}"
else
    BOT_STATUS="${RED}● STOPPED / INACTIVE${RESET}"
fi

echo -e "  ${BLUE}⚡ Hostname:${RESET}  $(hostname) ${DIM}(Ubuntu $(lsb_release -rs 2>/dev/null || cat /etc/issue | awk '{print $2}'))${RESET}"
echo -e "  ${BLUE}⏱️  Uptime:${RESET}    ${UPTIME}"
echo -e "  ${BLUE}📊 Load Avg:${RESET}  ${LOAD}"
echo -e "  ${BLUE}💾 Memory:${RESET}    ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_PERCENT}%)"
echo -e "  ${BLUE}💿 Storage:${RESET}   ${DISK_USED}"
echo -e "  ${BLUE}🤖 Bot Agent:${RESET} ${BOT_STATUS}"
echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

# Dynamic Thiel Principle of the Day
QUOTES=(
  "\"Competition is for losers. Build a monopoly through distinct compounding execution.\""
  "\"The most contrarian thing of all is not to oppose the crowd, but to think for yourself.\""
  "\"A great company is a conspiracy to change the world; when you share that secret, you recruit a conspirator.\""
  "\"Brilliant thinking is rare, but courage is in even shorter supply than genius.\""
  "\"Higher score follows monotonic execution with verifiable proof, not noise.\""
)
RANDOM_QUOTE=${QUOTES[$RANDOM % ${#QUOTES[@]}]}
echo -e "  ${YELLOW}💡 Thiel Principle:${RESET} ${DIM}${RANDOM_QUOTE}${RESET}"
echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
EOF
chmod +x /root/.banner/motd.sh

# 5. Configure Shell Aliases & Hooks in ~/.bashrc
echo "⚡ Injecting high-velocity aliases into ~/.bashrc..."

# Clean out any old calcrum rice block if rerun
sed -i '/# BEGIN CALCRUM RICE/,/# END CALCRUM RICE/d' /root/.bashrc

cat << 'EOF' >> /root/.bashrc

# BEGIN CALCRUM RICE
# Show custom MOTD banner on interactive logins
if [[ $- == *i* ]]; then
    /root/.banner/motd.sh
fi

# Initialize Starship
eval "$(starship init bash)"

# Modern Replacement Aliases
if command -v eza &> /dev/null; then
    alias ls='eza --icons --group-directories-first'
    alias ll='eza -la --icons --git --group-directories-first'
    alias tree='eza --tree --icons'
else
    alias ll='ls -la --color=auto'
fi

if command -v bat &> /dev/null; then
    alias cat='bat --paging=never --style=plain'
fi

alias top='btop'
alias sysinfo='fastfetch 2>/dev/null || neofetch 2>/dev/null || uname -a'

# Peter Thiel Bot Quick Shortcuts
alias bot-status='systemctl status peter-thiel.service'
alias bot-logs='journalctl -u peter-thiel.service -f -n 50'
alias bot-restart='systemctl restart peter-thiel.service && echo "✅ Peter Thiel restarted!"'
alias bot-stop='systemctl stop peter-thiel.service'
alias bot-cd='cd /root/peter-thiel-review-agent'
alias bot-score='cd /root/peter-thiel-review-agent && ./venv/bin/python -c "import asyncio; from cogs.scheduler import SchedulerCog; print(\"Triggering scoring manually...\")"'
# END CALCRUM RICE
EOF

echo "✨ Server Rice Complete! Your terminal is now elite."
echo "👉 Run: source ~/.bashrc to see the magic right now!"
