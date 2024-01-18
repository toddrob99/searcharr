from commands import Command
import settings
import util
from util import xlate, xlate_aliases


class Start(Command):
    _name = "start"
    _command_aliases = settings.searcharr_start_command_aliases
    _validation_checks = []

    def _action(self, update, context):
        password = util.strip_entities(update.message)
        util.log.debug(f"{update}")
        
        if password and password == settings.searcharr_admin_password:
            self.searcharr._add_user(
                id=update.message.from_user.id,
                username=update.message.from_user.username,
                admin=1,
            )
            update.message.reply_text(
                xlate_aliases("admin_auth_success", settings.searcharr_help_command_aliases)
            )
        elif self.searcharr._authenticated(update):
            update.message.reply_text(
                xlate_aliases("already_authenticated", settings.searcharr_help_command_aliases)
            )

        elif password == settings.searcharr_password:
            self.searcharr._add_user(
                id=update.message.from_user.id,
                username=update.message.from_user.username,
            )
            update.message.reply_text(
                xlate_aliases("auth_successful", settings.searcharr_help_command_aliases)
            )
        else:
            update.message.reply_text(xlate("incorrect_pw"))