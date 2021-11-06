"""
Searcharr
Sonarr & Radarr Telegram Bot
By Todd Roberts
https://github.com/toddrob99/searcharr
"""

# Searcharr Bot
searcharr_password = ""  # Used to authenticate as a regular user to add series/movies
searcharr_admin_password = ""  # Used to authenticate as admin to manage users

# Telegram
tgram_token = ""

# Sonarr
sonarr_enabled = True
sonarr_url = ""  # http://192.168.0.100:8989
sonarr_api_key = ""
sonarr_quality_profile_id = "HD-720p"       # can be name or id value
sonarr_add_monitored = True
sonarr_search_on_add = True
sonarr_tag_with_username = True
sonarr_anime_enabled = True                 # enables the /anime command, sets the series type to anime
sonarr_anime_tag_with_anime = True          # will tag the added anime with 'anime'

# Radarr
radarr_enabled = True
radarr_url = ""  # http://192.168.0.100:7878
radarr_api_key = ""
radarr_quality_profile_id = "HD-720p"  # can be name or id value
radarr_add_monitored = True
radarr_search_on_add = True
radarr_tag_with_username = True
