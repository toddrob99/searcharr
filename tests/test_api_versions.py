"""API routing regression tests without settings or live services."""

import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import requests

from api.api_client import ApiClient


class ApiVersionTests(unittest.TestCase):
    def initialize_client(self, service, version, api_path):
        """Simulate a server that only serves its supported API routes."""
        profiles = [{"id": 1, "name": "HD"}]
        folders = [{"id": 1, "path": "/media", "freeSpace": 100, "totalSpace": 200}]
        quality_endpoint = "qualityprofile" if service == "sonarr" else "qualityProfile"
        if service == "radarr" and api_path == "/api":
            quality_endpoint = "profile"
        routes = {
            f"{api_path}/system/status": {"version": version},
            f"{api_path}/{quality_endpoint}": profiles,
            f"{api_path}/RootFolder": folders,
        }

        def get(url):
            path = urlsplit(url).path
            response = requests.Response()
            response.url = url
            response.status_code = 200 if path in routes else 404
            response._content = json.dumps(routes.get(path, {})).encode()
            return response

        with patch("api.api_client.requests.get", side_effect=get) as mock_get:
            with patch("api.api_client.set_up_logger"):
                client = ApiClient("http://arr.test/", "test-key", service)

        self.assertEqual(client.version, version)
        self.assertEqual(client._quality_profiles, profiles)
        self.assertEqual(client._root_folders, folders)
        self.assertEqual(
            client.api_url,
            f"http://arr.test{api_path}/{{endpoint}}?apikey=test-key",
        )
        paths = [urlsplit(call.args[0]).path for call in mock_get.call_args_list]
        self.assertEqual(
            paths[-2:],
            [f"{api_path}/{quality_endpoint}", f"{api_path}/RootFolder"],
        )
        return paths

    def test_sonarr_4_and_later_initialize_using_v3_api(self):
        for version in ("4.0.16.2944", "5.0.0.2870", "6.0.0.1"):
            with self.subTest(version=version):
                self.initialize_client("sonarr", version, "/api/v3")

    def test_older_sonarr_keeps_legacy_api_fallback(self):
        for version in ("2.0.0.5344", "3.0.10.1567"):
            with self.subTest(version=version):
                paths = self.initialize_client("sonarr", version, "/api")
                self.assertEqual(
                    paths[:2], ["/api/v3/system/status", "/api/system/status"]
                )

    def test_radarr_api_routing_is_unchanged(self):
        for version, api_path in (
            ("0.2.0.1504", "/api"),
            ("6.4.4.10685", "/api/v3"),
        ):
            with self.subTest(version=version):
                self.initialize_client("radarr", version, api_path)


if __name__ == "__main__":
    unittest.main()
