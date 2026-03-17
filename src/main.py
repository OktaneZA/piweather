"""PiWeather — main entry point.

Starts three threads:
  1. Main / render thread  — 250 ms display loop (this thread)
  2. Weather fetch thread  — periodic Open-Meteo API calls
  3. Flask portal thread   — web config interface

Shared state is protected by threading.Lock.
SIGTERM / SIGINT sets _shutdown_event; all threads exit cleanly.
Config reload without restart: _restart_event triggers a weather re-fetch.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from typing import Any

# Add src directory to path when running directly
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import config as cfg_module
import weather as weather_module
from display import ST7789, draw_weather, draw_error
from portal import create_app

# ------------------------------------------------------------------ #
# Logging setup                                                        #
# ------------------------------------------------------------------ #

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "").upper() == "TRUE" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Shared state                                                         #
# ------------------------------------------------------------------ #

_lock = threading.Lock()

# Weather state: {"today": {...}, "tomorrow": {...}, "fetched_at": "..."}
_weather_state: dict[str, Any] = {}

# Epoch counter: incremented when weather state changes
_display_epoch: list[int] = [0]

_shutdown_event = threading.Event()
_restart_event = threading.Event()

# ------------------------------------------------------------------ #
# Signal handler                                                       #
# ------------------------------------------------------------------ #

def _handle_signal(signum: int, frame: Any) -> None:  # type: ignore[type-arg]
    """Set shutdown event on SIGTERM or SIGINT."""
    logger.info("Signal %d received — shutting down", signum)
    _shutdown_event.set()


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# ------------------------------------------------------------------ #
# Weather fetch thread                                                 #
# ------------------------------------------------------------------ #

def _weather_thread_func(config_path: str) -> None:
    """Periodically fetch weather data and update shared state."""
    while not _shutdown_event.is_set():
        if _restart_event.is_set():
            _restart_event.clear()
            logger.info("Restart event — reloading config and re-fetching weather")

        try:
            config = cfg_module.load_config(config_path)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Cannot load config: %s — retry in 30s", exc)
            _shutdown_event.wait(timeout=30)
            continue

        try:
            lat, lon = weather_module.get_location(config)
            state = weather_module.fetch_weather(
                lat, lon,
                unit=config.get("temperature_unit", "celsius"),
            )
            with _lock:
                _weather_state.clear()
                _weather_state.update(state)
                _display_epoch[0] += 1
            logger.info("Weather state updated")
        except Exception as exc:  # noqa: BLE001 — must not crash thread
            logger.error("Weather fetch failed: %s", exc)

        # Wait for refresh interval or restart event
        refresh_s = config.get("weather_refresh_min", 30) * 60
        _restart_event.wait(timeout=refresh_s)
        _restart_event.clear()

    logger.info("Weather thread exiting")


# ------------------------------------------------------------------ #
# Portal thread                                                        #
# ------------------------------------------------------------------ #

def _portal_thread_func(config_path: str) -> None:
    """Run Flask portal in a daemon thread."""
    try:
        config = cfg_module.load_config(config_path)
        port = config.get("portal_port", 8080)
    except Exception:  # noqa: BLE001
        port = 8080

    app = create_app(
        config_path=config_path,
        shared_state=_weather_state,
        lock=_lock,
        restart_event=_restart_event,
    )

    logger.info("Web portal starting on port %d", port)
    try:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("Portal crashed: %s", exc, exc_info=True)


# ------------------------------------------------------------------ #
# Render loop                                                          #
# ------------------------------------------------------------------ #

_RENDER_INTERVAL_S = 0.250   # 250 ms ≈ 4 Hz


def _render_loop(config_path: str, display: ST7789) -> None:
    """Main render loop — reads shared state, drives display."""
    from PIL import Image

    image = Image.new("RGB", (240, 240), (8, 12, 24))

    prev_epoch = -1
    prev_day = -1
    current_day = 0      # 0 = today, 1 = tomorrow
    last_flip = time.monotonic()

    config: dict[str, Any] = {}
    try:
        config = cfg_module.load_config(config_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Config not available at render start: %s", exc)

    while not _shutdown_event.is_set():
        loop_start = time.monotonic()

        # Reload config on restart
        if _restart_event.is_set():
            try:
                config = cfg_module.load_config(config_path)
            except Exception:  # noqa: BLE001
                pass

        flip_interval = config.get("flip_interval_s", 10)

        # Flip day index on timer
        if time.monotonic() - last_flip >= flip_interval:
            current_day = 1 - current_day
            last_flip = time.monotonic()
            with _lock:
                _display_epoch[0] += 1  # force redraw on flip

        with _lock:
            epoch = _display_epoch[0]
            state_snap = dict(_weather_state)

        # Redraw if epoch changed or day changed
        if epoch != prev_epoch or current_day != prev_day:
            now = datetime.now()

            if not state_snap:
                # No weather data yet — show loading screen
                draw_error(image, "Fetching weather...")
            else:
                day_key = "today" if current_day == 0 else "tomorrow"
                day_data = state_snap.get(day_key, {})
                if day_data:
                    draw_weather(image, day_data, current_day, now)
                else:
                    draw_error(image, "Weather unavailable")

            try:
                display.show(image)
                logger.info("Display updated (epoch=%d day=%d)", epoch, current_day)
            except Exception as exc:  # noqa: BLE001
                logger.error("Display show() failed: %s", exc, exc_info=True)
            prev_epoch = epoch
            prev_day = current_day

        elapsed = time.monotonic() - loop_start
        _shutdown_event.wait(timeout=max(0.0, _RENDER_INTERVAL_S - elapsed))

    logger.info("Render loop exiting")


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main() -> None:
    """Initialise hardware and start threads."""
    config_path = os.environ.get("PIWEATHER_CONFIG", cfg_module.DEFAULT_CONFIG_PATH)
    logger.info("PiWeather starting (config=%s)", config_path)

    try:
        config = cfg_module.load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Config error: %s", exc)
        sys.exit(1)

    try:
        display = ST7789(brightness=config.get("display_brightness", 100))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialise display: %s", exc)
        sys.exit(1)

    weather_thread = threading.Thread(
        target=_weather_thread_func,
        args=(config_path,),
        daemon=True,
        name="weather",
    )
    weather_thread.start()

    portal_thread = threading.Thread(
        target=_portal_thread_func,
        args=(config_path,),
        daemon=True,
        name="portal",
    )
    portal_thread.start()

    try:
        _render_loop(config_path, display)
    finally:
        display.close()
        logger.info("PiWeather stopped")


if __name__ == "__main__":
    main()
