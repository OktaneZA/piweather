# PiWeather

A Raspberry Pi Zero 2 W weather display for the **Waveshare 1.54" LCD** (240×240 ST7789 SPI).

Shows today's and tomorrow's weather — icon, high/low temperature, description, and date — alternating every 10 seconds (configurable). Weather data from [Open-Meteo](https://open-meteo.com/) (free, no API key). Icons from [InkyPi](https://github.com/fatihak/InkyPi).

---

## Hardware

| Component | Details |
|-----------|---------|
| Raspberry Pi | Zero 2 W (Raspberry Pi OS Bookworm Lite, 64-bit) |
| Display | Waveshare 1.54" LCD Module — 240×240 ST7789 SPI |

---

## Display Wiring (GPIO)

| Display Pin | Pi GPIO | Physical Pin |
|-------------|---------|-------------|
| VCC | 5V | Pin 2 |
| GND | GND | Pin 6 |
| DIN (MOSI) | GPIO 10 | Pin 19 (SPI0 MOSI) |
| CLK (SCLK) | GPIO 11 | Pin 23 (SPI0 CLK) |
| CS | GPIO 8 | Pin 24 (CE0) |
| DC | GPIO 25 | Pin 22 |
| RST | GPIO 27 | Pin 13 |
| BL | GPIO 24 | Pin 18 |

---

## Quick Install

```bash
# On your Pi Zero 2 W, as root:
sudo bash install.sh
```

The installer will:
1. Enable SPI
2. Create system user `piweather`
3. Set up Python venv and install dependencies
4. Download InkyPi weather icons
5. Prompt for location (optional — auto-detected from IP), temperature unit, flip interval, and portal password
6. Assign a random port above 4000 for the web portal
7. Start the systemd service

---

## Configuration

After installation, open the web portal shown at the end of the install output:

```
http://<pi-ip>:<port>
```

**Portal access:**
- **No password set** — accessible from localhost only (`127.0.0.1` / `::1`). Use an SSH tunnel for remote access: `ssh -L 8080:localhost:<port> pi@<pi-ip>`.
- **Password set** — HTTP Basic Auth required from all clients (username: `admin`). Password stored as a PBKDF2-HMAC-SHA256 hash.

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

Weather icons from [InkyPi](https://github.com/fatihak/InkyPi) by [@fatihak](https://github.com/fatihak).
Weather data from [Open-Meteo](https://open-meteo.com/) (WMO weather codes).
