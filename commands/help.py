from commands import Command
import settings
from util import xlate, xlate_aliases


class Help(Command):
    _name = "help"
    _command_aliases = settings.searcharr_help_command_aliases
    _validation_checks = ["_validate_authenticated"]

    def _action(self, update, context):
        response = ""
        if self.searcharr.sonarr:
            sonarr_help = xlate_aliases("help_sonarr", settings.sonarr_series_command_aliases, "title")
            response += f" {sonarr_help}"
        if self.searcharr.radarr:
            radarr_help = xlate_aliases("help_radarr", settings.radarr_movie_command_aliases, "title")
            response += f" {radarr_help}"
        if self.searcharr.readarr:
            readarr_help = xlate_aliases("help_readarr", settings.readarr_book_command_aliases, "title")
            response += f" {readarr_help}"
        if response == "":
            response = xlate("no_features")

        if self.auth_level == 2:
            response += " " + xlate_aliases("admin_help", settings.searcharr_users_command_aliases)

        update.message.reply_text(response)