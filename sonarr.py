"""
Searcharr
Sonarr, Radarr & Readarr Telegram Bot
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
        self.sonarr_version = self.discover_version(api_url, api_key)
        if not self.sonarr_version.startswith("4."):
            self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key
        self._quality_profiles = self.get_all_quality_profiles()
        self._root_folders = self.get_root_folders()
        self._all_series = {}
        self.get_all_series()

    def discover_version(self, api_url, api_key):
        try:
            self.api_url = api_url + "/api/v3/{endpoint}?apikey=" + api_key
            sonarrInfo = self._api_get("system/status")
            self.logger.debug(
                f"Discovered Sonarr version {sonarrInfo.get('version')} using v3 api."
            )
            return sonarrInfo.get("version")
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"Sonarr v3 API threw exception: {e}")

        try:
            self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key
            sonarrInfo = self._api_get("system/status")
            self.logger.warning(
                f"Discovered Sonarr version {sonarrInfo.get('version')}. Using legacy API. Consider upgrading to the latest version of Radarr for the best experience."
            )
            return sonarrInfo.get("version")
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"Sonarr legacy API threw exception: {e}")

        self.logger.debug("Failed to discover Sonarr version")
        return None

    def lookup_series(self, title=None, tvdb_id=None):
        r = self._api_get(
            "series/lookup", {"term": f"tvdb:{tvdb_id}" if tvdb_id else quote(title)}
        )
        if not r:
            return []

        return [
            {
                "title": x.get("title"),
                "seasonCount": len(x.get("seasons")),
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
        search=True,
        season_folders=True,
        monitored=True,
        unmonitor_existing=True,
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

        path = additional_data["p"]
        quality = int(additional_data["q"])
        monitor_options = int(additional_data.get("m", 0))
        if monitor_options == 1:
            # Monitor only the first season
            for s in series_info["seasons"]:
                if s["seasonNumber"] != 1:
                    s.update({"monitored": False})
        elif monitor_options == 2:
            if next(
                (x for x in series_info["seasons"] if x["seasonNumber"] == 0), False
            ):
                # There is a Season 0
                max_season = len(series_info["seasons"]) - 1
            else:
                max_season = len(series_info["seasons"])
            # Monitor only the latest season
            for s in series_info["seasons"]:
                if s["seasonNumber"] != max_season:
                    s.update({"monitored": False})
        tags = additional_data.get("t", "")
        if len(tags):
            tag_ids = [int(x) for x in tags.split(",")]
        else:
            tag_ids = []

        self.logger.debug(f"{series_info['seasons']=}")

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
            "tags": tag_ids,
            "addOptions": {
                "ignoreEpisodesWithFiles": unmonitor_existing,
                "ignoreEpisodesWithoutFiles": False,
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

    def get_all_tags(self):
        r = self._api_get("tag", {})
        self.logger.debug(f"Result of API call to get all tags: {r}")
        return [] if not r else r

    def get_filtered_tags(self, allowed_tags, excluded_tags):
        r = self.get_all_tags()
        if not r:
            return []
        elif allowed_tags == []:
            return [
                x
                for x in r
                if not x["label"].startswith("searcharr-")
                and not x["label"] in excluded_tags
            ]
        else:
            return [
                x
                for x in r
                if not x["label"].startswith("searcharr-")
                and (x["label"] in allowed_tags or x["id"] in allowed_tags)
                and x["label"] not in excluded_tags
            ]

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

    def lookup_quality_profile(self, v):
        # Look up quality profile from a profile name or id
        return next(
            (x for x in self._quality_profiles if str(v) in [x["name"], str(x["id"])]),
            None,
        )

    def get_all_quality_profiles(self):
        return self._api_get("qualityprofile", {}) or None

    def lookup_root_folder(self, v):
        # Look up root folder from a path or id
        return next(
            (x for x in self._root_folders if str(v) in [x["path"], str(x["id"])]),
            None,
        )

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
