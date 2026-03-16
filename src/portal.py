"""Flask web config portal for PiWeather.

Serves a dark-themed configuration page on a configurable port.
Auth behaviour:
  - Empty portal_password: localhost (127.0.0.1 / ::1) allowed without credentials,
    all other origins receive HTTP 403.
  - Non-empty portal_password: HTTP Basic Auth required from all origins; password
    verified via PBKDF2-HMAC-SHA256 hash.

Sensitive fields (portal_password) are masked in the UI. (SEC-01)
"""

import functools
import logging
import threading
from typing import Any

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

import config as cfg_module

logger = logging.getLogger(__name__)

_MASK = "••••••••"
_SENSITIVE_KEYS = ("portal_password",)


def _mask_config(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with sensitive fields replaced by mask."""
    masked = dict(data)
    for key in _SENSITIVE_KEYS:
        if masked.get(key):
            masked[key] = _MASK
    return masked


def create_app(
    config_path: str,
    shared_state: dict[str, Any],
    lock: threading.Lock,
    restart_event: threading.Event,
) -> Flask:
    """Create and return the Flask app.

    Args:
        config_path: Path to the JSON config file.
        shared_state: Shared weather state dict (read-only in portal).
        lock: Lock protecting *shared_state*.
        restart_event: Set to trigger weather re-fetch after config save.
    """
    app = Flask(__name__, template_folder="templates")
    app.secret_key = "piweather-portal"

    # -------------------------------------------------------------- #
    # Auth decorator                                                   #
    # -------------------------------------------------------------- #

    def require_auth(f):  # type: ignore[no-untyped-def]
        @functools.wraps(f)
        def decorated(*args, **kwargs):  # type: ignore[no-untyped-def]
            try:
                current_cfg = cfg_module.load_config(config_path)
                portal_password = current_cfg.get("portal_password", "")
            except Exception as exc:  # noqa: BLE001
                logger.error("require_auth: failed to load config — blocking remote access: %s", exc)
                portal_password = ""

            if not portal_password:
                if request.remote_addr in ("127.0.0.1", "::1"):
                    return f(*args, **kwargs)
                return Response(
                    "Remote access requires a password to be configured.",
                    403,
                )

            auth = request.authorization
            if not auth or auth.username != "admin" or not cfg_module.verify_password(
                auth.password or "", portal_password
            ):
                return Response(
                    "Authentication required",
                    401,
                    {"WWW-Authenticate": 'Basic realm="PiWeather"'},
                )
            return f(*args, **kwargs)
        return decorated

    # -------------------------------------------------------------- #
    # Routes                                                           #
    # -------------------------------------------------------------- #

    @app.route("/", methods=["GET"])
    @require_auth
    def index() -> str:
        """Show configuration form."""
        try:
            current_cfg = cfg_module.load_config(config_path)
        except (FileNotFoundError, ValueError):
            current_cfg = dict(cfg_module.DEFAULTS)

        masked = _mask_config(current_cfg)
        errors = request.args.get("errors", "")
        saved = request.args.get("saved", "")
        return render_template("index.html", cfg=masked, errors=errors, saved=saved)

    @app.route("/save", methods=["POST"])
    @require_auth
    def save() -> Response:
        """Validate and write config, then trigger weather re-fetch."""
        try:
            current_cfg = cfg_module.load_config(config_path)
        except Exception:  # noqa: BLE001
            current_cfg = dict(cfg_module.DEFAULTS)

        form = request.form
        new_cfg: dict[str, Any] = dict(current_cfg)

        new_cfg["lat"] = form.get("lat", "").strip()
        new_cfg["lon"] = form.get("lon", "").strip()
        new_cfg["temperature_unit"] = form.get("temperature_unit", "celsius")
        new_cfg["portal_port"] = int(form.get("portal_port", 8080))

        try:
            new_cfg["flip_interval_s"] = int(form.get("flip_interval_s", 10))
        except (ValueError, TypeError):
            new_cfg["flip_interval_s"] = current_cfg.get("flip_interval_s", 10)

        try:
            new_cfg["weather_refresh_min"] = int(form.get("weather_refresh_min", 30))
        except (ValueError, TypeError):
            new_cfg["weather_refresh_min"] = current_cfg.get("weather_refresh_min", 30)

        try:
            new_cfg["display_brightness"] = int(form.get("display_brightness", 100))
        except (ValueError, TypeError):
            new_cfg["display_brightness"] = current_cfg.get("display_brightness", 100)

        try:
            new_cfg["display_rotation"] = int(form.get("display_rotation", 0))
        except (ValueError, TypeError):
            new_cfg["display_rotation"] = current_cfg.get("display_rotation", 0)

        # Password: hash if a new value is provided (not the mask)
        new_pw = form.get("portal_password", "").strip()
        if new_pw and new_pw != _MASK:
            new_cfg["portal_password"] = cfg_module.hash_password(new_pw)

        errors = cfg_module.validate_config(new_cfg)
        if errors:
            error_str = " | ".join(errors)
            return redirect(url_for("index", errors=error_str))

        try:
            cfg_module.save_config(new_cfg, config_path)
        except (PermissionError, OSError) as exc:
            return redirect(url_for("index", errors=str(exc)))

        logger.info("Config saved via portal; triggering weather re-fetch")
        restart_event.set()
        return redirect(url_for("index", saved="1"))

    @app.route("/status", methods=["GET"])
    @require_auth
    def status() -> Response:
        """Return current weather state as JSON."""
        with lock:
            state_copy = dict(shared_state)
        return jsonify(state_copy)

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        """Liveness check — no auth required."""
        return jsonify({"ok": True})

    return app
