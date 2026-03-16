# PiWeather — Claude Instructions

## What This Project Is

A Raspberry Pi Zero 2 W weather display that shows today's and tomorrow's weather on a Waveshare 1.54" LCD (240×240 ST7789 SPI). Weather data from Open-Meteo (free, no API key). Includes a Flask web config portal.

## Repository Structure

```
/
├── CLAUDE.md                   ← You are here
├── REQUIREMENTS.md             ← Canonical requirements (read before coding)
├── README.md
│
├── src/
│   ├── main.py                 ← Entry point: threads, render loop, SIGTERM handler
│   ├── weather.py              ← Open-Meteo fetch, WMO→icon mapping, IP geolocation
│   ├── display.py              ← ST7789 rendering via PIL
│   ├── config.py               ← Config load/save/validate (JSON-based)
│   ├── portal.py               ← Flask web config portal
│   ├── icons/                  ← PNG weather icons (bundled in the repository)
│   ├── fonts/                  ← TTF fonts (DejaVuSans, DejaVuSans-Bold)
│   └── templates/
│       └── index.html
│
├── tests/
│   ├── test_config.py
│   ├── test_weather.py
│   └── test_display.py
│
├── systemd/
│   └── piweather.service
│
├── validate.py
├── install.sh
├── update.sh
├── requirements.txt
└── requirements-dev.txt
```

## Requirements First

**Read `REQUIREMENTS.md` before making any changes.** Requirement IDs (e.g. `WX-04`, `SEC-03`) are referenced in code comments.

## Python Conventions

- Python 3.9+ compatible
- Type hints on all public functions
- Docstrings on all public functions
- `logging` module for all output — never `print()` in production code
- Log levels: `DEBUG` render detail, `INFO` connections/state changes, `WARNING` recoverable errors, `ERROR` failures
- Line length: 100 characters max

## Threading Model

- **Three threads**: main render + weather fetch + Flask portal
- **Shared state**: `_weather_state`, `_display_epoch` protected by `threading.Lock`
- Render thread never writes shared state
- Fetch thread never calls display functions
- SIGTERM/SIGINT sets `_shutdown_event` (ARCH-04)
- `_restart_event` set by portal triggers weather re-fetch (ARCH-05)

## Security — Do Not

- **NEVER** log `portal_password` — not in errors, not in debug
- **NEVER** run the service as root (SEC-05)
- **NEVER** use `eval()`, `exec()`, `os.system()`, or `subprocess` with config-derived strings
- **NEVER** use `verify=False` on any `requests` call

## Display Notes

- ST7789: same GPIO as BambuHelper (DC=25, RST=27, BL=24, CS=8, MOSI=10, CLK=11)
- All rendering into a PIL `Image.new("RGB", (240, 240))`, then pushed via `display.show()`
- Icons: RGBA PNG composited onto dark background before pasting onto RGB image
- Fonts: DejaVuSans from `src/fonts/`; PIL fallback if not found

## Weather Icons

Icons are PNG files bundled in `src/icons/`, named by weather event:
e.g. `clear-sky-day.png`, `rain-night.png`, `thunderstorm-day.png`.

WMO code → icon mapping is in `weather.py:_WMO_TO_ICON`.
Each entry maps to a `(day_icon, night_icon)` tuple; `night_icon` is `None` when no night variant exists.

## How to Run Tests

```bash
pip install -r requirements-dev.txt
pytest --tb=short -q
```

All tests mock spidev, RPi.GPIO, and ST7789 — safe on Windows/macOS/Linux.

## How to Install (on Pi, as root)

```bash
sudo bash install.sh
```

## How to View Logs

```bash
journalctl -u piweather -f
```

## Web Config Portal

```
http://<pi-ip>:<port>   ← port randomly assigned at install, shown in install output
# No password = localhost only
# Password set = admin / <your-password> (PBKDF2 hashed)
```

## Current Status

| Component | Status |
|---|---|
| REQUIREMENTS.md | Complete |
| src/config.py | Complete |
| src/weather.py | Complete |
| src/display.py | Complete |
| src/portal.py | Complete |
| src/main.py | Complete |
| tests/ | Complete |
| validate.py | Complete |
| install.sh | Complete |
| systemd unit | Complete |
