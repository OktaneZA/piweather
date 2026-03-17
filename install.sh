#!/usr/bin/env bash
# PiWeather installer — idempotent, must run as root on a Raspberry Pi.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()    { echo -e "\n${CYAN}▶ $*${NC}"; }
confirm() { read -r -p "$1 [y/N] " _ans; [[ "${_ans,,}" == "y" ]]; }

INSTALL_DIR="/opt/piweather"
CONFIG_DIR="/etc/piweather"
CONFIG_FILE="${CONFIG_DIR}/config.json"
SERVICE_FILE="/etc/systemd/system/piweather.service"
SERVICE_USER="piweather"
TARBALL_URL="https://github.com/OktaneZA/piweather/archive/refs/heads/master.tar.gz"

# ------------------------------------------------------------------ #
# Verify Raspberry Pi                                                  #
# ------------------------------------------------------------------ #

step "Checking environment"

[[ "$EUID" -eq 0 ]] || error "This installer must run as root (sudo bash install.sh)"

if [[ ! -f /proc/device-tree/model ]] || ! grep -qi "raspberry" /proc/device-tree/model; then
    error "This installer must run on a Raspberry Pi."
fi
info "Raspberry Pi detected: $(tr -d '\0' < /proc/device-tree/model)"

# ------------------------------------------------------------------ #
# System packages                                                      #
# ------------------------------------------------------------------ #

step "Installing system packages"

apt-get update -qq
for pkg in python3 python3-venv python3-pip python3-spidev python3-rpi.gpio git wget; do
    if dpkg -s "$pkg" &>/dev/null; then
        info "  $pkg already installed"
    else
        info "  Installing $pkg …"
        apt-get install -y -qq "$pkg"
    fi
done

# ------------------------------------------------------------------ #
# Enable SPI                                                           #
# ------------------------------------------------------------------ #

step "Enabling SPI interface"

if raspi-config nonint get_spi | grep -q "0"; then
    info "SPI already enabled"
else
    raspi-config nonint do_spi 0
    info "SPI enabled"
fi

# ------------------------------------------------------------------ #
# Clone / update repo                                                  #
# ------------------------------------------------------------------ #

step "Installing PiWeather to ${INSTALL_DIR}"

info "Downloading latest release …"
TMP_DIR="$(mktemp -d)"
curl -fsSL "${TARBALL_URL}" | tar -xz -C "${TMP_DIR}"
EXTRACTED_DIR="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -1)"
rm -rf "${INSTALL_DIR}"
mv "${EXTRACTED_DIR}" "${INSTALL_DIR}"
rm -rf "${TMP_DIR}"
info "Installed to ${INSTALL_DIR}"

# ------------------------------------------------------------------ #
# Python venv                                                          #
# ------------------------------------------------------------------ #

step "Setting up Python virtual environment"

python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"
info "Dependencies installed"

# ------------------------------------------------------------------ #
# System user                                                          #
# ------------------------------------------------------------------ #

step "Creating system user '${SERVICE_USER}'"

if id -u "${SERVICE_USER}" &>/dev/null; then
    info "User '${SERVICE_USER}' already exists"
else
    useradd --system --no-create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
    info "User '${SERVICE_USER}' created"
fi

for grp in spi gpio; do
    if getent group "$grp" &>/dev/null; then
        usermod -aG "$grp" "${SERVICE_USER}"
        info "  Added to group: $grp"
    else
        warn "  Group $grp not found — skipping"
    fi
done

# ------------------------------------------------------------------ #
# Copy DejaVu fonts (included in Raspberry Pi OS)                     #
# ------------------------------------------------------------------ #

step "Copying fonts"

FONT_DIR="${INSTALL_DIR}/src/fonts"
mkdir -p "${FONT_DIR}"
for font in DejaVuSans.ttf DejaVuSans-Bold.ttf; do
    src_path=$(find /usr/share/fonts -name "$font" 2>/dev/null | head -1)
    if [[ -n "$src_path" ]]; then
        cp "$src_path" "${FONT_DIR}/${font}"
        info "  Copied $font"
    else
        warn "  $font not found — display will use PIL fallback font"
    fi
done

# ------------------------------------------------------------------ #
# Interactive configuration                                            #
# ------------------------------------------------------------------ #

step "Configuring PiWeather"

# Pre-initialise all interactive variables so set -u never fires if read
# receives EOF (which happens when the script is piped via curl | bash).
# All reads explicitly use /dev/tty so they reach the user's terminal
# regardless of how stdin is connected.
LAT=""
LON=""
TEMP_UNIT="celsius"
FLIP_INTERVAL="10"
PORTAL_PASSWORD=""

echo ""
echo "Location (leave both blank to auto-detect from IP):"
read -r -p "Latitude  [blank=auto]: " LAT          </dev/tty || true
read -r -p "Longitude [blank=auto]: " LON          </dev/tty || true
echo ""

