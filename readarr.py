"""
Searcharr
Sonarr, Radarr & Readarr Telegram Bot
Readarr API Wrapper
By Ayman Bagabas
https://github.com/toddrob99/searcharr
"""
import requests
from urllib.parse import quote

from log import set_up_logger


class Readarr(object):
    def __init__(self, api_url, api_key, verbose=False):
        self.logger = set_up_logger("searcharr.readarr", verbose, False)
        self.logger.debug("Logging started!")
        if api_url[-1] == "/":
            api_url = api_url[:-1]
        if api_url[:4] != "http":
            self.logger.error(
                "Invalid Readarr URL detected. Please update your settings to include http:// or https:// on the beginning of the URL."
            )
        self.readarr_version = self.discover_version(api_url, api_key)
        if not self.readarr_version.startswith("0."):
            self.api_url = api_url + "/api/v1/{endpoint}?apikey=" + api_key
        self._quality_profiles = self.get_all_quality_profiles()
        self._metadata_profiles = self.get_all_metadata_profiles()
        self._root_folders = self.get_root_folders()

    def discover_version(self, api_url, api_key):
        try:
            self.api_url = api_url + "/api/v1/{endpoint}?apikey=" + api_key
            readarrInfo = self._api_get("system/status")
            self.logger.debug(
                f"Discovered Readarr version {readarrInfo.get('version')}. Using v1 api."
            )
            return readarrInfo.get("version")
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"Readarr v1 API threw exception: {e}")

        try:
            self.api_url = api_url + "/api/{endpoint}?apikey=" + api_key
            readarrInfo = self._api_get("system/status")
            self.logger.warning(
                f"Discovered Readarr version {readarrInfo.get('version')}. Using legacy API. Consider upgrading to the latest version of Readarr for the best experience."
            )
            return readarrInfo.get("version")
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"Readarr legacy API threw exception: {e}")

        self.logger.debug("Failed to discover Readarr version")
        return None

    def lookup_book(self, title):
        r = self._api_get("search", {"term": quote(title)})
        if not r:
            return []

        return [
            {
                "title": x.get("book").get("title"),
                "authorId": x.get("book").get("authorId"),
                "authorTitle": x.get("book").get("authorTitle"),
                "seriesTitle": x.get("book").get("seriesTitle"),
                "disambiguation": x.get("book").get("disambiguation"),
                "overview": x.get("book").get("overview", "No overview available."),
                "remotePoster": x.get("book").get(
                    "remoteCover",
                    "https://artworks.thetvdb.com/banners/images/missing/movie.jpg",
                ),
                "releaseDate": x.get("book").get("releaseDate"),
                "foreignBookId": x.get("book").get("foreignBookId"),
                "id": x.get("book").get("id"),
                "pageCount": x.get("book").get("pageCount"),
                "titleSlug": x.get("book").get("titleSlug"),
                "images": x.get("book").get("images"),
                "links": x.get("book").get("links"),
                "author": x.get("book").get("author"),
                "editions": x.get("book").get("editions"),
            }
            for x in r
            if x.get("book")
        ]

    def add_book(
        self,
        book_info=None,
        search=True,
        monitored=True,
        additional_data={},
    ):
        if not book_info:
            return False

        if not book_info:
            book_info = self.lookup_book(book_info["title"])
            if len(book_info):
                book_info = book_info[0]
            else:
                return False

        self.logger.debug(f"Additional data: {additional_data}")

        path = additional_data["p"]
        quality = int(additional_data["q"])
        metadata = int(additional_data["m"])
        tags = additional_data.get("t", "")
        if len(tags):
            tag_ids = [int(x) for x in tags.split(",")]
        else:
            tag_ids = []

        params = {
            "title": book_info["title"],
            "releaseDate": book_info["releaseDate"],
            "foreignBookId": book_info["foreignBookId"],
            "titleSlug": book_info["titleSlug"],
            "monitored": monitored,
            "anyEditionOk": True,
            "addOptions": {"searchForNewBook": search},
            "editions": book_info["editions"],
            "author": {
                "qualityProfileId": quality,
                "metadataProfileId": metadata,
                "foreignAuthorId": book_info["author"]["foreignAuthorId"],
                "rootFolderPath": path,
                "tags": tag_ids,
            },
        }

        rsp = self._api_post("book", params)
        if rsp is not None and search:
            # Force book search
            srsp = self._api_post(
                "command", {"name": "BookSearch", "bookIds": [rsp.get("id")]}
            )
            self.logger.debug(f"Result of attempt to search book: {srsp}")
        return rsp

    def get_root_folders(self):
        r = self._api_get("rootfolder", {})
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
                    f"Wrong data type returned from Readarr API when attempting to add tag [{tag}]. Expected dict, got {type(t)}."
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
        return (self._api_get("qualityProfile", {})) or None

    def lookup_metadata_profile(self, v):
        # Look up metadata profile from a profile name or id
        return next(
            (x for x in self._metadata_profiles if str(v) in [x["name"], str(x["id"])]),
            None,
        )

    def get_all_metadata_profiles(self):
        return (self._api_get("metadataprofile", {})) or None

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
