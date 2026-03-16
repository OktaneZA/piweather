# PiWeather — Requirements

## Architecture

| ID | Requirement |
|----|-------------|
| ARCH-01 | Three-thread model: render thread (main), weather fetch background thread, web portal thread |
| ARCH-02 | All shared weather state protected by `threading.Lock`; render thread never writes; fetch thread never calls display functions |
| ARCH-03 | `_display_epoch` counter incremented on every state change and every day flip; render loop only redraws when epoch changes |
| ARCH-04 | SIGTERM and SIGINT set `_shutdown_event`; all threads check it and exit cleanly |
| ARCH-05 | Config reload without process restart: `_restart_event` set by portal triggers weather re-fetch with new settings |

## Display

| ID | Requirement |
|----|-------------|
| DISP-01 | 240×240 ST7789 SPI display at 250 ms refresh rate (~4 Hz) |
| DISP-02 | Layout: label row (TODAY/TOMORROW + time), 100×100 weather icon centred, description text, Hi/Low temperatures, full date, day indicator dots |
| DISP-03 | High temperature shown in warm orange `(255, 160, 0)`; Low temperature in cool blue `(80, 160, 255)` |
| DISP-04 | Day indicator: two dots at bottom — active dot white, inactive dot dark grey |
| DISP-05 | Background colour `(8, 12, 24)`; text white `(255, 255, 255)` |
| DISP-06 | Weather icons are 100×100 px PNG files loaded from `src/icons/`; fallback placeholder drawn if icon file is missing |
| DISP-07 | Error/loading screen shown until first successful weather fetch |

## Weather

| ID | Requirement |
|----|-------------|
| WX-01 | Weather data fetched from Open-Meteo API (free, no API key required) |
| WX-02 | Two-day forecast: today (index 0) and tomorrow (index 1) |
| WX-03 | Data per day: WMO weather code, high temp, low temp, sunrise, sunset, date |
| WX-04 | WMO codes mapped to InkyPi PNG icon filenames; day/night suffix applied for today based on current time vs sunrise/sunset |
| WX-05 | Tomorrow's icon always uses the daytime (`d`) variant |
| WX-06 | Temperature unit configurable: `celsius` (default) or `fahrenheit` |
| WX-07 | Weather refreshed every `weather_refresh_min` minutes (default 30); also refreshed immediately on config save |
| WX-08 | Location auto-detected via `ipinfo.io` IP geolocation; overridable with explicit `lat`/`lon` in config |

## Security

| ID | Requirement |
|----|-------------|
| SEC-01 | Web portal auth: empty `portal_password` → localhost (`127.0.0.1`/`::1`) allowed without credentials; all other origins receive HTTP 403 |
| SEC-02 | Web portal auth: non-empty `portal_password` → HTTP Basic Auth required from all origins; incorrect credentials return HTTP 401 |
| SEC-03 | `portal_password` stored as `pbkdf2:sha256:260000:<salt_hex>:<base64_hash>`; legacy plaintext detected via absence of `pbkdf2:` prefix (migration path) |
| SEC-04 | Config file permissions `640` (root:piweather); never world-readable |
| SEC-05 | Service runs as non-root system user `piweather` |
| SEC-06 | Config written by Python `json.dumps` in installer — no shell heredoc variable interpolation |
| SEC-07 | Password passed to Python via stdin in installer (not `sys.argv`) to avoid `/proc/cmdline` exposure |

## Configuration

| ID | Requirement |
|----|-------------|
| CFG-01 | Config stored as JSON at `/etc/piweather/config.json` |
| CFG-02 | Portal port randomly selected from 4001–65000 at install time; written to config and shown in install summary |
| CFG-03 | All config fields have documented defaults; missing fields filled from defaults on load |
| CFG-04 | Config validated at load time; invalid config raises `ValueError` with actionable message |
| CFG-05 | Config writes are atomic: write to `.tmp`, then `os.replace()` |

## Installation

| ID | Requirement |
|----|-------------|
| INST-01 | `install.sh` is idempotent: re-running on an already-installed system updates code without data loss |
| INST-02 | Installer verifies it is running on a Raspberry Pi before proceeding |
| INST-03 | Installer enables SPI interface via `raspi-config nonint do_spi 0` |
| INST-04 | Installer creates system user `piweather` and adds to `spi` and `gpio` groups |
| INST-05 | Installer downloads InkyPi weather icons to `src/icons/` via `wget` |
| INST-06 | Service managed by systemd; starts on boot after `network-online.target` |
| INST-07 | `validate.py` performs 5 post-install checks: SPI, config, Open-Meteo API, icons, display init |
