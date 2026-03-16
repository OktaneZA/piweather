#!/usr/bin/env bash
# PiWeather updater — pull latest code and restart service.
set -euo pipefail

INSTALL_DIR="/opt/piweather"

[[ "$EUID" -eq 0 ]] || { echo "Run as root: sudo bash update.sh" >&2; exit 1; }

echo "Pulling latest code …"
git -C "${INSTALL_DIR}" pull --quiet
echo "Updated to $(git -C "${INSTALL_DIR}" rev-parse --short HEAD)"

echo "Reinstalling dependencies …"
"${INSTALL_DIR}/.venv/bin/pip" install --quiet --upgrade -r "${INSTALL_DIR}/requirements.txt"

echo "Restarting service …"
systemctl restart piweather.service
sleep 2

if systemctl is-active --quiet piweather.service; then
    echo "Service restarted successfully"
else
    echo "Service may not have started — check: journalctl -u piweather -n 50"
fi
