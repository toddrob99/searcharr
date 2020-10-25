"""
Searcharr
Sonarr & Radarr Telegram Bot
Sonarr API Wrapper
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
import requests
from urllib.parse import quote

from log import set_up_logger


class Sonarr(object):
    def __init__(self, api_url, api_key, verbose=False):
        self.logger = set_up_logger("searcharr.sonarr", verbose, False)
        self.logger.debug("Logging started!")
        if api_url[-1] == "/":
            api_url = api_url[:-1]
        self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key

    def lookup_series(self, title=None, tvdb_id=None):
        r = self._api_get(
            "series/lookup", {"term": f"tvdb:{tvdb_id}" if tvdb_id else quote(title)}
        )
        if not r:
            return []

        return [
            {
                "title": x.get("title"),
                "seasonCount": x.get("seasonCount", 0),
                "status": x.get("status", "Unknown Status"),
                "overview": x.get("overview", "Overview not available."),
                "network": x.get("network"),
                "remotePoster": x.get(
                    "remotePoster",
                    "https://artworks.thetvdb.com/banners/images/missing/movie.jpg",
                ),
                "year": x.get("year"),
                "tvdbId": x.get("tvdbId"),
                "seriesType": x.get("seriesType"),
                "imdbId": x.get("imdbId"),
                "certification": x.get("certification"),
                "id": x.get("id"),
                "titleSlug": x.get("titleSlug"),
                "cleanTitle": x.get("cleanTitle"),
                "tvRageId": x.get("tvRageId"),
                "images": x.get("images"),
                "seasons": x.get("seasons"),
            }
            for x in r
        ]

    def add_series(
        self,
        series_info=None,
        tvdb_id=None,
        path=None,
        quality=None,
        search=True,
        season_folders=True,
        monitored=True,
        unmonitor_existing=True,
    ):
        if not series_info and not tvdb_id:
            return False

        if not series_info:
            series_info = self.lookup_series(tvdb_id=tvdb_id)
            if len(series_info):
                series_info = series_info[0]
            else:
                return False

        params = {
            "tvdbId": series_info["tvdbId"],
            "title": series_info["title"],
            "qualityProfileId": quality,
            "titleSlug": series_info["titleSlug"],
            "images": series_info["images"],
            "seasons": series_info["seasons"],
            "rootFolderPath": path,
            "tvRageId": series_info["tvRageId"],
            "seasonFolder": season_folders,
            "monitored": monitored,
            "addOptions": {
                "ignoreEpisodesWithFiles": unmonitor_existing,
                "ignoreEpisodesWithoutFiles": "false",
                "searchForMissingEpisodes": search,
            },
        }

        return self._api_post("series", params)

    def get_root_folders(self):
        r = self._api_get("RootFolder", {})
        if not r:
            return []

        return [
            {
                "path": x.get("path"),
                "freeSpace": x.get("freeSpace"),
                "totalSpace": x.get("totalSpace"),
                "id": x.get("id"),
            }
            for x in r
        ]

    def lookup_quality_profile_id(self, v):
        # Look up quality profile id from a profile name,
        # Or validate existence of a quality profile id
        r = self._api_get("profile", {})
        if not r:
            return 0

        return next((x["id"] for x in r if v in [x["name"], x["id"]]), 0)

    def _api_get(self, endpoint, params={}):
        url = self.api_url.format(endpoint=endpoint)
        for k, v in params.items():
            url += f"&{k}={v}"
        self.logger.debug(f"Submitting GET request: [{url}]")
        r = requests.get(url)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
        else:
            return r.json()

    def _api_post(self, endpoint, params={}):
        url = self.api_url.format(endpoint=endpoint)
        self.logger.debug(f"Submitting POST request: [{url}]; params: [{params}]")
        r = requests.post(url, json=params)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
        else:
            return r.json()
