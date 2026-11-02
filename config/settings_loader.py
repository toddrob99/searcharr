"""Load configuration from defaults, an optional Python file, and the environment."""

import copy
import importlib.util
import json
import logging
import os
import shutil
import sys
from types import ModuleType
from urllib.parse import urlsplit

from config.defaults import DEFAULT_SETTINGS

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_DATA_SETTINGS = os.path.join(_PROJECT_ROOT, "data", "settings.py")
_ROOT_SETTINGS = os.path.join(_PROJECT_ROOT, "settings.py")
_NAME_OR_ID_SETTINGS = {
    "sonarr_quality_profile_id", "sonarr_series_paths",
    "radarr_quality_profile_id", "radarr_movie_paths",
}


class ConfigurationError(ValueError):
    """Invalid configuration, reported without including credential values."""


def environment_name(setting):
    """Return the single supported environment name for a setting."""
    name = setting.upper()
    return name if name.startswith("SEARCHARR_") else "SEARCHARR_" + name


def _invalid(setting, detail):
    return ConfigurationError(f"{setting} ({environment_name(setting)}) {detail}")


def _parse_environment(setting, value):
    default = DEFAULT_SETTINGS[setting]
    if isinstance(default, bool):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise _invalid(setting, "must be true/false, 1/0, yes/no, or on/off.")
    if isinstance(default, list):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            raise _invalid(setting, "must be a JSON array; use [] for an empty list.") from None
        if not isinstance(parsed, list):
            raise _invalid(setting, "must be a JSON array; use [] for an empty list.")
        return parsed
    # Empty strings are explicit overrides; do not strip passwords or tokens.
    return value


def _validate_configuration(settings):
    for name, default in DEFAULT_SETTINGS.items():
        value = getattr(settings, name)
        if isinstance(default, list):
            # Preserve the documented single-name/ID form in Python settings files.
            if name in _NAME_OR_ID_SETTINGS and type(value) in (str, int):
                value = [value]
                setattr(settings, name, value)
            if not isinstance(value, list):
                raise _invalid(name, "must be a list.")
            for item in value:
                if isinstance(item, str) and item.strip():
                    continue
                if name in _NAME_OR_ID_SETTINGS and type(item) is int and item > 0:
                    continue
                detail = "nonempty strings or positive integer IDs" if name in _NAME_OR_ID_SETTINGS else "nonempty strings"
                raise _invalid(name, f"must contain only {detail}.")
        elif type(value) is not type(default):
            expected = "a boolean" if isinstance(default, bool) else "a string"
            raise _invalid(name, f"must be {expected}.")

    if not settings.tgram_token.strip():
        raise _invalid("tgram_token", "must be set.")

    for service in ("sonarr", "radarr"):
        if not getattr(settings, f"{service}_enabled"):
            continue
        for suffix in ("url", "api_key"):
            name = f"{service}_{suffix}"
            if not getattr(settings, name).strip():
                raise _invalid(name, f"must be set when {service}_enabled is true.")
        try:
            url = urlsplit(getattr(settings, f"{service}_url"))
            valid_url = url.scheme in {"http", "https"} and bool(url.hostname)
            url.port  # Validate the optional port without logging the supplied URL.
        except ValueError:
            valid_url = False
        if not valid_url:
            raise _invalid(f"{service}_url", "must be an HTTP or HTTPS URL.")

    if settings.radarr_min_availability not in {"announced", "inCinemas", "released"}:
        raise _invalid("radarr_min_availability", "must be announced, inCinemas, or released.")


def load_settings():
    """Apply defaults < optional settings.py < SEARCHARR_* environment variables."""
    # Preserve automatic migration for existing installations.
    if not os.path.exists(_DATA_SETTINGS) and os.path.exists(_ROOT_SETTINGS):
        os.makedirs(os.path.dirname(_DATA_SETTINGS), exist_ok=True)
        shutil.copy2(_ROOT_SETTINGS, _DATA_SETTINGS)

    settings_path = next(
        (path for path in (_DATA_SETTINGS, _ROOT_SETTINGS) if os.path.exists(path)),
        None,
    )
    if settings_path:
        spec = importlib.util.spec_from_file_location("settings", settings_path)
        settings = importlib.util.module_from_spec(spec)
    else:
        settings = ModuleType("settings")
    settings.__dict__.update(copy.deepcopy(DEFAULT_SETTINGS))
    if settings_path:
        spec.loader.exec_module(settings)

    overrides = []
    for name in DEFAULT_SETTINGS:
        env_name = environment_name(name)
        if env_name in os.environ:
            setattr(settings, name, _parse_environment(name, os.environ[env_name]))
            overrides.append(env_name)

    _validate_configuration(settings)
    settings._settings_file = settings_path
    settings._environment_overrides = tuple(overrides)
    # Complete configuration must exist before callback modules import settings.
    sys.modules["settings"] = settings
    return settings


def check_settings_migration():
    """Report configuration sources after logging is configured, without values."""
    logger = logging.getLogger("searcharr")
    settings = sys.modules["settings"]
    source = getattr(settings, "_settings_file", None)
    if source == _DATA_SETTINGS:
        if os.path.exists(_ROOT_SETTINGS):
            with open(_DATA_SETTINGS, "rb") as data_file, open(_ROOT_SETTINGS, "rb") as root_file:
                if data_file.read() != root_file.read():
                    logger.warning(
                        "Settings have moved to data/settings.py. Your ROOT settings.py "
                        "has DIFFERENT content and is being IGNORED. Update data/settings.py "
                        "or use SEARCHARR_* environment variables; remove the old root file "
                        "mapping from docker-compose.yml."
                    )
                else:
                    logger.info(
                        "Settings loaded from data/settings.py. "
                        "The root settings.py volume mapping is no longer needed."
                    )
        else:
            logger.info("Settings loaded from data/settings.py.")
    elif source:
        logger.info("Settings loaded from root settings.py (consider moving to data/).")
    else:
        logger.info("Settings loaded from environment variables and built-in defaults.")

    overrides = getattr(settings, "_environment_overrides", ())
    if overrides:
        logger.info("Environment overrides applied: %s", ", ".join(overrides))
