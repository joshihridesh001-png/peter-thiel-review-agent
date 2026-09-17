#!/usr/bin/env bash
# Quick automated deploy script for Google Cloud Compute Engine (e2-micro Always Free VM)
set -e

echo "=== 🚀 Installing dependencies on Google Cloud VM ==="
sudo apt-get update -y
sudo apt-get install -y git python3 python3-pip python3-venv

APP_DIR="$HOME/peter-thiel-review-agent"

if [ -d "$APP_DIR" ]; then
    echo "Updating existing repository..."
    cd "$APP_DIR"
    git pull origin main
else
    echo "Cloning repository..."
    git clone https://github.com/joshihridesh001-png/peter-thiel-review-agent.git "$APP_DIR"
    cd "$APP_DIR"
fi

echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if not exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env from .env.example. Please add your DISCORD_BOT_TOKEN and GEMINI_API_KEY."
    fi
fi

echo "Registering systemd 24/7 background service..."
sudo bash -c "cat << 'EOF' > /etc/systemd/system/peter-thiel.service
[Unit]
Description=Peter Thiel Review Agent (Krishna Engineering OS)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable peter-thiel.service
sudo systemctl restart peter-thiel.service

echo "=== ✅ Peter Thiel Agent is now running 24/7 on Google Cloud! ==="
sudo systemctl status peter-thiel.service --no-pager
