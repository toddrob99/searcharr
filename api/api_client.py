"""
Searcharr
Sonarr & Radarr Telegram Bot
Base API Client
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
import requests
from bot.utils.log import set_up_logger


class ApiClient(object):
    """Base API client for *arr services (Sonarr, Radarr)"""

    def __init__(self, api_url, api_key, service_name, verbose=False):
        """Initialize the API client

        Args:
            api_url (str): Base URL for the service API (e.g. http://localhost:8989)
            api_key (str): API key for authentication
            service_name (str): Name of the service (sonarr, radarr)
            verbose (bool, optional): Enable verbose logging. Defaults to False.
        """
        self.service_name = service_name.lower()
        self.logger = set_up_logger(f"searcharr.{self.service_name}")
        self.logger.debug("Logging started!")
        
        # Validate inputs
        if not api_url:
            self.logger.error(f"Invalid {service_name.title()} URL: URL cannot be empty")
            raise ValueError(f"API URL for {service_name.title()} cannot be empty")
            
        if not api_key:
            self.logger.error(f"Invalid {service_name.title()} API key: API key cannot be empty")
            raise ValueError(f"API key for {service_name.title()} cannot be empty")
        
        # Normalize API URL
        if api_url[-1] == "/":
            api_url = api_url[:-1]
        
        # Validate API URL protocol
        if api_url[:4] != "http":
            self.logger.error(
                f"Invalid {service_name.title()} URL detected. Please update your settings "
                "to include http:// or https:// on the beginning of the URL."
            )
        
        # Discover API version and set appropriate endpoint format
        self.version = self.discover_version(api_url, api_key)
        self.api_url = self._get_api_url_format(api_url, api_key)
        
        # Cache common data
        self._quality_profiles = self.get_all_quality_profiles()
        self._root_folders = self.get_root_folders()
        
    def discover_version(self, api_url, api_key):
        """Discover the version of the service by trying different API endpoints.
        
        Args:
            api_url (str): Base URL for the service
            api_key (str): API key for authentication
            
        Returns:
            str: Version string of the service if found, None otherwise
        """
        api_version = "v3"
        try:
            temp_api_url = f"{api_url}/api/{api_version}/{{endpoint}}?apikey={api_key}"
            self.api_url = temp_api_url  # Temporarily set for _api_get
            service_info = self._api_get("system/status")
            version = service_info.get("version")
            self.logger.debug(
                f"Discovered {self.service_name.title()} version {version}. "
                f"Using {api_version} api."
            )
            return version
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"{self.service_name.title()} {api_version} API threw exception: {e}")

        # Fall back to legacy API
        try:
            temp_api_url = f"{api_url}/api/{{endpoint}}?apikey={api_key}"
            self.api_url = temp_api_url  # Temporarily set for _api_get
            service_info = self._api_get("system/status")
            version = service_info.get("version")
            self.logger.warning(
                f"Discovered {self.service_name.title()} version {version}. "
                f"Using legacy API. Consider upgrading to the latest version "
                f"of {self.service_name.title()} for the best experience."
            )
            return version
        except requests.exceptions.HTTPError as e:
            self.logger.debug(f"{self.service_name.title()} legacy API threw exception: {e}")

        self.logger.debug(f"Failed to discover {self.service_name.title()} version")
        return None

    def _get_api_url_format(self, api_url, api_key):
        """Get the appropriate API URL format based on service and version.
        
        Args:
            api_url (str): Base URL for the service
            api_key (str): API key for authentication
            
        Returns:
            str: Formatted API URL string with endpoint placeholder
        """
        if self.service_name == "sonarr":
            if self.version and self.version.startswith("4."):
                return f"{api_url}/api/v3/{{endpoint}}?apikey={api_key}"
            return f"{api_url}/api/{{endpoint}}?apikey={api_key}"
        elif self.service_name == "sportarr":
            # Sportarr has always exposed the v3-compatible surface.
            return f"{api_url}/api/v3/{{endpoint}}?apikey={api_key}"
        elif self.service_name == "radarr":
            if self.version and not self.version.startswith("0."):
                return f"{api_url}/api/v3/{{endpoint}}?apikey={api_key}"
            return f"{api_url}/api/{{endpoint}}?apikey={api_key}"
        else:
            # Default format if service is unknown
            return f"{api_url}/api/{{endpoint}}?apikey={api_key}"

    def get_root_folders(self):
        """Get all root folders configured in the service.
        
        Returns:
            list: List of root folder objects with path, freeSpace, totalSpace, and id
        """
        endpoint = "RootFolder"
        r = self._api_get(endpoint, {})
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
        """Get all tags configured in the service.
        
        Returns:
            list: List of tag objects
        """
        r = self._api_get("tag", {})
        self.logger.debug(f"Result of API call to get all tags: {r}")
        return [] if not r else r

    def get_filtered_tags(self, allowed_tags, excluded_tags):
        """Get filtered tags based on allowed and excluded lists.
        
        Args:
            allowed_tags (list): List of tag names or IDs to allow
            excluded_tags (list): List of tag names to exclude
            
        Returns:
            list: Filtered list of tag objects
        """
        r = self.get_all_tags()
        if not r:
            return []
        elif allowed_tags == []:
            return [
                x
                for x in r
                if not x["label"].startswith("searcharr-")
                and x["label"] not in excluded_tags
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
        """Add a new tag to the service.
        
        Args:
            tag (str): Tag name to add
            
        Returns:
            dict: Added tag object or None on failure
        """
        params = {
            "label": tag,
        }
        t = self._api_post("tag", params)
        self.logger.debug(f"Result of API call to add tag: {t}")
        return t

    def get_tag_id(self, tag):
        """Get ID for a tag, creating it if it doesn't exist.
        
        Args:
            tag (str): Tag name to look up
            
        Returns:
            int: Tag ID or None on failure
        """
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
                    f"Wrong data type returned from {self.service_name.title()} API when "
                    f"attempting to add tag [{tag}]. Expected dict, got {type(t)}."
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
        """Look up quality profile from a profile name or id.
        
        Args:
            v (str): Quality profile name or ID
            
        Returns:
            dict: Quality profile object or None if not found
        """
        return next(
            (x for x in self._quality_profiles if str(v) in [x["name"], str(x["id"])]),
            None,
        )

    def get_all_quality_profiles(self):
        """Get all quality profiles.
        
        Returns:
            list: Quality profile objects or None on failure
        """
        # Handle different endpoints based on service and version
        if self.service_name == "sonarr":
            endpoint = "qualityprofile"
        elif self.service_name == "radarr":
            if self.version and self.version.startswith("0."):
                endpoint = "profile"
            else:
                endpoint = "qualityProfile"
        else:
            endpoint = "qualityprofile"
            
        return self._api_get(endpoint, {}) or None

    def lookup_root_folder(self, v):
        """Look up root folder from a path or id.
        
        Args:
            v (str): Root folder path or ID
            
        Returns:
            dict: Root folder object or None if not found
        """
        return next(
            (x for x in self._root_folders if str(v) in [x["path"], str(x["id"])]),
            None,
        )

    def _api_get(self, endpoint, params={}):
        """Make a GET request to the API.
        
        Args:
            endpoint (str): API endpoint
            params (dict, optional): Query parameters. Defaults to {}.
            
        Returns:
            dict: Response JSON. Raises requests.HTTPError on non-2xx response.
        """
        url = self.api_url.format(endpoint=endpoint)
        for k, v in params.items():
            url += f"&{k}={v}"
        self.logger.debug(f"Submitting GET request: [{url}]")
        r = requests.get(url)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
        return r.json()

    def _api_post(self, endpoint, params={}):
        """Make a POST request to the API.
        
        Args:
            endpoint (str): API endpoint
            params (dict, optional): Request JSON body. Defaults to {}.
            
        Returns:
            dict: Response JSON. Raises requests.HTTPError on non-2xx response.
        """
        url = self.api_url.format(endpoint=endpoint)
        self.logger.debug(f"Submitting POST request: [{url}]; params: [{params}]")
        r = requests.post(url, json=params)
        if r.status_code not in [200, 201, 202, 204]:
            r.raise_for_status()
        return r.json()