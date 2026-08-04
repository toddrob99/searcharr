"""
Searcharr
Sonarr & Radarr Telegram Bot
Command Handlers Registration
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from telegram.ext import CommandHandler

import settings
from bot.commands.start import start_command
from bot.commands.help import help_command
from bot.commands.series import series_command
from bot.commands.sport import sport_command
from bot.commands.movie import movie_command
from bot.commands.users import users_command


def register_commands(application, bot):
    """Register all command handlers with the application.
    
    Args:
        application: The telegram application
        bot: The SearcharrBot instance
    """
    logger = bot.logger
    
    # Register help commands
    for cmd in settings.searcharr_help_command_aliases:
        logger.debug(f"Registering [/{cmd}] as a help command")
        application.add_handler(
            CommandHandler(cmd, lambda update, context: help_command(update, context, bot))
        )
    
    # Register start commands
    for cmd in settings.searcharr_start_command_aliases:
        logger.debug(f"Registering [/{cmd}] as a start command")
        application.add_handler(
            CommandHandler(cmd, lambda update, context: start_command(update, context, bot))
        )
    
    # Register series commands if sonarr is enabled
    if bot.sonarr:
        for cmd in settings.sonarr_series_command_aliases:
            logger.debug(f"Registering [/{cmd}] as a series command")
            application.add_handler(
                CommandHandler(cmd, lambda update, context: series_command(update, context, bot))
            )
    
    # Register sport commands if sportarr is enabled
    if bot.sportarr:
        for cmd in settings.sportarr_sport_command_aliases:
            logger.debug(f"Registering [/{cmd}] as a sport command")
            application.add_handler(
                CommandHandler(cmd, lambda update, context: sport_command(update, context, bot))
            )

    # Register movie commands if radarr is enabled
    if bot.radarr:
        for cmd in settings.radarr_movie_command_aliases:
            logger.debug(f"Registering [/{cmd}] as a movie command")
            application.add_handler(
                CommandHandler(cmd, lambda update, context: movie_command(update, context, bot))
            )
    
    # Register users management commands
    for cmd in settings.searcharr_users_command_aliases:
        logger.debug(f"Registering [/{cmd}] as a users command")
        application.add_handler(
            CommandHandler(cmd, lambda update, context: users_command(update, context, bot))
        )