# PiWeather

A Raspberry Pi Zero 2 W weather display for the **Waveshare 1.54" LCD** (240×240 ST7789 SPI).

Shows today's and tomorrow's weather — icon, high/low temperature, description, and date — alternating every 10 seconds (configurable). Weather data from [Open-Meteo](https://open-meteo.com/) (free, no API key).

---

## Hardware

| Component | Details |
|-----------|---------|
| Raspberry Pi | Zero 2 W (Raspberry Pi OS Bookworm Lite, 64-bit) |
| Display | Waveshare 1.54" LCD Module — 240×240 ST7789 SPI |

---

## Step 1 — Flash the Pi

1. Download and install **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)** on your computer.
2. Click **Choose Device** → `Raspberry Pi Zero 2 W`.
3. Click **Choose OS** → `Raspberry Pi OS (other)` → **`Raspberry Pi OS Lite (64-bit)`**.
4. Click **Choose Storage** → select your microSD card.
5. Click **Next**, then **Edit Settings** in the OS customisation dialog:
   - Set a **hostname** (e.g. `piweather`)
   - Set a **username and password**
   - Configure your **Wi-Fi** (SSID + password + country)
   - Under **Services**, enable **SSH** → `Use password authentication`
6. Click **Save** → **Yes** → let it flash and verify.
7. Insert the card into the Pi and power it on.

> The Pi may take 60–90 seconds on first boot to resize the filesystem.

---

## Step 2 — Connect Remotely (Raspberry Pi Connect)

[Raspberry Pi Connect](https://connect.raspberrypi.com/) gives you a browser-based remote shell without needing to be on the same network — useful if your Pi is headless and you're setting it up away from your router.

### On the Pi (SSH in first, or use a keyboard + monitor):

```bash
# Install the Connect agent
sudo apt update && sudo apt install -y rpi-connect

# Start and enable it
sudo systemctl enable --now rpi-connect

# Sign in — this prints a URL to open in your browser
rpi-connect signin
```

Open the printed URL in your browser, sign in with your **Raspberry Pi ID** (create a free account at [id.raspberrypi.com](https://id.raspberrypi.com)), and authorise the device.

### Access your Pi from anywhere:

Go to **[connect.raspberrypi.com](https://connect.raspberrypi.com)**, select your Pi, and open a **Remote Shell** — a full terminal in the browser. No VPN, no port forwarding needed.

> Connect only provides shell access on Raspberry Pi OS Lite. Screen sharing requires the full Desktop image.

---

## Step 3 — Wire the Display

Solder the 2×20 pin header onto the Pi Zero 2 W before connecting the display.

| Display Pin | Pi GPIO | Physical Pin |
|-------------|---------|-------------|
| VCC | 5V | Pin 2 |
| GND | GND | Pin 6 |
| DIN (MOSI) | GPIO 10 | Pin 19 (SPI0 MOSI) |
| CLK (SCLK) | GPIO 11 | Pin 23 (SPI0 CLK) |
| CS | GPIO 8 | Pin 24 (CE0) |
| DC | GPIO 25 | Pin 22 |
| RST | GPIO 27 | Pin 13 |
| BL | GPIO 18 | Pin 12 |

---

## Step 4 — Install PiWeather

Run this single command on the Pi (as root):

```bash
curl -fsSL https://raw.githubusercontent.com/OktaneZA/piweather/master/install.sh | sudo bash
```

The installer will:
1. Enable SPI
2. Create system user `piweather`
3. Clone this repository to `/opt/piweather` (icons are bundled — no separate download)
4. Set up a Python venv and install dependencies
5. Copy DejaVu fonts from the OS
6. Prompt for location, temperature unit, flip interval, and portal password
7. Assign a random port above 4000 for the web portal
8. Start the `piweather` systemd service

At the end, the installer prints the web portal URL and port.

---

## Configuration

After installation, open the web portal shown at the end of the install output:

```
http://<pi-ip>:<port>
```

**Portal access:**
- **No password set** — accessible from localhost only. Use an SSH tunnel for remote access:
  ```bash
  ssh -L 8080:localhost:<port> pi@<pi-ip>
  # then open http://localhost:8080 on your computer
  ```
- **Password set** — HTTP Basic Auth required from all clients (username: `admin`). Password stored as PBKDF2-HMAC-SHA256.

**Configurable settings:**

| Setting | Default | Description |
|---|---|---|
| Latitude / Longitude | *(auto)* | Leave blank to auto-detect from IP |
| Temperature unit | `celsius` | `celsius` or `fahrenheit` |
| Flip interval | `10` s | Seconds to show today before flipping to tomorrow |
| Weather refresh | `30` min | How often to call the Open-Meteo API |
| Display brightness | `100` | 0–255 |
| Display rotation | `0°` | 0, 90, 180, or 270 degrees |

---

## Screen Layout

```
┌──────────────────────────┐
│  TODAY          14:32    │
│                          │
│      [WEATHER ICON]      │
│        100×100 px        │
│                          │
│      Partly Cloudy       │
│                          │
│   ▲ 24°C    ▼ 18°C      │
│                          │
│   Monday 16 March 2026   │
│          ● ○             │
└──────────────────────────┘
```

The two dots at the bottom indicate the current day (● = active).

---

## Updating

```bash
sudo bash /opt/piweather/update.sh
```

---

## Post-Install Validation

```bash
sudo /opt/piweather/.venv/bin/python /opt/piweather/validate.py
```

Expected: 5 checks, all `[ PASS ]`.

---

## Logs

```bash
journalctl -u piweather -f
```

---

## Running Tests (dev)

Tests mock all Pi hardware — safe to run on Windows/macOS/Linux.

```bash
pip install -r requirements-dev.txt
pytest --tb=short -q
```

---

## Credits

Weather data from [Open-Meteo](https://open-meteo.com/) (WMO weather codes).
