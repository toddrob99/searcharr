import os
import sys
from importlib import util as import_util
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from telegram.error import BadRequest
import traceback

import settings
import util
from util import xlate, xlate_aliases


class Command:
    _dict = {}
    _name = ""
    _command_aliases = None
    _validation_checks = []
    auth_level = None

    def __init__(self):
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        instance = cls()
        cls._dict[cls._name] = instance

    def _inject_dependency(self, searcharr_instance):
        self.searcharr = searcharr_instance

    def _validate_authenticated(self, update):
        self.auth_level = self.searcharr._authenticated(update.message.from_user.id)
        if self.auth_level:
            return True
        else:
            update.message.reply_text(xlate_aliases("auth_required", settings.searcharr_start_command_aliases, "password"))
            return None

    def _validate_radarr_enabled(self, update):
        if settings.radarr_enabled:
            return True
        else:
            update.message.reply_text(xlate("radarr_disabled"))
            return None

    def _validate_sonarr_enabled(self, update):
        if settings.sonarr_enabled:
            return True
        else:
            update.message.reply_text(xlate("sonarr_disabled"))
            return None

    def _validate_readarr_enabled(self, update):
        if settings.readarr_enabled:
            return True
        else:
            update.message.reply_text(xlate("readarr_disabled"))
            return None

    def _validated(self, update):
        for check in self._validation_checks:
            method = getattr(self, check)
            if not method(update):
                return None
        return True

    def _execute(self, update, context):
        util.log.debug(f"Received {self._name} cmd from [{update.message.from_user.username}]")
        if not self._validated(update):
            return
        self._action(update, context)

    def _action(self, update, context):
        pass
    
    def _search_collection(self, update, context, kind, plural, search_function, command_aliases):
        title = util.strip_entities(update.message)

        if not len(title):
            x_title = xlate("title").title()
            response = xlate_aliases("include_" + kind + "_title_in_cmd", command_aliases, x_title)
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
            update.message.reply_text(xlate("no_matching_" + plural))
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
                util.log.error(
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
    spec = import_util.spec_from_file_location(name, path)
    module = import_util.module_from_spec(spec)
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