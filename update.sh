#!/usr/bin/env bash
# PiWeather updater — re-download latest release and restart service.
set -euo pipefail

INSTALL_DIR="/opt/piweather"
TARBALL_URL="https://github.com/OktaneZA/piweather/archive/refs/heads/master.tar.gz"
VENV_DIR="${INSTALL_DIR}/.venv"

[[ "$EUID" -eq 0 ]] || { echo "Run as root: sudo bash update.sh" >&2; exit 1; }

echo "[INFO] Downloading latest release …"
TMP_DIR="$(mktemp -d)"
curl -fsSL "${TARBALL_URL}" | tar -xz -C "${TMP_DIR}"
EXTRACTED_DIR="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -1)"

# Preserve the venv across the directory replacement
VENV_TMP="$(mktemp -d)"
if [[ -d "${VENV_DIR}" ]]; then
    mv "${VENV_DIR}" "${VENV_TMP}/.venv"
fi

rm -rf "${INSTALL_DIR}"
mv "${EXTRACTED_DIR}" "${INSTALL_DIR}"
rm -rf "${TMP_DIR}"

# Restore venv
if [[ -d "${VENV_TMP}/.venv" ]]; then
    mv "${VENV_TMP}/.venv" "${VENV_DIR}"
fi
rm -rf "${VENV_TMP}"

echo "[INFO] Reinstalling dependencies …"
"${VENV_DIR}/bin/pip" install --quiet --prefer-binary --upgrade -r "${INSTALL_DIR}/requirements.txt"

echo "[INFO] Restarting service …"
systemctl restart piweather.service
sleep 2

if systemctl is-active --quiet piweather.service; then
    echo "[INFO] Service restarted successfully."
else
    echo "[WARN] Service may not have started — check: journalctl -u piweather -n 50"
fi
