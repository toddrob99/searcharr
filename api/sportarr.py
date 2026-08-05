"""
Searcharr
Sonarr & Radarr Telegram Bot
Sportarr API Wrapper
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from .sonarr import Sonarr


class Sportarr(Sonarr):
    """Sportarr (https://github.com/Sportarr/Sportarr) is a sports event
    manager exposing a Sonarr-v3-compatible API: series lookup, root
    folders, quality profiles, tags and series add all behave like
    Sonarr's, with leagues surfacing as series and events as episodes.
    The Sonarr wrapper therefore drives it as-is; only the service name
    differs so logs and settings stay clearly labeled.
    """

    def __init__(self, api_url, api_key, verbose=False):
        # Skip Sonarr.__init__ on purpose: it pins the service name to
        # "sonarr". Replicate its body with the sportarr service name.
        super(Sonarr, self).__init__(api_url, api_key, "sportarr", verbose)
        self._all_series = {}
        self.get_all_series()
