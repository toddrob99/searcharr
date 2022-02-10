"""
Searcharr
Sonarr & Radarr Telegram Bot
Sonarr API Wrapper
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
import requests
import time
from urllib.parse import quote

from log import set_up_logger


class Sonarr(object):
    def __init__(self, api_url, api_key, verbose=False):
        self.logger = set_up_logger("searcharr.sonarr", verbose, False)
        self.logger.debug("Logging started!")
        if api_url[-1] == "/":
            api_url = api_url[:-1]
        if api_url[:4] != "http":
            self.logger.error(
                "Invalid Sonarr URL detected. Please update your settings to include http:// or https:// on the beginning of the URL."
            )
        self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key
        self._all_series = {}
        self.get_all_series()

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
                "id": x.get("id", self._series_internal_id(x.get("tvdbId"))),
                "titleSlug": x.get("titleSlug"),
                "cleanTitle": x.get("cleanTitle"),
                "tvRageId": x.get("tvRageId"),
                "images": x.get("images"),
                "seasons": x.get("seasons"),
                "genres": x.get("genres", []),
            }
            for x in r
        ]

    def _series_internal_id(self, tvdb_id):
        return next(
            (x["id"] for x in self.get_all_series() if x.get("tvdbId", 0) == tvdb_id),
            None,
        )

    def get_all_series(self):
        if int(round(self._all_series.get("ts", 0))) < int(round(time.time())) - 30:
            self.logger.debug("Refreshing all series cache...")
            r = self._api_get("series", {})
            self._all_series.update({"series": r, "ts": time.time()})

        return self._all_series["series"]

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
        tag=None,
        additional_data={},
    ):
        if not series_info and not tvdb_id:
            return False

        if not series_info:
            series_info = self.lookup_series(tvdb_id=tvdb_id)
            if len(series_info):
                series_info = series_info[0]
            else:
                return False

        self.logger.debug(f"Additional data: {additional_data}")

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
            "seriesType": "anime" if additional_data.get("st") == "a" else "standard",
            "addOptions": {
                "ignoreEpisodesWithFiles": unmonitor_existing,
                "ignoreEpisodesWithoutFiles": "false",
                "searchForMissingEpisodes": search,
            },
        }
        if tag:
            if tag_id := self.get_tag_id(tag):
                params.update({"tags": [tag_id]})
            else:
                self.logger.warning(
                    "Tag lookup/creation failed. The series will not be tagged."
                )

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

    def get_all_tags(self):
        r = self._api_get("tag", {})
        self.logger.debug(f"Result of API call to get all tags: {r}")
        return [] if not r else r

    def add_tag(self, tag):
        params = {
            "label": tag,
        }
        t = self._api_post("tag", params)
        self.logger.debug(f"Result of API call to add tag: {t}")
        return t

    def get_tag_id(self, tag):
        if i := next(
            iter(
                [
                    x.get("id")
                    for x in self.get_all_tags()
                    if x.get("label").lower() == tag.lower()
                ]
            ),
            None,
        ):
            self.logger.debug(f"Found tag id [{i}] for tag [{tag}]")
            return i
        else:
            self.logger.debug(f"No tag id found for [{tag}]; adding...")
            t = self.add_tag(tag)
            if not isinstance(t, dict):
                self.logger.error(
                    f"Wrong data type returned from Sonarr API when attempting to add tag [{tag}]. Expected dict, got {type(t)}."
                )
                return None
            else:
                self.logger.debug(
                    f"Created tag id for tag [{tag}]: {t['id']}"
                    if t.get("id")
                    else f"Could not add tag [{tag}]"
                )
            return t.get("id", None)

    def lookup_quality_profile_id(self, v):
        # Look up quality profile id from a profile name,
        # Or validate existence of a quality profile id
        r = self._api_get("profile", {})
        if not r:
            return 0

        return next((x["id"] for x in r if str(v) in [x["name"], str(x["id"])]), 0)

    def _api_get(self, endpoint, params={}):
        url = self.api_url.format(endpoint=endpoint)
        for k, v in params.items():
            url += f"&{k}={v}"
        self.logger.debug(f"Submitting GET request: [{url}]")
        r = requests.get(url)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
            return None
        else:
            return r.json()

    def _api_post(self, endpoint, params={}):
        url = self.api_url.format(endpoint=endpoint)
        self.logger.debug(f"Submitting POST request: [{url}]; params: [{params}]")
        r = requests.post(url, json=params)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
            return None
        else:
            return r.json()
