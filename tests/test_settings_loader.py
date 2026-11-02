"""Configuration precedence and parsing tests without services or credentials."""

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import settings_loader
from config.defaults import DEFAULT_SETTINGS
from config.settings_loader import ConfigurationError, environment_name, load_settings


class SettingsLoaderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data_file = self.root / "data" / "settings.py"
        self.root_file = self.root / "settings.py"
        patches = (
            patch.object(settings_loader, "_DATA_SETTINGS", str(self.data_file)),
            patch.object(settings_loader, "_ROOT_SETTINGS", str(self.root_file)),
            patch.dict(os.environ, {
                "SEARCHARR_TGRAM_TOKEN": "test-token",
                "SEARCHARR_SONARR_ENABLED": "false",
                "SEARCHARR_RADARR_ENABLED": "false",
            }, clear=True),
            patch.dict(sys.modules),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def write_settings(self, path, **values):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(f"{name} = {value!r}" for name, value in values.items()) + "\n",
            encoding="utf-8",
        )

    def test_environment_only_creates_no_settings_file(self):
        settings = load_settings()
        self.assertEqual(settings.tgram_token, "test-token")
        self.assertEqual(settings.searcharr_language, "en-us")
        self.assertFalse(settings.sonarr_enabled)
        self.assertIsNone(settings._settings_file)
        self.assertFalse(self.data_file.exists())
        self.assertFalse(self.root_file.exists())
        self.assertIs(sys.modules["settings"], settings)

    def test_all_settings_have_prefixed_environment_overrides(self):
        for name, default in DEFAULT_SETTINGS.items():
            with self.subTest(setting=name):
                if isinstance(default, bool):
                    value = not default
                elif isinstance(default, list):
                    value = ["first", "name, with comma"]
                    if name in settings_loader._NAME_OR_ID_SETTINGS:
                        value.append(2)
                elif name.endswith("_url"):
                    value = "https://example.invalid/service"
                elif name == "radarr_min_availability":
                    value = "announced"
                else:
                    value = "configured value"
                raw = json.dumps(value) if type(value) in (bool, list) else value
                with patch.dict(os.environ, {environment_name(name): raw}):
                    settings = load_settings()
                    self.assertEqual(getattr(settings, name), value)
                self.assertTrue(environment_name(name).startswith("SEARCHARR_"))
                self.assertNotIn("SEARCHARR_SEARCHARR_", environment_name(name))

    def test_data_file_overrides_defaults_and_environment_overrides_file(self):
        self.write_settings(
            self.data_file, searcharr_language="pt-br", searcharr_password="file-password",
            sonarr_search_on_add=True, sonarr_series_paths=["/file"],
        )
        with patch.dict(os.environ, {
            "SEARCHARR_PASSWORD": "",
            "SEARCHARR_SONARR_SEARCH_ON_ADD": "false",
            "SEARCHARR_SONARR_SERIES_PATHS": "[]",
        }):
            settings = load_settings()
        self.assertEqual(settings.searcharr_language, "pt-br")
        self.assertEqual(settings.searcharr_password, "")
        self.assertFalse(settings.sonarr_search_on_add)
        self.assertEqual(settings.sonarr_series_paths, [])
        self.assertEqual(settings.searcharr_help_command_aliases, ["help"])

    def test_existing_file_only_installation(self):
        self.write_settings(
            self.data_file, tgram_token="file-token",
            sonarr_enabled=True, sonarr_url="http://sonarr:8989", sonarr_api_key="sonarr-key",
            radarr_enabled=True, radarr_url="http://radarr:7878", radarr_api_key="radarr-key",
            sonarr_quality_profile_id=3, radarr_movie_paths="/movies",
        )
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()
        self.assertEqual(settings.tgram_token, "file-token")
        self.assertEqual(settings.sonarr_quality_profile_id, [3])
        self.assertEqual(settings.radarr_movie_paths, ["/movies"])
        self.assertTrue(settings.radarr_enabled)

    def test_root_file_migrates_without_persisting_environment(self):
        self.write_settings(self.root_file, searcharr_password="file-password")
        original = self.root_file.read_bytes()
        with patch.dict(os.environ, {"SEARCHARR_PASSWORD": "env-password"}):
            settings = load_settings()
        self.assertEqual(settings.searcharr_password, "env-password")
        self.assertEqual(self.data_file.read_bytes(), original)
        self.assertEqual(self.root_file.read_bytes(), original)

    def test_data_file_wins_over_root_file(self):
        self.root_file.write_text("raise AssertionError('root file was executed')\n")
        self.write_settings(self.data_file, searcharr_language="de-de")
        self.assertEqual(load_settings().searcharr_language, "de-de")

    def test_unprefixed_names_are_ignored(self):
        with patch.dict(os.environ, {"SONARR_ENABLED": "true", "TGRAM_TOKEN": "wrong"}):
            settings = load_settings()
        self.assertFalse(settings.sonarr_enabled)
        self.assertEqual(settings.tgram_token, "test-token")

    def test_boolean_spellings(self):
        for text in ("true", "TRUE", " 1 ", "yes", "on", "false", "FALSE", " 0 ", "no", "off"):
            with self.subTest(text=text):
                with patch.dict(os.environ, {"SEARCHARR_SONARR_SEARCH_ON_ADD": text}):
                    actual = load_settings().sonarr_search_on_add
                self.assertEqual(actual, text.strip().lower() in {"true", "1", "yes", "on"})

    def test_invalid_boolean_fails_without_disclosing_value(self):
        for value in ("", "sometimes-secret"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"SEARCHARR_SONARR_ENABLED": value}
            ):
                with self.assertRaises(ConfigurationError) as raised:
                    load_settings()
                self.assertIn("SEARCHARR_SONARR_ENABLED", str(raised.exception))
                if value:
                    self.assertNotIn(value, str(raised.exception))

    def test_invalid_lists_fail_without_disclosing_value(self):
        for value in ('secret-tag', '', '"scalar"', '{}', 'null', '[true]', '[["nested"]]', '[""]'):
            with self.subTest(value=value), patch.dict(
                os.environ, {"SEARCHARR_SONARR_FORCED_TAGS": value}
            ):
                with self.assertRaises(ConfigurationError) as raised:
                    load_settings()
                self.assertIn("SEARCHARR_SONARR_FORCED_TAGS", str(raised.exception))
                self.assertNotIn("secret-tag", str(raised.exception))

    def test_integer_ids_are_restricted_to_profiles_and_paths(self):
        for value in ('[0]', '[-1]', '[true]', '[1.5]'):
            with self.subTest(value=value), patch.dict(
                os.environ, {"SEARCHARR_SONARR_QUALITY_PROFILE_ID": value}
            ):
                with self.assertRaises(ConfigurationError):
                    load_settings()
        with patch.dict(os.environ, {"SEARCHARR_START_COMMAND_ALIASES": "[1]"}):
            with self.assertRaises(ConfigurationError):
                load_settings()

    def test_required_credentials_and_enabled_services(self):
        with patch.dict(os.environ, {"SEARCHARR_TGRAM_TOKEN": ""}):
            with self.assertRaisesRegex(ConfigurationError, "SEARCHARR_TGRAM_TOKEN"):
                load_settings()
        for service in ("SONARR", "RADARR"):
            with self.subTest(service=service):
                with patch.dict(os.environ, {f"SEARCHARR_{service}_ENABLED": "true"}):
                    with self.assertRaisesRegex(ConfigurationError, f"SEARCHARR_{service}_URL"):
                        load_settings()
                    with patch.dict(os.environ, {f"SEARCHARR_{service}_URL": "http://localhost"}):
                        with self.assertRaisesRegex(ConfigurationError, f"SEARCHARR_{service}_API_KEY"):
                            load_settings()
                        with patch.dict(os.environ, {f"SEARCHARR_{service}_API_KEY": "key"}):
                            self.assertTrue(getattr(load_settings(), service.lower() + "_enabled"))

    def test_invalid_url_and_availability_are_reported_by_name(self):
        for url in ("not-a-url", "http://[invalid", "http://host:invalid-port"):
            with self.subTest(url=url), patch.dict(os.environ, {
                "SEARCHARR_SONARR_ENABLED": "true", "SEARCHARR_SONARR_API_KEY": "key",
                "SEARCHARR_SONARR_URL": url,
            }):
                with self.assertRaisesRegex(ConfigurationError, "SEARCHARR_SONARR_URL"):
                    load_settings()
        with patch.dict(os.environ, {"SEARCHARR_RADARR_MIN_AVAILABILITY": "invalid"}):
            with self.assertRaisesRegex(ConfigurationError, "SEARCHARR_RADARR_MIN_AVAILABILITY"):
                load_settings()

    def test_string_whitespace_and_dollar_signs_are_preserved(self):
        with patch.dict(os.environ, {"SEARCHARR_PASSWORD": "  secret$literal  "}):
            self.assertEqual(load_settings().searcharr_password, "  secret$literal  ")

    def test_defaults_are_not_shared_between_loads(self):
        settings = load_settings()
        settings.sonarr_forced_tags.append("temporary")
        self.assertEqual(load_settings().sonarr_forced_tags, [])
        self.assertEqual(DEFAULT_SETTINGS["sonarr_forced_tags"], [])

    def test_source_logging_works_without_a_file_and_does_not_log_secrets(self):
        load_settings()
        with self.assertLogs("searcharr", level="INFO") as logs:
            settings_loader.check_settings_migration()
        self.assertIn("environment variables", " ".join(logs.output))
        self.assertNotIn("test-token", " ".join(logs.output))

    def test_sample_matches_builtin_defaults(self):
        sample = Path(settings_loader._PROJECT_ROOT) / "settings-sample.py"
        if not sample.exists():
            self.skipTest("sample is intentionally excluded from the Docker image")
        parsed = {}
        for node in ast.parse(sample.read_text(encoding="utf-8-sig")).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        parsed[target.id] = ast.literal_eval(node.value)
        self.assertEqual(parsed, DEFAULT_SETTINGS)


if __name__ == "__main__":
    unittest.main()
