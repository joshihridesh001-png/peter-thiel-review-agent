#!/usr/bin/env bash
# ==============================================================================
# 🕶️ CALCRUM VPS RICE SCRIPT • CYBERPUNK TERMINAL SUITE
# Transforms plain Ubuntu VPS into a high-performance, neon aesthetic powerhouse.
# Features:
# - Tokyo Night Starship prompt
# - Cyberpunk SSH Login Art (Cyber Shades + ANSI Shadow CALCRUM + Live Gauges)
# - Futuristic Power-Off & Reboot Shutdown Screens
# - Clean SSH Logout Banner
# - Modern CLI toolkit (btop, eza, bat, fastfetch)
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

mkdir -p /root/.banner

# 4. Install Brand-Accurate Calcrum Terminal Engine (calcrum.com design)
echo "🎨 Installing Calcrum Brand Terminal Engine..."
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f "$REPO_DIR/scripts/terminal/calcrum_term.py" ]; then
    chmod +x "$REPO_DIR/scripts/terminal/calcrum_term.py"
    cp -f "$REPO_DIR/scripts/terminal/calcrum_term.py" /usr/local/bin/calcrum
    chmod +x /usr/local/bin/calcrum
elif [ -f "/root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py" ]; then
    chmod +x "/root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py"
    cp -f "/root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py" /usr/local/bin/calcrum
    chmod +x /usr/local/bin/calcrum
fi

# 5. Create MOTD Banner Hook
cat << 'EOF' > /root/.banner/motd.sh
#!/usr/bin/env bash
if command -v calcrum &> /dev/null; then
    exec calcrum login
elif [ -f /usr/local/bin/calcrum ]; then
    exec /usr/local/bin/calcrum login
elif [ -f /root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py ]; then
    exec python3 /root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py login
fi
EOF
chmod +x /root/.banner/motd.sh

# 6. Create Shutdown & Reboot Screen Hook
cat << 'EOF' > /root/.banner/shutdown_screen.sh
#!/usr/bin/env bash
ACTION="poweroff"
if [[ "$1" == "reboot" ]] || [[ "$0" == *"reboot"* ]]; then
    ACTION="reboot"
fi

if command -v calcrum &> /dev/null; then
    exec calcrum "$ACTION"
elif [ -f /usr/local/bin/calcrum ]; then
    exec /usr/local/bin/calcrum "$ACTION"
elif [ -f /root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py ]; then
    exec python3 /root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py "$ACTION"
else
    /sbin/"$ACTION"
fi
EOF
chmod +x /root/.banner/shutdown_screen.sh

# 7. Create SSH Logout Banner Hook
cat << 'EOF' > /root/.banner/logout.sh
#!/usr/bin/env bash
if command -v calcrum &> /dev/null; then
    exec calcrum logout
elif [ -f /usr/local/bin/calcrum ]; then
    exec /usr/local/bin/calcrum logout
elif [ -f /root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py ]; then
    exec python3 /root/peter-thiel-review-agent/scripts/terminal/calcrum_term.py logout
fi
EOF
chmod +x /root/.banner/logout.sh

# 7. Configure ~/.bashrc and ~/.bash_logout Hooks
echo "⚡ Wiring hooks into ~/.bashrc and ~/.bash_logout..."

# Configure ~/.bash_logout
mkdir -p /root
cat << 'EOF' > /root/.bash_logout
# Show custom Calcrum logout screen
if [ -x /root/.banner/logout.sh ]; then
    /root/.banner/logout.sh
fi
EOF

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

# Calcrum Brand Controls
alias motd='/root/.banner/motd.sh'
alias shutdown='/root/.banner/shutdown_screen.sh shutdown'
alias poweroff='/root/.banner/shutdown_screen.sh shutdown'
alias reboot='/root/.banner/shutdown_screen.sh reboot'
# END CALCRUM RICE
EOF

echo "✨ Server Rice Complete! SSH Login, Logout, and Shutdown art is armed."
echo "👉 Run: source ~/.bashrc to see the new login screen right now!"
