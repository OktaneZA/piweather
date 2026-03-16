#!/usr/bin/env python3
"""Render sample PiWeather screens to PNG files.

Usage:
    python preview.py [output_dir]

Downloads a small set of icons from InkyPi if not already present,
then renders today, tomorrow, and error screens at 240×240 px.
Saves them to output_dir (default: preview/).
"""

import os
import sys
import urllib.request
from datetime import datetime

# Add src to path
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from PIL import Image
import display as display_module

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "preview")
os.makedirs(OUT_DIR, exist_ok=True)

ICON_DIR = os.path.join(_SRC, "icons")
os.makedirs(ICON_DIR, exist_ok=True)

ICON_BASE = "https://raw.githubusercontent.com/fatihak/InkyPi/main/src/plugins/weather/icons"
PREVIEW_ICONS = ["01d", "01n", "02d", "10d", "10n", "11d", "13d", "09d", "50d", "04d"]

print("Fetching icons …")
for name in PREVIEW_ICONS:
    path = os.path.join(ICON_DIR, f"{name}.png")
    if os.path.isfile(path):
        print(f"  {name}.png already present")
    else:
        url = f"{ICON_BASE}/{name}.png"
        try:
            urllib.request.urlretrieve(url, path)
            print(f"  Downloaded {name}.png")
        except Exception as exc:
            print(f"  WARNING: could not fetch {name}.png — {exc}")

# ------------------------------------------------------------------
# Sample data
# ------------------------------------------------------------------

SAMPLE_TODAY = {
    "icon": "02d",
    "description": "Partly Cloudy",
    "high": 24.0,
    "low": 18.0,
    "unit_symbol": "°C",
    "date": "2026-03-16",
    "sunrise": "2026-03-16T06:21",
    "sunset": "2026-03-16T18:45",
    "wmo_code": 2,
}

SAMPLE_TOMORROW = {
    "icon": "10d",
    "description": "Moderate Rain",
    "high": 19.5,
    "low": 14.2,
    "unit_symbol": "°C",
    "date": "2026-03-17",
    "sunrise": "2026-03-17T06:20",
    "sunset": "2026-03-17T18:46",
    "wmo_code": 63,
}

SAMPLE_FAHRENHEIT = {
    "icon": "01d",
    "description": "Clear Sky",
    "high": 75.2,
    "low": 64.4,
    "unit_symbol": "°F",
    "date": "2026-03-16",
    "sunrise": "2026-03-16T06:21",
    "sunset": "2026-03-16T18:45",
    "wmo_code": 0,
}

SAMPLE_SNOW = {
    "icon": "13d",
    "description": "Heavy Snow",
    "high": -2.0,
    "low": -8.0,
    "unit_symbol": "°C",
    "date": "2026-03-16",
    "sunrise": "2026-03-16T07:10",
    "sunset": "2026-03-16T17:30",
    "wmo_code": 75,
}

SAMPLE_STORM = {
    "icon": "11d",
    "description": "Thunderstorm",
    "high": 28.0,
    "low": 22.0,
    "unit_symbol": "°C",
    "date": "2026-03-17",
    "sunrise": "2026-03-17T06:19",
    "sunset": "2026-03-17T18:47",
    "wmo_code": 95,
}

SAMPLE_NIGHT = {
    "icon": "01n",
    "description": "Clear Sky",
    "high": 22.0,
    "low": 16.0,
    "unit_symbol": "°C",
    "date": "2026-03-16",
    "sunrise": "2026-03-16T06:21",
    "sunset": "2026-03-16T18:45",
    "wmo_code": 0,
}

# ------------------------------------------------------------------
# Render screens
# ------------------------------------------------------------------

SCREENS = [
    ("today_cloudy",      SAMPLE_TODAY,       0, datetime(2026, 3, 16, 14, 32)),
    ("tomorrow_rain",     SAMPLE_TOMORROW,    1, datetime(2026, 3, 16, 14, 32)),
    ("today_fahrenheit",  SAMPLE_FAHRENHEIT,  0, datetime(2026, 3, 16,  9, 15)),
    ("today_snow",        SAMPLE_SNOW,        0, datetime(2026, 3, 16, 11,  0)),
    ("tomorrow_storm",    SAMPLE_STORM,       1, datetime(2026, 3, 16, 14, 32)),
    ("today_night",       SAMPLE_NIGHT,       0, datetime(2026, 3, 16, 22, 45)),
]

print("\nRendering screens …")
for filename, data, day, now in SCREENS:
    img = Image.new("RGB", (240, 240), (8, 12, 24))
    display_module.draw_weather(img, data, day=day, now=now)
    # Scale up 3× for easier viewing
    big = img.resize((720, 720), Image.NEAREST)
    out_path = os.path.join(OUT_DIR, f"{filename}.png")
    big.save(out_path)
    print(f"  Saved {out_path}")

# Error / loading screen
img = Image.new("RGB", (240, 240), (8, 12, 24))
display_module.draw_error(img, "Fetching weather...")
big = img.resize((720, 720), Image.NEAREST)
out_path = os.path.join(OUT_DIR, "loading.png")
big.save(out_path)
print(f"  Saved {out_path}")

print(f"\nDone — {len(SCREENS) + 1} screens saved to {OUT_DIR}/")
