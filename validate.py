#!/usr/bin/env python3
"""Post-install validator for PiWeather.

Performs 5 checks and prints [ PASS ] / [ FAIL ] per check.
Run as: sudo /opt/piweather/.venv/bin/python /opt/piweather/validate.py
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

PASS = "\033[32m[ PASS ]\033[0m"
FAIL = "\033[31m[ FAIL ]\033[0m"

results: list[bool] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    tag = PASS if passed else FAIL
    line = f"  {tag}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    results.append(passed)


print("\nPiWeather — post-install validation\n")

# 1. SPI available
try:
    import spidev
    s = spidev.SpiDev()
    s.open(0, 0)
    s.close()
    check("SPI interface accessible", True)
except Exception as exc:
    check("SPI interface accessible", False, str(exc))

# 2. Config file exists and loads
try:
    import config as cfg_module
    cfg = cfg_module.load_config()
    check("Config file valid", True, f"port={cfg['portal_port']}")
except Exception as exc:
    check("Config file valid", False, str(exc))

# 3. Weather API reachable
try:
    import requests
    resp = requests.get("https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&daily=weathercode&forecast_days=1", timeout=8)
    resp.raise_for_status()
    check("Open-Meteo API reachable", True)
except Exception as exc:
    check("Open-Meteo API reachable", False, str(exc))

# 4. Icon files present
ICON_DIR = os.path.join(_SRC, "icons")
required_icons = ["01d.png", "01n.png", "10d.png", "11d.png"]
missing = [i for i in required_icons if not os.path.isfile(os.path.join(ICON_DIR, i))]
check("Weather icons present", not missing,
      "missing: " + ", ".join(missing) if missing else f"{len(os.listdir(ICON_DIR))} icons found")

# 5. Display init (hardware only)
try:
    from display import ST7789
    disp = ST7789(brightness=50)
    disp.close()
    check("Display (ST7789) initialised", True)
except Exception as exc:
    check("Display (ST7789) initialised", False, str(exc))

print()
passed = sum(results)
total = len(results)
print(f"  {passed}/{total} checks passed\n")
sys.exit(0 if passed == total else 1)
