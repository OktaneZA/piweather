"""Tests for src/weather.py — WMO mapping, location, Open-Meteo parsing."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import weather as weather_module

# ------------------------------------------------------------------ #
# WMO code → icon mapping                                             #
# ------------------------------------------------------------------ #

class TestWmoToIcon:
    def test_code_0_is_clear_sky_day(self):
        assert weather_module.wmo_to_icon(0, is_night=False) == "clear-sky-day"

    def test_code_0_is_clear_sky_night(self):
        assert weather_module.wmo_to_icon(0, is_night=True) == "clear-sky-night"

    def test_code_3_overcast_has_no_night_variant(self):
        # overcast has no night variant no night variant, falls back to day icon
        assert weather_module.wmo_to_icon(3, is_night=True) == "overcast-day"

    def test_rain_showers_night_uses_day_icon(self):
        # rain-showers has no night variant no night variant, falls back to day icon
        assert weather_module.wmo_to_icon(80, is_night=True) == "rain-showers-day"

    def test_thunderstorm_night_uses_day_icon(self):
        # thunderstorm has no night variant no night variant, falls back to day icon
        assert weather_module.wmo_to_icon(95, is_night=True) == "thunderstorm-day"

    def test_fog_night_uses_day_icon(self):
        # fog has no night variant no night variant, falls back to day icon
        assert weather_module.wmo_to_icon(45, is_night=True) == "fog-day"

    def test_code_95_thunderstorm(self):
        assert weather_module.wmo_to_icon(95) == "thunderstorm-day"

    def test_code_71_light_snow(self):
        assert weather_module.wmo_to_icon(71) == "light-snow-day"

    def test_code_61_rain_day(self):
        assert weather_module.wmo_to_icon(61) == "rain-day"

    def test_code_61_rain_night(self):
        assert weather_module.wmo_to_icon(61, is_night=True) == "rain-night"

    def test_partly_cloudy_has_night_variant(self):
        assert weather_module.wmo_to_icon(2, is_night=True) == "partly-cloudy-night"

    def test_unknown_code_falls_back_to_clear_sky(self):
        assert weather_module.wmo_to_icon(999) == "clear-sky-day"

    def test_tomorrow_always_day_icon(self):
        # wmo_to_icon is called with is_night=False for tomorrow
        icon = weather_module.wmo_to_icon(0, is_night=False)
        assert icon.endswith("-day")


class TestWmoDescription:
    def test_code_0_description(self):
        assert weather_module.wmo_description(0) == "Clear Sky"

    def test_code_95_description(self):
        assert "Thunderstorm" in weather_module.wmo_description(95)

    def test_unknown_code_returns_unknown(self):
        assert weather_module.wmo_description(999) == "Unknown"


# ------------------------------------------------------------------ #
# Temperature conversion                                               #
# ------------------------------------------------------------------ #

class TestTemperatureConversion:
    def test_0_celsius_is_32_fahrenheit(self):
        assert weather_module._celsius_to_fahrenheit(0) == 32.0

    def test_100_celsius_is_212_fahrenheit(self):
        assert weather_module._celsius_to_fahrenheit(100) == 212.0

    def test_minus_40_same_in_both(self):
        assert weather_module._celsius_to_fahrenheit(-40) == -40.0


# ------------------------------------------------------------------ #
# Location detection                                                   #
# ------------------------------------------------------------------ #

class TestGetLocation:
    def test_uses_config_lat_lon_when_set(self):
        config = {"lat": "-33.8688", "lon": "151.2093"}
        lat, lon = weather_module.get_location(config)
        assert abs(lat - (-33.8688)) < 0.001
        assert abs(lon - 151.2093) < 0.001

    def test_falls_back_to_ipinfo(self):
        config = {"lat": "", "lon": ""}
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"loc": "51.5074,-0.1278", "city": "London"}
        mock_resp.raise_for_status = MagicMock()

        with patch("weather.requests.get", return_value=mock_resp) as mock_get:
            lat, lon = weather_module.get_location(config)

        mock_get.assert_called_once()
        assert abs(lat - 51.5074) < 0.001
        assert abs(lon - (-0.1278)) < 0.001

    def test_raises_if_no_config_and_ipinfo_fails(self):
        config = {"lat": "", "lon": ""}
        with patch("weather.requests.get", side_effect=Exception("network error")):
            with pytest.raises(RuntimeError, match="Could not determine location"):
                weather_module.get_location(config)

    def test_raises_if_ipinfo_returns_no_loc(self):
        config = {"lat": "", "lon": ""}
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        with patch("weather.requests.get", return_value=mock_resp):
            with pytest.raises(RuntimeError):
                weather_module.get_location(config)

    def test_invalid_lat_in_config_raises(self):
        config = {"lat": "not-a-float", "lon": "10.0"}
        with pytest.raises(RuntimeError, match="Invalid lat/lon"):
            weather_module.get_location(config)


# ------------------------------------------------------------------ #
# Open-Meteo response parsing                                          #
# ------------------------------------------------------------------ #

_MOCK_RESPONSE = {
    "daily": {
        "time": ["2026-03-16", "2026-03-17"],
        "weathercode": [1, 63],
        "temperature_2m_max": [24.0, 19.5],
        "temperature_2m_min": [18.0, 14.2],
        "sunrise": ["2026-03-16T06:21", "2026-03-17T06:20"],
        "sunset":  ["2026-03-16T18:45", "2026-03-17T18:46"],
    },
    "current_weather": {
        "temperature": 22.0,
        "windspeed": 10.0,
        "weathercode": 1,
        "is_day": 1,
        "time": "2026-03-16T14:00",
    },
    "timezone": "Australia/Sydney",
}


class TestFetchWeather:
    def _mock_get(self, data=None):
        resp = MagicMock()
        resp.json.return_value = data or _MOCK_RESPONSE
        resp.raise_for_status = MagicMock()
        return resp

    def test_returns_today_and_tomorrow(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0, unit="celsius")
        assert "today" in result
        assert "tomorrow" in result

    def test_today_has_correct_date(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0)
        assert result["today"]["date"] == "2026-03-16"

    def test_tomorrow_has_correct_date(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0)
        assert result["tomorrow"]["date"] == "2026-03-17"

    def test_celsius_temperatures(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0, unit="celsius")
        assert result["today"]["high"] == 24.0
        assert result["today"]["low"] == 18.0
        assert result["today"]["unit_symbol"] == "°C"

    def test_fahrenheit_temperatures(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0, unit="fahrenheit")
        # 24°C = 75.2°F
        assert abs(result["today"]["high"] - 75.2) < 0.2
        assert result["today"]["unit_symbol"] == "°F"

    def test_today_icon_is_string(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0)
        icon = result["today"]["icon"]
        assert isinstance(icon, str)
        assert icon.endswith("-day") or icon.endswith("-night")

    def test_tomorrow_icon_always_day(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0)
        assert result["tomorrow"]["icon"].endswith("-day")

    def test_tomorrow_wmo_code_63_is_rain(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0)
        assert "Rain" in result["tomorrow"]["description"]

    def test_malformed_response_raises_value_error(self):
        bad_resp = MagicMock()
        bad_resp.json.return_value = {"unexpected": "format"}
        bad_resp.raise_for_status = MagicMock()
        with patch("weather.requests.get", return_value=bad_resp):
            with pytest.raises(ValueError):
                weather_module.fetch_weather(0.0, 0.0)

    def test_fetched_at_is_present(self):
        with patch("weather.requests.get", return_value=self._mock_get()):
            result = weather_module.fetch_weather(0.0, 0.0)
        assert "fetched_at" in result