read -r -p "Temperature unit (celsius/fahrenheit) [celsius]: " TEMP_UNIT </dev/tty || true
TEMP_UNIT="${TEMP_UNIT:-celsius}"
if [[ "$TEMP_UNIT" != "celsius" && "$TEMP_UNIT" != "fahrenheit" ]]; then
    warn "Invalid unit — defaulting to celsius"
    TEMP_UNIT="celsius"
fi

read -r -p "Flip interval in seconds (today→tomorrow) [10]: " FLIP_INTERVAL </dev/tty || true
FLIP_INTERVAL="${FLIP_INTERVAL:-10}"

echo ""
read -r -s -p "Web portal password (leave blank for localhost-only access): " PORTAL_PASSWORD </dev/tty || true
echo ""

# ------------------------------------------------------------------ #
# Find a free port above 4000                                          #
# ------------------------------------------------------------------ #

step "Finding free port for web portal"

PORTAL_PORT=$(python3 - <<'PYEOF'
import socket, random, sys
for _ in range(100):
    port = random.randint(4001, 65000)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
            print(port)
            sys.exit(0)
    except OSError:
        pass
sys.exit(1)
PYEOF
)
PORTAL_IP=$(hostname -I | awk '{print $1}')
info "Web portal will be available at: http://${PORTAL_IP}:${PORTAL_PORT}"

# ------------------------------------------------------------------ #
# Hash the portal password                                             #
# ------------------------------------------------------------------ #

if [[ -n "${PORTAL_PASSWORD}" ]]; then
    PORTAL_PASSWORD_HASH=$(printf '%s' "${PORTAL_PASSWORD}" | python3 -c "
import hashlib, secrets, base64, sys
pw = sys.stdin.read()
salt = secrets.token_hex(16)
dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 260000)
print(f'pbkdf2:sha256:260000:{salt}:{base64.b64encode(dk).decode()}')
")
else
    PORTAL_PASSWORD_HASH=""
    info "No password set — portal accessible from localhost only"
fi

# ------------------------------------------------------------------ #
# Write config (Python handles JSON encoding to avoid injection)       #
# ------------------------------------------------------------------ #

step "Writing config to ${CONFIG_FILE}"

mkdir -p "${CONFIG_DIR}"

# Use Python to write JSON safely (avoids shell heredoc injection for user-supplied values)
_LAT="${LAT}" _LON="${LON}" _TEMP_UNIT="${TEMP_UNIT}" _FLIP="${FLIP_INTERVAL}" \
_PW_HASH="${PORTAL_PASSWORD_HASH}" _PORT="${PORTAL_PORT}" _CONFIG_FILE="${CONFIG_FILE}" \
python3 - <<'PYEOF'
import json, os
data = {
    "lat": os.environ.get("_LAT", ""),
    "lon": os.environ.get("_LON", ""),
    "temperature_unit": os.environ.get("_TEMP_UNIT", "celsius"),
    "flip_interval_s": int(os.environ.get("_FLIP", "10") or "10"),
    "weather_refresh_min": 30,
    "display_brightness": 100,
    "display_rotation": 0,
    "portal_password": os.environ.get("_PW_HASH", ""),
    "portal_port": int(os.environ.get("_PORT", "8080")),
}
path = os.environ["_CONFIG_FILE"]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"Config written to {path}")
PYEOF

chown root:"${SERVICE_USER}" "${CONFIG_FILE}"
chmod 640 "${CONFIG_FILE}"
info "Config written with permissions 640 (root:${SERVICE_USER})"

# ------------------------------------------------------------------ #
# systemd service                                                      #
# ------------------------------------------------------------------ #

step "Installing systemd service"

cp "${INSTALL_DIR}/systemd/piweather.service" "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable piweather.service
info "Service enabled"

# ------------------------------------------------------------------ #
# Start service                                                        #
# ------------------------------------------------------------------ #

step "Starting PiWeather service"

systemctl restart piweather.service
sleep 2

if systemctl is-active --quiet piweather.service; then
    info "Service started successfully"
else
    warn "Service may not have started yet — check: journalctl -u piweather -n 50"
fi

# ------------------------------------------------------------------ #
# Summary                                                              #
# ------------------------------------------------------------------ #

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  PiWeather installed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Web portal:  ${CYAN}http://${PORTAL_IP}:${PORTAL_PORT}${NC}"
if [[ -n "${PORTAL_PASSWORD}" ]]; then
    echo -e "  Credentials: ${CYAN}admin / <password set during install>${NC}  (stored as PBKDF2 hash)"
else
    echo -e "  Access:      ${CYAN}Localhost only (no password set)${NC}"
fi
echo ""
echo -e "  Logs:        ${CYAN}journalctl -u piweather -f${NC}"
echo -e "  Update:      ${CYAN}sudo bash ${INSTALL_DIR}/update.sh${NC}"
echo ""

if confirm "Run post-install validator now?"; then
    "${INSTALL_DIR}/.venv/bin/python" "${INSTALL_DIR}/validate.py" || true
fi
