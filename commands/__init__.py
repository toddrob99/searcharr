import os
import sys
from importlib import util

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import settings

from telegram.error import BadRequest
import traceback


class Command:
    _list = []
    _name = ""
    _command_aliases = None
    _validation_checks = []
    auth_level = None

    def __init__(self):
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        instance = cls()
        cls._list.append(instance)

    def _register(self, searcharr_instance, logger_instance):
        self.searcharr = searcharr_instance
        self.logger = logger_instance

    def _strip_entities(self, message):
        text = message.text
        entities = message.parse_entities()
        self.logger.debug(f"{entities=}")
        for v in entities.values():
            text = text.replace(v, "")
        text = text.replace("  ", "").strip()
        self.logger.debug(f"Stripped entities from message [{message.text}]: [{text}]")
        return text

    def _xlate(self, key, **kwargs):
        return self.searcharr._xlate(key, **kwargs)

    def _xlate_aliases(self, message, aliases, arg = None):
        joined_message = self._xlate(
            message,
            commands = " OR ".join(
                [
                    f"`/{c}{("" if arg == None else " <" + self._xlate(arg) + ">")}`"
                    for c in aliases
                ]
            ),
        )
        return joined_message

    def _validate_authenticated(self, update):
        self.auth_level = self.searcharr._authenticated(update.message.from_user.id)
        if self.auth_level:
            return True
        else:
            update.message.reply_text(self._xlate_aliases("auth_required", settings.searcharr_start_command_aliases, "password"))
            return None

    def _validate_radarr_enabled(self, update):
        if settings.radarr_enabled:
            return True
        else:
            update.message.reply_text(self._xlate("radarr_disabled"))
            return None

    def _validate_sonarr_enabled(self, update):
        if settings.sonarr_enabled:
            return True
        else:
            update.message.reply_text(self._xlate("sonarr_disabled"))
            return None

    def _validate_readarr_enabled(self, update):
        if settings.readarr_enabled:
            return True
        else:
            update.message.reply_text(self._xlate("readarr_disabled"))
            return None

    def _validated(self, update):
        for check in self._validation_checks:
            method = getattr(self, check)
            if not method(update):
                return None
        return True

    def _execute(self, update, context):
        self.logger.debug(f"Received {self._name} cmd from [{update.message.from_user.username}]")
        if not self._validated(update):
            return
        self._action(update, context)

    def _action(self, update, context):
        pass

    def _search_collection(self, update, context, kind, plural, search_function, command_aliases):
        title = self._strip_entities(update.message)

        if not len(title):
            x_title = self._xlate("title").title()
            response = self._xlate_aliases("include_" + kind + "_title_in_cmd", command_aliases, x_title)
            update.message.reply_text(response)
            return

        results = search_function(title)
        cid = self.searcharr._generate_cid()
        self.searcharr._create_conversation(
            id = cid,
            username = str(update.message.from_user.username),
            kind = kind,
            results = results,
        )

        if not len(results):
            update.message.reply_text(self._xlate("no_matching_" + plural))
            return

        r = results[0]
        reply_message, reply_markup = self.searcharr._prepare_response(
            kind, r, cid, 0, len(results)
        )
        try:
            context.bot.sendPhoto(
                chat_id=update.message.chat.id,
                photo=r["remotePoster"],
                caption=reply_message,
                reply_markup=reply_markup,
            )
        except BadRequest as e:
            if str(e) in self._bad_request_poster_error_messages:
                self.logger.error(
                    f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                )
                context.bot.sendPhoto(
                    chat_id=update.message.chat.id,
                    photo="https://artworks.thetvdb.com/banners/images/missing/movie.jpg",
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
            else:
                raise


def load_module(path):
    name = os.path.split(path)[-1]
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

path = os.path.abspath(__file__)
dirpath = os.path.dirname(path)

for fname in os.listdir(dirpath):
    if not fname.startswith('.') and \
       not fname.startswith('__') and fname.endswith('.py'):
        try:
            load_module(os.path.join(dirpath, fname))
        except Exception:
            traceback.print_exc()