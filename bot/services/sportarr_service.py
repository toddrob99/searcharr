"""
Searcharr
Sonarr & Radarr Telegram Bot
Sportarr Service Configuration
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from bot.utils.log import set_up_logger
import settings

logger = set_up_logger("sportarr_service")


def configure_sportarr(client):
    """Configure the Sportarr client.
    
    Args:
        client: The Sportarr client
        
    Returns:
        object: The configured Sportarr client
    """
    # Configure quality profiles
    client = _configure_quality_profiles(client)
    
    # Configure root folders
    client = _configure_root_folders(client)
    
    # Configure tags
    _configure_tags(client)
    
    # Check service-specific settings
    _check_service_settings()
    
    return client


def _configure_quality_profiles(client):
    """Configure quality profiles for Sportarr.
    
    Args:
        client: The Sportarr client
        
    Returns:
        object: The Sportarr client with configured quality profiles
    """
    quality_profiles = []
    setting_name = "sportarr_quality_profile_id"
    
    profile_setting = getattr(settings, setting_name, [])
    if not isinstance(profile_setting, list):
        setattr(settings, setting_name, [profile_setting])
        profile_setting = [profile_setting]
        
    for i in profile_setting:
        logger.debug(f"Looking up/validating Sportarr quality profile id for [{i}]...")
        foundProfile = client.lookup_quality_profile(i)
        
        if not foundProfile:
            logger.error(f"Sportarr quality profile id/name [{i}] is invalid!")
        else:
            logger.debug(f"Found Sportarr quality profile for [{i}]: [{foundProfile}]")
            quality_profiles.append(foundProfile)
            
    if not quality_profiles:
        logger.warning(
            f"No valid Sportarr quality profile(s) provided! "
            f"Using all of the quality profiles found in Sportarr: {client._quality_profiles}"
        )
    else:
        logger.debug(
            f"Using the following Sportarr quality profile(s): "
            f"{[(x['id'], x['name']) for x in quality_profiles]}"
        )
        client._quality_profiles = quality_profiles
        
    return client


def _configure_root_folders(client):
    """Configure root folders for Sportarr.
    
    Args:
        client: The Sportarr client
        
    Returns:
        object: The Sportarr client with configured root folders
    """
    setting_name = "sportarr_series_paths"
    
    root_folders = []
    
    if not hasattr(settings, setting_name):
        setattr(settings, setting_name, [])
        logger.warning(
            f"No {setting_name} setting detected. Please set one in settings.py "
            f"({setting_name}=[\"/path/1\", \"/path/2\"]). Proceeding with all root folders configured in Sportarr."
        )
        
    paths_setting = getattr(settings, setting_name)
    if not isinstance(paths_setting, list):
        setattr(settings, setting_name, [paths_setting])
        paths_setting = [paths_setting]
        
    for i in paths_setting:
        logger.debug(f"Looking up/validating Sportarr root folder for [{i}]...")
        foundPath = client.lookup_root_folder(i)
        
        if not foundPath:
            logger.error(f"Sportarr root folder path/id [{i}] is invalid!")
        else:
            logger.debug(f"Found Sportarr root folder for [{i}]: [{foundPath}]")
            root_folders.append(foundPath)
            
    if not root_folders:
        logger.warning(
            f"No valid Sportarr root folder(s) provided! "
            f"Using all of the root folders found in Sportarr: {client._root_folders}"
        )
    else:
        logger.debug(
            f"Using the following Sportarr root folder(s): "
            f"{[(x['id'], x['path']) for x in root_folders]}"
        )
        client._root_folders = root_folders
        
    return client


def _configure_tags(client):
    """Configure tags for Sportarr.
    
    Args:
        client: The Sportarr client
    """
    # Process forced tags
    forced_tags = getattr(settings, "sportarr_forced_tags", [])
    
    for t in forced_tags:
        if t_id := client.get_tag_id(t):
            logger.debug(f"Tag id [{t_id}] for forced Sportarr tag [{t}]")
            
    # Process user-selectable tags
    user_tags = getattr(settings, "sportarr_user_selectable_tags", [])
    
    for t in user_tags:
        if t_id := client.get_tag_id(t):
            logger.debug(f"Tag id [{t_id}] for user-selectable Sportarr tag [{t}]")


def _check_service_settings():
    """Check and set defaults for Sportarr settings."""
    # Check tag_with_username setting
    if not hasattr(settings, "sportarr_tag_with_username"):
        settings.sportarr_tag_with_username = True
        logger.warning(
            "No sportarr_tag_with_username setting found. Please add sportarr_tag_with_username to settings.py "
            "(sportarr_tag_with_username=True or sportarr_tag_with_username=False). Defaulting to True."
        )
        
    # Check command aliases setting
    if not hasattr(settings, "sportarr_sport_command_aliases"):
        settings.sportarr_sport_command_aliases = ["sport"]
        logger.warning(
            "No sportarr_sport_command_aliases setting found. Please add sportarr_sport_command_aliases to settings.py "
            '(e.g. sportarr_sport_command_aliases=["sport", "sp"]). '
            'Defaulting to ["sport"].'
        )
        
    # Check forced tags setting
    if not hasattr(settings, "sportarr_forced_tags"):
        settings.sportarr_forced_tags = []
        logger.warning(
            "No sportarr_forced_tags setting found. Please add sportarr_forced_tags to settings.py "
            '(e.g. sportarr_forced_tags=["tag-1", "tag-2"]) if you want specific tags '
            "added to each series. Defaulting to empty list ([])."
        )
        
    # Check user_selectable_tags setting
    if not hasattr(settings, "sportarr_user_selectable_tags"):
        settings.sportarr_user_selectable_tags = []
        logger.warning(
            "No sportarr_user_selectable_tags setting found. Please add sportarr_user_selectable_tags to settings.py "
            '(e.g. sportarr_user_selectable_tags=["tag-1", "tag-2"]) if you want to limit the tags '
            "a user can select. Defaulting to empty list ([]), which will present the user with all tags."
        )
        
    # Check allow_user_to_select_tags setting
    if not hasattr(settings, "sportarr_allow_user_to_select_tags"):
        settings.sportarr_allow_user_to_select_tags = False
        logger.warning(
            "No sportarr_allow_user_to_select_tags setting found. Please add sportarr_allow_user_to_select_tags to settings.py "
            "(e.g. sportarr_allow_user_to_select_tags=True) "
            "if you want users to be able to select tags "
            "when adding a series. Defaulting to False."
        )
        
    # Check season_monitor_prompt setting
    if not hasattr(settings, "sportarr_season_monitor_prompt"):
        settings.sportarr_season_monitor_prompt = False
        logger.warning(
            "No sportarr_season_monitor_prompt setting found. Please add sportarr_season_monitor_prompt to settings.py "
            "(e.g. sportarr_season_monitor_prompt=True if you want users to choose whether to monitor "
            "all/first/latest season(s). Defaulting to False."
        )