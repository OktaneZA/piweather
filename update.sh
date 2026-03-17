#!/usr/bin/env bash
# PiWeather updater — re-download latest release and restart service.
set -euo pipefail

INSTALL_DIR="/opt/piweather"
TARBALL_URL="https://github.com/OktaneZA/piweather/archive/refs/heads/master.tar.gz"

[[ "$EUID" -eq 0 ]] || { echo "Run as root: sudo bash update.sh" >&2; exit 1; }

echo "[INFO] Downloading latest release …"
TMP_DIR="$(mktemp -d)"
curl -fsSL "${TARBALL_URL}" | tar -xz -C "${TMP_DIR}"
EXTRACTED_DIR="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -1)"
rm -rf "${INSTALL_DIR}"
mv "${EXTRACTED_DIR}" "${INSTALL_DIR}"
rm -rf "${TMP_DIR}"

echo "[INFO] Reinstalling dependencies …"
"${INSTALL_DIR}/.venv/bin/pip" install --quiet --upgrade -r "${INSTALL_DIR}/requirements.txt"

echo "[INFO] Restarting service …"
systemctl restart piweather.service
sleep 2

if systemctl is-active --quiet piweather.service; then
    echo "[INFO] Service restarted successfully."
else
    echo "[WARN] Service may not have started — check: journalctl -u piweather -n 50"
fi
