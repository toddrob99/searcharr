"""
Searcharr
Sonarr, Radarr & Readarr Telegram Bot
Radarr API Wrapper
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
import requests
from urllib.parse import quote

from log import set_up_logger


class Radarr(object):
    def __init__(self, api_url, api_key, verbose=False):
        self.logger = set_up_logger("searcharr.radarr", verbose, False)
        self.logger.debug("Logging started!")
        if api_url[-1] == "/":
            api_url = api_url[:-1]
        if api_url[:4] != "http":
            self.logger.error(
                "Invalid Radarr URL detected. Please update your settings to include http:// or https:// on the beginning of the URL."
            )
        self.radarr_version = self.discover_version(api_url, api_key)
        if not self.radarr_version.startswith("0."):
            self.api_url = api_url + "/api/v3/{endpoint}?apikey=" + api_key
        self._quality_profiles = self.get_all_quality_profiles()
        self._root_folders = self.get_root_folders()

    def discover_version(self, api_url, api_key):
        try:
            self.api_url = api_url + "/api/v3/{endpoint}?apikey=" + api_key
            radarrInfo = self._api_get("system/status")
            self.logger.debug(
                f"Discovered Radarr version {radarrInfo.get('version')}. Using v3 api."
            )
            return radarrInfo.get("version")
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"Radarr v3 API threw exception: {e}")

        try:
            self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key
            radarrInfo = self._api_get("system/status")
            self.logger.warning(
                f"Discovered Radarr version {radarrInfo.get('version')}. Using legacy API. Consider upgrading to the latest version of Radarr for the best experience."
            )
            return radarrInfo.get("version")
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"Radarr legacy API threw exception: {e}")

        self.logger.debug("Failed to discover Radarr version")
        return None

    def lookup_movie(self, title=None, tmdb_id=None):
        r = self._api_get(
            "movie/lookup", {"term": f"tmdb:{tmdb_id}" if tmdb_id else quote(title)}
        )
        if not r:
            return []

        return [
            {
                "title": x.get("title"),
                "overview": x.get("overview", "No overview available."),
                "status": x.get("status", "Unknown Status"),
                "inCinemas": x.get("inCinemas"),
                "remotePoster": x.get(
                    "remotePoster",
                    "https://artworks.thetvdb.com/banners/images/missing/movie.jpg",
                ),
                "year": x.get("year"),
                "tmdbId": x.get("tmdbId"),
                "imdbId": x.get("imdbId", None),
                "runtime": x.get("runtime"),
                "id": x.get("id"),
                "titleSlug": x.get("titleSlug"),
                "images": x.get("images"),
            }
            for x in r
        ]

    def add_movie(
        self,
        movie_info=None,
        tmdb_id=None,
        search=True,
        monitored=True,
        min_avail="released",
        additional_data={},
    ):
        if not movie_info and not tmdb_id:
            return False

        if not movie_info:
            movie_info = self.lookup_movie(tmdb_id=tmdb_id)
            if len(movie_info):
                movie_info = movie_info[0]
            else:
                return False

        self.logger.debug(f"Additional data: {additional_data}")

        path = additional_data["p"]
        quality = int(additional_data["q"])
        tags = additional_data.get("t", "")
        if len(tags):
            tag_ids = [int(x) for x in tags.split(",")]
        else:
            tag_ids = []

        params = {
            "tmdbId": movie_info["tmdbId"],
            "title": movie_info["title"],
            "year": movie_info["year"],
            "qualityProfileId": quality,
            "titleSlug": movie_info["titleSlug"],
            "images": movie_info["images"],
            "rootFolderPath": path,
            "monitored": monitored,
            "minimumAvailability": min_avail,
            "tags": tag_ids,
            "addOptions": {"searchForMovie": search},
        }

        return self._api_post("movie", params)

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
                    f"Wrong data type returned from Radarr API when attempting to add tag [{tag}]. Expected dict, got {type(t)}."
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
        return (
            self._api_get("profile", {})
            if self.radarr_version.startswith("0.")
            else self._api_get("qualityProfile", {})
        ) or None

    def lookup_root_folder(self, v):
        # Look up root folder from a path or id
        return next(
            (x for x in self._root_folders if str(v) in [x["path"], str(x["id"])]),
            None,
        )

    def _api_post(self, endpoint, params={}):
        url = self.api_url.format(endpoint=endpoint)
        self.logger.debug(f"Submitting POST request: [{url}]; params: [{params}]")
        r = requests.post(url, json=params)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
            return None
        else:
            return r.json()
