from commands import Command
import settings
from util import xlate, xlate_aliases


class Users(Command):
    _name = "users"
    _command_aliases = settings.searcharr_users_command_aliases
    _validation_checks = ["_validate_authenticated"]

    def _action(self, update, context):
        if self.auth_level != 2:
            update.message.reply_text(
                xlate_aliases("admin_auth_required", settings.searcharr_start_command_aliases, "admin_password")
            )
            return

        results = self.searcharr._get_users()
        cid = self.searcharr._generate_cid()
        self.searcharr._create_conversation(
            id=cid,
            username=str(update.message.from_user.username),
            kind="users",
            results=results,
        )

        if not len(results):
            update.message.reply_text(xlate("no_users_found"))
        else:
            reply_message, reply_markup = self.searcharr._prepare_response_users(
                cid,
                results,
                0,
                len(results),
            )
            context.bot.sendMessage(
                chat_id=update.message.chat.id,
                text=reply_message,
                reply_markup=reply_markup,
            )