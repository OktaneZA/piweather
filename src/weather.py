"""Weather data fetching and parsing for PiWeather.

Uses Open-Meteo (free, no API key) for forecast data.
Uses ipinfo.io (free, no key) for IP-based location detection.

WMO weather codes are mapped to InkyPi icon filenames so the display
module can load the correct PNG from src/icons/.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# WMO weather code → InkyPi icon name mapping                         #
# ------------------------------------------------------------------ #

# Map WMO code → base icon name (without d/n suffix).
# Suffix is appended based on whether it is currently day or night.
_WMO_TO_ICON: dict[int, str] = {
    0:  "01",   # Clear sky
    1:  "02",   # Mainly clear
    2:  "02",   # Partly cloudy
    3:  "04",   # Overcast
    45: "50",   # Fog
    48: "50",   # Depositing rime fog
    51: "51",   # Light drizzle
    53: "53",   # Moderate drizzle
    55: "53",   # Dense drizzle
    56: "56",   # Light freezing drizzle
    57: "57",   # Dense freezing drizzle
    61: "10",   # Slight rain
    63: "10",   # Moderate rain
    65: "10",   # Heavy rain
    66: "10",   # Slight freezing rain
    67: "10",   # Heavy freezing rain
    71: "71",   # Slight snow fall
    73: "73",   # Moderate snow fall
    75: "73",   # Heavy snow fall
    77: "77",   # Snow grains
    80: "09",   # Slight rain showers
    81: "09",   # Moderate rain showers
    82: "09",   # Violent rain showers
    85: "13",   # Slight snow showers
    86: "13",   # Heavy snow showers
    95: "11",   # Thunderstorm
    96: "11",   # Thunderstorm with slight hail
    99: "11",   # Thunderstorm with heavy hail
}

# Human-readable description for each WMO code
_WMO_DESCRIPTION: dict[int, str] = {
    0:  "Clear Sky",
    1:  "Mainly Clear",
    2:  "Partly Cloudy",
    3:  "Overcast",
    45: "Fog",
    48: "Rime Fog",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Heavy Drizzle",
    56: "Freezing Drizzle",
    57: "Heavy Freezing Drizzle",
    61: "Light Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    66: "Freezing Rain",
    67: "Heavy Freezing Rain",
    71: "Light Snow",
    73: "Moderate Snow",
    75: "Heavy Snow",
    77: "Snow Grains",
    80: "Rain Showers",
    81: "Rain Showers",
    82: "Heavy Showers",
    85: "Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm + Hail",
    99: "Thunderstorm + Hail",
}

# Icons that have meaningful day/night variants in InkyPi
_DAY_NIGHT_ICONS = {"01", "02", "09", "10", "11", "13", "50", "51", "53"}


def wmo_to_icon(code: int, is_night: bool = False) -> str:
    """Map WMO weather code to an InkyPi icon filename (without .png).

    Args:
        code: WMO weather interpretation code (0–99).
        is_night: If True and the icon has a night variant, return the night icon.

    Returns:
        Icon base name, e.g. ``"01d"``, ``"10n"``.
    """
    base = _WMO_TO_ICON.get(code, "01")
    suffix = "n" if (is_night and base in _DAY_NIGHT_ICONS) else "d"
    return f"{base}{suffix}"


def wmo_description(code: int) -> str:
    """Return a short human-readable description for a WMO weather code."""
    return _WMO_DESCRIPTION.get(code, "Unknown")


def _celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return c * 9 / 5 + 32


# ------------------------------------------------------------------ #
# Location detection                                                   #
# ------------------------------------------------------------------ #

def get_location(config: dict[str, Any], timeout: int = 5) -> tuple[float, float]:
    """Return (lat, lon) for weather lookups.

    Order of preference:
    1. Explicit lat/lon in config (both non-empty).
    2. IP geolocation via ipinfo.io.

    Raises RuntimeError if location cannot be determined.
    """
    lat_str = config.get("lat", "").strip()
    lon_str = config.get("lon", "").strip()

    if lat_str and lon_str:
        try:
            return float(lat_str), float(lon_str)
        except ValueError as exc:
            raise RuntimeError(f"Invalid lat/lon in config: {exc}") from exc

    # IP geolocation fallback
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        loc = data.get("loc", "")
        if not loc:
            raise RuntimeError("ipinfo.io returned no location")
        lat_s, lon_s = loc.split(",", 1)
        lat, lon = float(lat_s), float(lon_s)
        logger.info("Location from IP: lat=%.4f lon=%.4f city=%s", lat, lon, data.get("city", "?"))
        return lat, lon
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Could not determine location via IP: {exc}") from exc


# ------------------------------------------------------------------ #
# Open-Meteo weather fetch                                             #
# ------------------------------------------------------------------ #

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(
    lat: float,
    lon: float,
    unit: str = "celsius",
    timeout: int = 10,
) -> dict[str, Any]:
    """Fetch today's and tomorrow's forecast from Open-Meteo.

    Args:
        lat: Latitude.
        lon: Longitude.
        unit: ``"celsius"`` or ``"fahrenheit"``.
        timeout: HTTP request timeout in seconds.

    Returns:
        Dict with keys ``"today"`` and ``"tomorrow"``, each containing:
          - ``icon``: InkyPi icon filename base (e.g. ``"01d"``)
          - ``description``: human-readable condition string
          - ``high``: high temperature (float, in requested unit)
          - ``low``: low temperature (float, in requested unit)
          - ``date``: ISO date string (``"YYYY-MM-DD"``)
          - ``sunrise``: ISO datetime string
          - ``sunset``: ISO datetime string
          - ``wmo_code``: raw WMO code (int)

    Raises:
        requests.RequestException: on network failure.
        ValueError: if the API response is malformed.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset",
        "current_weather": "true",
        "timezone": "auto",
        "forecast_days": 2,
    }

    logger.debug("Fetching weather from Open-Meteo lat=%.4f lon=%.4f", lat, lon)
    resp = requests.get(_OPEN_METEO_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    try:
        daily = data["daily"]
        dates = daily["time"]                  # ["2026-03-16", "2026-03-17"]
        wmo_codes = daily["weathercode"]       # [1, 3]
        highs = daily["temperature_2m_max"]    # [24.1, 19.5]
        lows = daily["temperature_2m_min"]     # [18.0, 14.2]
        sunrises = daily["sunrise"]            # ["2026-03-16T06:21", ...]
        sunsets = daily["sunset"]              # ["2026-03-16T18:45", ...]
        current = data.get("current_weather", {})
    except KeyError as exc:
        raise ValueError(f"Unexpected Open-Meteo response structure: {exc}") from exc

    # Determine day/night for today's icon based on current time vs sunrise/sunset
    try:
        now_hour = datetime.now().hour
        sunrise_hour = int(sunrises[0][11:13]) if sunrises[0] else 6
        sunset_hour = int(sunsets[0][11:13]) if sunsets[0] else 20
        is_night_today = now_hour < sunrise_hour or now_hour >= sunset_hour
    except (IndexError, ValueError):
        is_night_today = False

    def _build_day(idx: int, is_night: bool) -> dict[str, Any]:
        code = int(wmo_codes[idx])
        high_c = float(highs[idx])
        low_c = float(lows[idx])
        if unit == "fahrenheit":
            high = round(_celsius_to_fahrenheit(high_c), 1)
            low = round(_celsius_to_fahrenheit(low_c), 1)
            unit_symbol = "°F"
        else:
            high = round(high_c, 1)
            low = round(low_c, 1)
            unit_symbol = "°C"
        return {
            "icon": wmo_to_icon(code, is_night=is_night),
            "description": wmo_description(code),
            "high": high,
            "low": low,
            "unit_symbol": unit_symbol,
            "date": dates[idx],
            "sunrise": sunrises[idx],
            "sunset": sunsets[idx],
            "wmo_code": code,
        }

    result: dict[str, Any] = {
        "today": _build_day(0, is_night=is_night_today),
        "tomorrow": _build_day(1, is_night=False),  # forecast always uses day icon
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "Weather fetched: today=%s %.0f/%.0f tomorrow=%s %.0f/%.0f",
        result["today"]["description"],
        result["today"]["high"], result["today"]["low"],
        result["tomorrow"]["description"],
        result["tomorrow"]["high"], result["tomorrow"]["low"],
    )
    return result
