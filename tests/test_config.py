"""Tests for src/config.py — validation, defaults, atomic write, password hashing."""

import json
import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import config as cfg_module


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _write_config(data: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(data, f)


def _valid_config() -> dict:
    return {
        "lat": "",
        "lon": "",
        "temperature_unit": "celsius",
        "flip_interval_s": 10,
        "weather_refresh_min": 30,
        "display_brightness": 100,
        "display_rotation": 0,
        "portal_password": "",
        "portal_port": 5000,
    }


# ------------------------------------------------------------------ #
# validate_config                                                      #
# ------------------------------------------------------------------ #

class TestValidateConfig:
    def test_valid_config_has_no_errors(self):
        assert cfg_module.validate_config(_valid_config()) == []

    def test_invalid_temperature_unit(self):
        data = _valid_config()
        data["temperature_unit"] = "kelvin"
        errors = cfg_module.validate_config(data)
        assert any("temperature_unit" in e for e in errors)

    def test_flip_interval_too_low(self):
        data = _valid_config()
        data["flip_interval_s"] = 1
        errors = cfg_module.validate_config(data)
        assert any("flip_interval_s" in e for e in errors)

    def test_flip_interval_too_high(self):
        data = _valid_config()
        data["flip_interval_s"] = 9999
        errors = cfg_module.validate_config(data)
        assert any("flip_interval_s" in e for e in errors)

    def test_brightness_out_of_range(self):
        data = _valid_config()
        data["display_brightness"] = 300
        errors = cfg_module.validate_config(data)
        assert any("brightness" in e for e in errors)

    def test_invalid_rotation(self):
        data = _valid_config()
        data["display_rotation"] = 45
        errors = cfg_module.validate_config(data)
        assert any("rotation" in e for e in errors)

    def test_valid_rotations_accepted(self):
        for r in (0, 90, 180, 270):
            data = _valid_config()
            data["display_rotation"] = r
            assert cfg_module.validate_config(data) == []

    def test_invalid_port(self):
        data = _valid_config()
        data["portal_port"] = 99999
        errors = cfg_module.validate_config(data)
        assert any("port" in e for e in errors)

    def test_lat_without_lon_is_error(self):
        data = _valid_config()
        data["lat"] = "51.5"
        data["lon"] = ""
        errors = cfg_module.validate_config(data)
        assert any("lat" in e and "lon" in e for e in errors)

    def test_lat_lon_both_set_valid(self):
        data = _valid_config()
        data["lat"] = "-33.8688"
        data["lon"] = "151.2093"
        assert cfg_module.validate_config(data) == []

    def test_invalid_lat_float(self):
        data = _valid_config()
        data["lat"] = "not-a-float"
        data["lon"] = "151.0"
        errors = cfg_module.validate_config(data)
        assert any("lat" in e for e in errors)

    def test_fahrenheit_accepted(self):
        data = _valid_config()
        data["temperature_unit"] = "fahrenheit"
        assert cfg_module.validate_config(data) == []


# ------------------------------------------------------------------ #
# load_config                                                          #
# ------------------------------------------------------------------ #

class TestLoadConfig:
    def test_valid_config_loads(self, tmp_path):
        path = str(tmp_path / "config.json")
        _write_config(_valid_config(), path)
        result = cfg_module.load_config(path)
        assert result["temperature_unit"] == "celsius"
        assert result["flip_interval_s"] == 10

    def test_defaults_applied_for_missing_keys(self, tmp_path):
        path = str(tmp_path / "config.json")
        _write_config({}, path)
        # Empty config is valid (all defaults work)
        result = cfg_module.load_config(path)
        assert result["display_brightness"] == cfg_module.DEFAULTS["display_brightness"]
        assert result["portal_port"] == cfg_module.DEFAULTS["portal_port"]

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            cfg_module.load_config(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises_value_error(self, tmp_path):
        path = str(tmp_path / "config.json")
        with open(path, "w") as f:
            f.write("{not valid json")
        with pytest.raises(ValueError, match="valid JSON"):
            cfg_module.load_config(path)

    def test_invalid_config_raises_value_error(self, tmp_path):
        path = str(tmp_path / "config.json")
        bad = _valid_config()
        bad["temperature_unit"] = "kelvin"
        _write_config(bad, path)
        with pytest.raises(ValueError):
            cfg_module.load_config(path)


# ------------------------------------------------------------------ #
# save_config                                                          #
# ------------------------------------------------------------------ #

class TestSaveConfig:
    def test_save_writes_valid_json(self, tmp_path):
        path = str(tmp_path / "config.json")
        cfg_module.save_config(_valid_config(), path)
        with open(path) as f:
            data = json.load(f)
        assert data["temperature_unit"] == "celsius"

    def test_save_is_atomic_no_tmp_left(self, tmp_path):
        path = str(tmp_path / "config.json")
        cfg_module.save_config(_valid_config(), path)
        tmp_files = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
        assert tmp_files == []

    def test_save_roundtrip(self, tmp_path):
        path = str(tmp_path / "config.json")
        original = _valid_config()
        original["flip_interval_s"] = 15
        cfg_module.save_config(original, path)
        loaded = cfg_module.load_config(path)
        assert loaded["flip_interval_s"] == 15


# ------------------------------------------------------------------ #
# hash_password / verify_password                                      #
# ------------------------------------------------------------------ #

class TestPasswordHashing:
    def test_hash_returns_pbkdf2_prefix(self):
        h = cfg_module.hash_password("mypassword")
        assert h.startswith("pbkdf2:sha256:260000:")

    def test_hash_has_five_colon_separated_parts(self):
        parts = cfg_module.hash_password("mypassword").split(":")
        assert len(parts) == 5

    def test_hash_round_trip_correct_password(self):
        h = cfg_module.hash_password("correct-horse")
        assert cfg_module.verify_password("correct-horse", h) is True

    def test_hash_round_trip_wrong_password(self):
        h = cfg_module.hash_password("correct-horse")
        assert cfg_module.verify_password("wrong-horse", h) is False

    def test_two_hashes_of_same_password_differ(self):
        h1 = cfg_module.hash_password("same")
        h2 = cfg_module.hash_password("same")
        assert h1 != h2
        assert cfg_module.verify_password("same", h1) is True
        assert cfg_module.verify_password("same", h2) is True

    def test_verify_legacy_plaintext_migration(self):
        assert cfg_module.verify_password("admin", "admin") is True

    def test_verify_legacy_wrong_password(self):
        assert cfg_module.verify_password("wrong", "admin") is False

    def test_verify_empty_stored_returns_false(self):
        assert cfg_module.verify_password("anything", "") is False

    def test_verify_malformed_hash_returns_false(self):
        assert cfg_module.verify_password("pw", "pbkdf2:sha256:NOTANINT:abc:def") is False

    def test_verify_unsupported_method_returns_false(self):
        # Tampered method field
        h = cfg_module.hash_password("pw")
        tampered = h.replace("pbkdf2:sha256:", "pbkdf2:md5:")
        assert cfg_module.verify_password("pw", tampered) is False
