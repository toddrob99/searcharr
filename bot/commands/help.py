"""
Searcharr
Sonarr & Radarr Telegram Bot
Help Command Handler
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from bot.utils.auth import authenticated
from bot.utils.text import translate
from bot.utils.log import set_up_logger
import settings

logger = set_up_logger("commands.help")


async def help_command(update, context, bot):
    """Handle the /help command to provide usage information.
    
    Args:
        update: The update with the message
        context: The callback context
        bot: The SearcharrBot instance
    """
    logger.debug(f"Received help cmd from [{update.message.from_user.username}]")
    
    # Check authentication
    auth_level = authenticated(update.message.from_user.id)
    if not auth_level:
        await update.message.reply_text(
            translate(
                "auth_required",
                commands=" OR ".join(
                    [
                        f"`/{c} <{translate('password')}>`"
                        for c in settings.searcharr_start_command_aliases
                    ]
                ),
            )
        )
        return
    
    # Prepare help text based on enabled services
    help_text = []
    
    # Sonarr help
    if settings.sonarr_enabled:
        help_text.append(
            translate(
                "help_sonarr",
                series_commands=" OR ".join(
                    [
                        f"`/{c} {translate('title').title()}`"
                        for c in settings.sonarr_series_command_aliases
                    ]
                ),
            )
        )
    
    # Sportarr help
    if settings.sportarr_enabled:
        help_text.append(
            translate(
                "help_sportarr",
                sport_commands=" OR ".join(
                    [
                        f"`/{c} {translate('title').title()}`"
                        for c in settings.sportarr_sport_command_aliases
                    ]
                ),
            )
        )

    # Radarr help
    if settings.radarr_enabled:
        help_text.append(
            translate(
                "help_radarr",
                movie_commands=" OR ".join(
                    [
                        f"`/{c} {translate('title').title()}`"
                        for c in settings.radarr_movie_command_aliases
                    ]
                ),
            )
        )
    
    # Add admin help if the user is an admin
    if auth_level == 2:
        help_text.append(
            translate(
                "admin_help",
                commands=" OR ".join(
                    [f"`/{c}`" for c in settings.searcharr_users_command_aliases]
                ),
            )
        )
    
    # Format and send the help message
    if help_text:
        await update.message.reply_text(" ".join(help_text))
    else:
        await update.message.reply_text(translate("no_features"))