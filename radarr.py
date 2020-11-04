"""
Searcharr
Sonarr & Radarr Telegram Bot
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
        self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key

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
        path=None,
        quality=None,
        search=True,
        monitored=True,
    ):
        if not movie_info and not tmdb_id:
            return False

        if not movie_info:
            movie_info = self.lookup_movie(tmdb_id=tmdb_id)
            if len(movie_info):
                movie_info = movie_info[0]
            else:
                return False

        params = {
            "tmdbId": movie_info["tmdbId"],
            "title": movie_info["title"],
            "year": movie_info["year"],
            "qualityProfileId": quality,
            "titleSlug": movie_info["titleSlug"],
            "images": movie_info["images"],
            "rootFolderPath": path,
            "monitored": monitored,
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
        else:
            return r.json()

    def lookup_quality_profile_id(self, v):
        # Look up quality profile id from a profile name,
        # But also allow input of a quality profile id
        r = self._api_get("profile", {})
        if not r:
            return 0

        return next((x["id"] for x in r if str(v) in [x["name"], str(x["id"])]), 0)

    def _api_post(self, endpoint, params={}):
        url = self.api_url.format(endpoint=endpoint)
        self.logger.debug(f"Submitting POST request: [{url}]; params: [{params}]")
        r = requests.post(url, json=params)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
        else:
            return r.json()
