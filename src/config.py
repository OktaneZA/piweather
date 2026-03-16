"""Config loading, validation, and atomic saving for PiWeather.

Config is stored as JSON at /etc/piweather/config.json (or path from
PIWEATHER_CONFIG env var). All fields have defaults; missing keys are filled
automatically on load.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import stat
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "/etc/piweather/config.json"

DEFAULTS: dict[str, Any] = {
    "lat": "",                      # empty = use IP geolocation
    "lon": "",                      # empty = use IP geolocation
    "temperature_unit": "celsius",  # "celsius" | "fahrenheit"
    "flip_interval_s": 10,          # seconds to show today before flipping to tomorrow
    "weather_refresh_min": 30,      # minutes between weather API calls
    "display_brightness": 100,      # 0–255
    "display_rotation": 0,          # 0 | 90 | 180 | 270
    "portal_password": "",          # empty = local-only mode; set to PBKDF2 hash for remote
    "portal_port": 8080,
}


def hash_password(plaintext: str) -> str:
    """Hash *plaintext* with PBKDF2-HMAC-SHA256 and a random 16-byte salt.

    Returns: ``pbkdf2:sha256:260000:<salt_hex>:<base64_hash>``
    Uses only Python stdlib. Never logs input value.
    """
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plaintext.encode("utf-8"),
        bytes.fromhex(salt),
        260_000,
    )
    return f"pbkdf2:sha256:260000:{salt}:{base64.b64encode(dk).decode('ascii')}"


def verify_password(plaintext: str, stored: str) -> bool:
    """Return True if *plaintext* matches *stored* password hash.

    Handles legacy plaintext passwords (no ``pbkdf2:`` prefix) for migration.
    Never logs either argument.
    """
    if not stored:
        return False
    if not stored.startswith("pbkdf2:"):
        return secrets.compare_digest(plaintext, stored)
    try:
        _, method, iterations_str, salt_hex, hash_b64 = stored.split(":")
        if method != "sha256":
            logger.warning("verify_password: unsupported hash method %r", method)
            return False
        dk_stored = base64.b64decode(hash_b64)
        dk_attempt = hashlib.pbkdf2_hmac(
            method,
            plaintext.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_str),
        )
        return secrets.compare_digest(dk_attempt, dk_stored)
    except Exception:  # noqa: BLE001
        logger.warning("verify_password: malformed stored hash (not logging value)")
        return False


def _check_file_permissions(path: str) -> None:
    """Warn if config file is world-readable."""
    try:
        mode = os.stat(path).st_mode
        if mode & stat.S_IROTH:
            logger.warning(
                "Config file %s is world-readable — consider `chmod 640 %s`",
                path, path,
            )
    except OSError:
        pass


def validate_config(data: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings; empty list means valid."""
    errors: list[str] = []

    unit = data.get("temperature_unit", "")
    if unit not in ("celsius", "fahrenheit"):
        errors.append(f"temperature_unit must be 'celsius' or 'fahrenheit', got {unit!r}")

    flip = data.get("flip_interval_s", 10)
    if not isinstance(flip, int) or not (3 <= flip <= 3600):
        errors.append(f"flip_interval_s must be an integer 3–3600, got {flip!r}")

    refresh = data.get("weather_refresh_min", 30)
    if not isinstance(refresh, int) or not (5 <= refresh <= 1440):
        errors.append(f"weather_refresh_min must be an integer 5–1440, got {refresh!r}")

    brightness = data.get("display_brightness", 100)
    if not isinstance(brightness, int) or not (0 <= brightness <= 255):
        errors.append(f"display_brightness must be an integer 0–255, got {brightness!r}")

    rotation = data.get("display_rotation", 0)
    if rotation not in (0, 90, 180, 270):
        errors.append(f"display_rotation must be 0, 90, 180, or 270; got {rotation!r}")

    port = data.get("portal_port", 8080)
    if not isinstance(port, int) or not (1 <= port <= 65535):
        errors.append(f"portal_port must be 1–65535, got {port!r}")

    # lat/lon: either both empty (use IP geolocation) or both valid floats
    lat = data.get("lat", "")
    lon = data.get("lon", "")
    if bool(lat) != bool(lon):
        errors.append("lat and lon must both be set or both be empty")
    if lat:
        try:
            float(lat)
        except (ValueError, TypeError):
            errors.append(f"lat must be a valid float, got {lat!r}")
    if lon:
        try:
            float(lon)
        except (ValueError, TypeError):
            errors.append(f"lon must be a valid float, got {lon!r}")

    return errors


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load and validate config from *path*.

    Missing keys are filled from DEFAULTS. Raises ValueError if validation fails.
    """
    path = path or os.environ.get("PIWEATHER_CONFIG", DEFAULT_CONFIG_PATH)

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    _check_file_permissions(path)

    try:
        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file {path} is not valid JSON: {exc}") from exc

    data = {**DEFAULTS, **raw}

    errors = validate_config(data)
    if errors:
        raise ValueError(
            f"Config validation failed ({len(errors)} error(s)):\n  "
            + "\n  ".join(errors)
        )

    logger.info(
        "Config loaded: unit=%s flip=%ds lat=%s lon=%s",
        data["temperature_unit"],
        data["flip_interval_s"],
        data["lat"] or "(auto)",
        data["lon"] or "(auto)",
    )
    return data


def save_config(data: dict[str, Any], path: str | None = None) -> None:
    """Validate and atomically write config to *path*.

    Writes to a .tmp file then uses os.replace() for atomicity.
    Raises ValueError if validation fails.
    """
    path = path or os.environ.get("PIWEATHER_CONFIG", DEFAULT_CONFIG_PATH)

    errors = validate_config(data)
    if errors:
        raise ValueError(
            f"Config validation failed ({len(errors)} error(s)):\n  "
            + "\n  ".join(errors)
        )

    dir_path = os.path.dirname(path) or "."
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except PermissionError as exc:
        raise PermissionError(f"Cannot write config to {path}: {exc}") from exc

    logger.info("Config saved to %s", path)
