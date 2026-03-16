"""Tests for src/display.py — rendering with mocked hardware."""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Mock hardware modules before importing display
for mod in ("ST7789", "RPi", "RPi.GPIO", "spidev"):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from PIL import Image
import display as display_module


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _blank_image() -> Image.Image:
    return Image.new("RGB", (240, 240), (8, 12, 24))


def _today_data() -> dict:
    return {
        "icon": "clear-sky-day",
        "description": "Clear Sky",
        "high": 24.0,
        "low": 18.0,
        "unit_symbol": "°C",
        "date": "2026-03-16",
        "sunrise": "2026-03-16T06:21",
        "sunset": "2026-03-16T18:45",
        "wmo_code": 0,
    }


def _tomorrow_data() -> dict:
    return {
        "icon": "rain-day",
        "description": "Moderate Rain",
        "high": 19.5,
        "low": 14.2,
        "unit_symbol": "°C",
        "date": "2026-03-17",
        "sunrise": "2026-03-17T06:20",
        "sunset": "2026-03-17T18:46",
        "wmo_code": 63,
    }


# ------------------------------------------------------------------ #
# draw_weather                                                         #
# ------------------------------------------------------------------ #

class TestDrawWeather:
    def test_draw_today_does_not_raise(self):
        img = _blank_image()
        now = datetime(2026, 3, 16, 14, 32)
        display_module.draw_weather(img, _today_data(), day=0, now=now)

    def test_draw_tomorrow_does_not_raise(self):
        img = _blank_image()
        now = datetime(2026, 3, 16, 14, 32)
        display_module.draw_weather(img, _tomorrow_data(), day=1, now=now)

    def test_draw_modifies_image(self):
        img = _blank_image()
        before = img.tobytes()
        now = datetime(2026, 3, 16, 14, 32)
        display_module.draw_weather(img, _today_data(), day=0, now=now)
        after = img.tobytes()
        # At least some pixels should have changed
        assert before != after

    def test_draw_tomorrow_no_time_shown(self):
        """Tomorrow screen should not raise even though time is not displayed."""
        img = _blank_image()
        now = datetime(2026, 3, 16, 22, 0)
        display_module.draw_weather(img, _tomorrow_data(), day=1, now=now)

    def test_draw_with_missing_icon_file_does_not_raise(self):
        """If icon PNG is missing, fallback placeholder should be drawn."""
        img = _blank_image()
        now = datetime(2026, 3, 16, 14, 0)
        data = _today_data()
        data["icon"] = "99z"   # non-existent icon
        display_module.draw_weather(img, data, day=0, now=now)

    def test_draw_fahrenheit_data(self):
        img = _blank_image()
        now = datetime(2026, 3, 16, 10, 0)
        data = _today_data()
        data["high"] = 75.2
        data["low"] = 64.4
        data["unit_symbol"] = "°F"
        display_module.draw_weather(img, data, day=0, now=now)

    def test_image_dimensions_unchanged(self):
        img = _blank_image()
        now = datetime(2026, 3, 16, 9, 0)
        display_module.draw_weather(img, _today_data(), day=0, now=now)
        assert img.size == (240, 240)


# ------------------------------------------------------------------ #
# draw_error                                                           #
# ------------------------------------------------------------------ #

class TestDrawError:
    def test_draw_error_does_not_raise(self):
        img = _blank_image()
        display_module.draw_error(img, "Fetching weather...")

    def test_draw_error_modifies_image(self):
        img = _blank_image()
        before = img.tobytes()
        display_module.draw_error(img, "Loading...")
        after = img.tobytes()
        assert before != after

    def test_draw_error_long_message(self):
        img = _blank_image()
        display_module.draw_error(img, "Could not determine location via IP geolocation service")
