#!/usr/bin/env bash
set -e

SERVICE_NAME="powertracker"
SERVICE_FILE="powertracker.service"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing dependencies..."
pip install -r <(pip-compile pyproject.toml -q 2>/dev/null || echo "psycopg2-binary python-dotenv flask") 2>/dev/null \
  || pip install psycopg2-binary python-dotenv flask

echo "Installing systemd service..."
sudo cp "$INSTALL_DIR/$SERVICE_FILE" "/etc/systemd/system/$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Done. Status:"
sudo systemctl status "$SERVICE_NAME" --no-pager
