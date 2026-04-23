#!/usr/bin/env bash
set -e

SERVICE_NAME="powertracker"
SERVICE_FILE="/etc/systemd/system/powertracker.service"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CURRENT_USER="$(whoami)"
PYTHON="$(which python3)"

echo "Installing dependencies..."
"${PYTHON}" -m pip install -e "$REPO_DIR" -q

echo "Writing systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Power Tracker Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${REPO_DIR}/.env
ExecStart=${PYTHON} -m power_tracker.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Done. Status:"
sudo systemctl status "$SERVICE_NAME" --no-pager
