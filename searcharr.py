"""
Searcharr
Sonarr & Radarr Telegram Bot
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
import argparse
import json
import os
import sqlite3
from threading import Lock
from urllib.parse import parse_qsl
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import BadRequest
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

from log import set_up_logger
import radarr
import sonarr
import settings

__version__ = "2.0-b5"

DBPATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
DBFILE = "searcharr.db"
DBLOCK = Lock()


def parse_args():
    parser = argparse.ArgumentParser(
        prog="Searcharr", description="Start the Searcharr Bot."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        dest="verbose",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--console-logging",
        "-c",
        action="store_true",
        dest="console_logging",
        help="Enable console logging.",
    )
    parser.add_argument(
        "--dev",
        "-d",
        action="store_true",
        dest="dev_mode",
        help="Enable developer mode, which will result in more exceptions being raised instead of handled.",
    )
    return parser.parse_args()


class Searcharr(object):
    def __init__(self, token):
        self.DEV_MODE = True if args.dev_mode else False
        self.token = token
        logger.info(f"Searcharr v{__version__} - Logging started!")
        self.sonarr = (
            sonarr.Sonarr(settings.sonarr_url, settings.sonarr_api_key, args.verbose)
            if settings.sonarr_enabled
            else None
        )
        if self.sonarr:
            quality_profiles = []
            if not isinstance(settings.sonarr_quality_profile_id, list):
                settings.sonarr_quality_profile_id = [
                    settings.sonarr_quality_profile_id
                ]
            for i in settings.sonarr_quality_profile_id:
                logger.debug(
                    f"Looking up/validating Sonarr quality profile id for [{i}]..."
                )
                foundProfile = self.sonarr.lookup_quality_profile(i)
                if not foundProfile:
                    logger.error(f"Sonarr quality profile id/name [{i}] is invalid!")
                else:
                    logger.debug(
                        f"Found Sonarr quality profile for [{i}]: [{foundProfile}]"
                    )
                    quality_profiles.append(foundProfile)
            if not len(quality_profiles):
                logger.warning(
                    f"No valid Sonarr quality profile(s) provided! Using all of the quality profiles I found in Sonarr: {self.sonarr._quality_profiles}"
                )
            else:
                logger.debug(
                    f"Using the following Sonarr quality profile(s): {[(x['id'], x['name']) for x in quality_profiles]}"
                )
                self.sonarr._quality_profiles = quality_profiles

            root_folders = []
            if not hasattr(settings, "sonarr_series_paths"):
                settings.sonarr_series_paths = []
                logger.warning(
                    'No sonarr_series_paths setting detected. Please set one in settings.py (sonarr_series_paths=["/path/1", "/path/2"]). Proceeding with all root folders configured in Sonarr.'
                )
            if not isinstance(settings.sonarr_series_paths, list):
                settings.sonarr_series_paths = [settings.sonarr_series_paths]
            for i in settings.sonarr_series_paths:
                logger.debug(f"Looking up/validating Sonarr root folder for [{i}]...")
                foundPath = self.sonarr.lookup_root_folder(i)
                if not foundPath:
                    logger.error(f"Sonarr root folder path/id [{i}] is invalid!")
                else:
                    logger.debug(f"Found Sonarr root folder for [{i}]: [{foundPath}]")
                    root_folders.append(foundPath)
            if not len(root_folders):
                logger.warning(
                    f"No valid Sonarr root folder(s) provided! Using all of the root folders I found in Sonarr: {self.sonarr._root_folders}"
                )
            else:
                logger.debug(
                    f"Using the following Sonarr root folder(s): {[(x['id'], x['path']) for x in root_folders]}"
                )
                self.sonarr._root_folders = root_folders
            if not hasattr(settings, "sonarr_tag_with_username"):
                settings.sonarr_tag_with_username = True
                logger.warning(
                    "No sonarr_tag_with_username setting found. Please add sonarr_tag_with_username to settings.py (sonarr_tag_with_username=True or sonarr_tag_with_username=False). Defaulting to True."
                )
            if not hasattr(settings, "sonarr_series_command_aliases"):
                settings.sonarr_series_command_aliases = ["series"]
                logger.warning(
                    'No sonarr_series_command_aliases setting found. Please add sonarr_series_command_aliases to settings.py (e.g. sonarr_series_command_aliases=["series", "tv"]. Defaulting to ["series"].'
                )
            if not hasattr(settings, "sonarr_season_monitor_prompt"):
                settings.sonarr_season_monitor_prompt = False
                logger.warning(
                    "No sonarr_season_monitor_prompt setting found. Please add sonarr_season_monitor_prompt to settings.py (e.g. sonarr_season_monitor_prompt=True if you want users to choose whether to monitor all/first/latest season(s). Defaulting to False."
                )
            if not hasattr(settings, "sonarr_forced_tags"):
                settings.sonarr_forced_tags = []
                logger.warning(
                    'No sonarr_forced_tags setting found. Please add sonarr_forced_tags to settings.py (e.g. sonarr_forced_tags=["tag-1", "tag-2"]) if you want specific tags added to each series. Defaulting to empty list ([]).'
                )
            if not hasattr(settings, "sonarr_allow_user_to_select_tags"):
                settings.sonarr_allow_user_to_select_tags = False
                logger.warning(
                    "No sonarr_allow_user_to_select_tags setting found. Please add sonarr_allow_user_to_select_tags to settings.py (e.g. sonarr_allow_user_to_select_tags=True) if you want users to be able to select tags when adding a series. Defaulting to False."
                )
            if not hasattr(settings, "sonarr_user_selectable_tags"):
                settings.sonarr_user_selectable_tags = []
                logger.warning(
                    'No sonarr_user_selectable_tags setting found. Please add sonarr_user_selectable_tags to settings.py (e.g. sonarr_user_selectable_tags=["tag-1", "tag-2"]) if you want to limit the tags a user can select. Defaulting to empty list ([]), which will present the user with all tags.'
                )
            for t in settings.sonarr_user_selectable_tags:
                if t_id := self.sonarr.get_tag_id(t):
                    logger.debug(
                        f"Tag id [{t_id}] for user-selectable Sonarr tag [{t}]"
                    )
            for t in settings.sonarr_forced_tags:
                if t_id := self.sonarr.get_tag_id(t):
                    logger.debug(f"Tag id [{t_id}] for forced Sonarr tag [{t}]")
        self.radarr = (
            radarr.Radarr(settings.radarr_url, settings.radarr_api_key, args.verbose)
            if settings.radarr_enabled
            else None
        )
        if self.radarr:
            quality_profiles = []
            if not isinstance(settings.radarr_quality_profile_id, list):
                settings.radarr_quality_profile_id = [
                    settings.radarr_quality_profile_id
                ]
            for i in settings.radarr_quality_profile_id:
                logger.debug(
                    f"Looking up/validating Radarr quality profile id for [{i}]..."
                )
                foundProfile = self.radarr.lookup_quality_profile(i)
                if not foundProfile:
                    logger.error(f"Radarr quality profile id/name [{i}] is invalid!")
                else:
                    logger.debug(
                        f"Found Radarr quality profile for [{i}]: [{foundProfile}]"
                    )
                    quality_profiles.append(foundProfile)
            if not len(quality_profiles):
                logger.warning(
                    f"No valid Radarr quality profile(s) provided! Using all of the quality profiles I found in Radarr: {self.radarr._quality_profiles}"
                )
            else:
                logger.debug(
                    f"Using the following Radarr quality profile(s): {[(x['id'], x['name']) for x in quality_profiles]}"
                )
                self.radarr._quality_profiles = quality_profiles

            root_folders = []
            if not hasattr(settings, "radarr_movie_paths"):
                settings.radarr_movie_paths = []
                logger.warning(
                    'No radarr_movie_paths setting detected. Please set one in settings.py (radarr_movie_paths=["/path/1", "/path/2"]). Proceeding with all root folders configured in Radarr.'
                )
            if not isinstance(settings.radarr_movie_paths, list):
                settings.radarr_movie_paths = [settings.radarr_movie_paths]
            for i in settings.radarr_movie_paths:
                logger.debug(f"Looking up/validating Radarr root folder for [{i}]...")
                foundPath = self.radarr.lookup_root_folder(i)
                if not foundPath:
                    logger.error(f"Radarr root folder path/id [{i}] is invalid!")
                else:
                    logger.debug(f"Found Radarr root folder for [{i}]: [{foundPath}]")
                    root_folders.append(foundPath)
            if not len(root_folders):
                logger.warning(
                    f"No valid Radarr root folder(s) provided! Using all of the root folders I found in Radarr: {self.radarr._root_folders}"
                )
            else:
                logger.debug(
                    f"Using the following Radarr root folder(s): {[(x['id'], x['path']) for x in root_folders]}"
                )
                self.radarr._root_folders = root_folders
            if not hasattr(settings, "radarr_tag_with_username"):
                settings.radarr_tag_with_username = True
                logger.warning(
                    "No radarr_tag_with_username setting found. Please add radarr_tag_with_username to settings.py (radarr_tag_with_username=True or radarr_tag_with_username=False). Defaulting to True."
                )
            if not hasattr(settings, "radarr_min_availability"):
                settings.radarr_min_availability = "released"
                logger.warning(
                    'No radarr_min_availability setting found. Please add radarr_min_availability to settings.py (options: "released", "announced", "inCinema"). Defaulting to "released".'
                )
            if not hasattr(settings, "radarr_movie_command_aliases"):
                settings.radarr_movie_command_aliases = ["movie"]
                logger.warning(
                    'No radarr_movie_command_aliases setting found. Please add radarr_movie_command_aliases to settings.py (e.g. radarr_movie_command_aliases=["movie", "mv"]. Defaulting to ["movie"].'
                )
            if not hasattr(settings, "radarr_forced_tags"):
                settings.radarr_forced_tags = []
                logger.warning(
                    'No radarr_forced_tags setting found. Please add radarr_forced_tags to settings.py (e.g. radarr_forced_tags=["tag-1", "tag-2"]) if you want specific tags added to each movie. Defaulting to empty list ([]).'
                )
            if not hasattr(settings, "radarr_allow_user_to_select_tags"):
                settings.radarr_allow_user_to_select_tags = True
                logger.warning(
                    "No radarr_allow_user_to_select_tags setting found. Please add radarr_allow_user_to_select_tags to settings.py (e.g. radarr_allow_user_to_select_tags=False) if you do not want users to be able to select tags when adding a movie. Defaulting to True."
                )
            if not hasattr(settings, "radarr_user_selectable_tags"):
                settings.radarr_user_selectable_tags = []
                logger.warning(
                    'No radarr_user_selectable_tags setting found. Please add radarr_user_selectable_tags to settings.py (e.g. radarr_user_selectable_tags=["tag-1", "tag-2"]) if you want to limit the tags a user can select. Defaulting to empty list ([]), which will present the user with all tags.'
                )
            for t in settings.radarr_user_selectable_tags:
                if t_id := self.radarr.get_tag_id(t):
                    logger.debug(
                        f"Tag id [{t_id}] for user-selectable Radarr tag [{t}]"
                    )
            for t in settings.radarr_forced_tags:
                if t_id := self.radarr.get_tag_id(t):
                    logger.debug(f"Tag id [{t_id}] for forced Radarr tag [{t}]")

        self.conversations = {}
        if not hasattr(settings, "searcharr_admin_password"):
            settings.searcharr_admin_password = uuid.uuid4().hex
            logger.warning(
                f'No admin password detected. Please set one in settings.py (searcharr_admin_password="your admin password"). Using {settings.searcharr_admin_password} as the admin password for this session.'
            )
        if settings.searcharr_password == "":
            logger.warning(
                'Password is blank. This will allow anyone to add series/movies using your bot. If this is unexpected, set a password in settings.py (searcharr_password="your password").'
            )

    def cmd_start(self, update, context):
        logger.debug(f"Received start cmd from [{update.message.from_user.username}]")
        password = self._strip_entities(update.message)
        if password and password == settings.searcharr_admin_password:
            self._add_user(
                id=update.message.from_user.id,
                username=str(update.message.from_user.username),
                admin=1,
            )
            update.message.reply_text(
                "Admin authentication successful. Use /help for commands."
            )
        elif self._authenticated(update.message.from_user.id):
            update.message.reply_text(
                "You are already authenticated. Try /help for usage info."
            )
        elif password == settings.searcharr_password:
            self._add_user(
                id=update.message.from_user.id,
                username=str(update.message.from_user.username),
            )
            update.message.reply_text(
                "Authentication successful. Use /help for commands."
            )
        else:
            update.message.reply_text("Incorrect password.")

    def cmd_movie(self, update, context):
        logger.debug(f"Received movie cmd from [{update.message.from_user.username}]")
        if not self._authenticated(update.message.from_user.id):
            update.message.reply_text(
                "I don't seem to know you... Please authenticate with `/start <password>` and then try again."
            )
            return
        if not settings.radarr_enabled:
            update.message.reply_text("Sorry, but movie support is disabled.")
            return
        title = self._strip_entities(update.message)
        if not len(title):
            update.message.reply_text(
                f'Please include the movie title in the command, e.g. {" OR ".join([f"`/{c} Title Here`" for c in settings.radarr_movie_command_aliases])}'
            )
            return
        results = self.radarr.lookup_movie(title)
        cid = self._generate_cid()
        # self.conversations.update({cid: {"cid": cid, "type": "movie", "results": results}})
        self._create_conversation(
            id=cid,
            username=str(update.message.from_user.username),
            kind="movie",
            results=results,
        )

        if not len(results):
            update.message.reply_text("Sorry, but I didn't find any matching movies.")
        else:
            r = results[0]
            reply_message, reply_markup = self._prepare_response(
                "movie", r, cid, 0, len(results)
            )
            try:
                context.bot.sendPhoto(
                    chat_id=update.message.chat.id,
                    photo=r["remotePoster"],
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
            except BadRequest as e:
                if str(e) == "Wrong type of the web page content":
                    logger.error(
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

    def cmd_series(self, update, context):
        logger.debug(f"Received series cmd from [{update.message.from_user.username}]")
        if not self._authenticated(update.message.from_user.id):
            update.message.reply_text(
                "I don't seem to know you... Please authenticate with `/start <password>` and then try again."
            )
            return
        if not settings.sonarr_enabled:
            update.message.reply_text("Sorry, but series support is disabled.")
            return
        title = self._strip_entities(update.message)
        if not len(title):
            update.message.reply_text(
                f'Please include the series title in the command, e.g. {" OR ".join([f"`/{c} Title Here`" for c in settings.sonarr_series_command_aliases])}'
            )
            return
        results = self.sonarr.lookup_series(title)
        cid = self._generate_cid()
        # self.conversations.update({cid: {"cid": cid, "type": "series", "results": results}})
        self._create_conversation(
            id=cid,
            username=str(update.message.from_user.username),
            kind="series",
            results=results,
        )

        if not len(results):
            update.message.reply_text("Sorry, but I didn't find any matching series.")
        else:
            r = results[0]
            reply_message, reply_markup = self._prepare_response(
                "series", r, cid, 0, len(results)
            )
            try:
                context.bot.sendPhoto(
                    chat_id=update.message.chat.id,
                    photo=r["remotePoster"],
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
            except BadRequest as e:
                if str(e) == "Wrong type of the web page content":
                    logger.error(
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

    def cmd_users(self, update, context):
        logger.debug(f"Received users cmd from [{update.message.from_user.username}]")
        auth_level = self._authenticated(update.message.from_user.id)
        if not auth_level:
            update.message.reply_text(
                "I don't seem to know you... Please authenticate with `/start <password>` and then try again."
            )
            return
        elif auth_level != 2:
            update.message.reply_text(
                "You do not have admin permissions... Please authenticate with `/start <admin password>` and then try again."
            )
            return

        results = self._get_users()
        cid = self._generate_cid()
        # self.conversations.update({cid: {"cid": cid, "type": "users", "results": results}})
        self._create_conversation(
            id=cid,
            username=str(update.message.from_user.username),
            kind="users",
            results=results,
        )
        if not len(results):
            update.message.reply_text(
                "Sorry, but I didn't find any users. That seems wrong..."
            )
        else:
            reply_message, reply_markup = self._prepare_response_users(
                cid,
                results,
                0,
                5,
                len(results),
            )
            context.bot.sendMessage(
                chat_id=update.message.chat.id,
                text=reply_message,
                reply_markup=reply_markup,
            )

    def callback(self, update, context):
        query = update.callback_query
        logger.debug(
            f"Received callback from [{query.from_user.username}]: [{query.data}]"
        )
        auth_level = self._authenticated(query.from_user.id)
        if not auth_level:
            query.message.reply_text(
                "I don't seem to know you... Please authenticate with `/start <password>` and then try again."
            )
            query.message.delete()
            query.answer()
            return

        if not query.data or not len(query.data):
            query.answer()
            return

        convo = self._get_conversation(query.data.split("^^^")[0])
        # convo = self.conversations.get(query.data.split("^^^")[0])
        if not convo:
            query.message.reply_text(
                "I received your command, but I don't recognize the conversation. Please start again."
            )
            query.message.delete()
            query.answer()
            return

        cid, i, op = query.data.split("^^^")
        if "^^" in op:
            op, op_flags = op.split("^^")
            op_flags = dict(parse_qsl(op_flags))
            for k, v in op_flags.items():
                logger.debug(
                    f"Adding/Updating additional data for cid=[{cid}], key=[{k}], value=[{v}]..."
                )
                self._update_add_data(cid, k, v)
        i = int(i)
        if op == "noop":
            pass
        elif op == "cancel":
            self._delete_conversation(cid)
            # self.conversations.pop(cid)
            query.message.reply_text("Search canceled!")
            query.message.delete()
        elif op == "done":
            self._delete_conversation(cid)
            # self.conversations.pop(cid)
            query.message.delete()
        elif op == "prev":
            if convo["type"] in ["series", "movie"]:
                if i <= 0:
                    query.answer()
                    return
                r = convo["results"][i - 1]
                reply_message, reply_markup = self._prepare_response(
                    convo["type"], r, cid, i - 1, len(convo["results"])
                )
                try:
                    query.message.edit_media(
                        media=InputMediaPhoto(r["remotePoster"]),
                        reply_markup=reply_markup,
                    )
                except BadRequest as e:
                    if str(e) == "Wrong type of the web page content":
                        logger.error(
                            f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                        )
                        query.message.edit_media(
                            media=InputMediaPhoto(
                                "https://artworks.thetvdb.com/banners/images/missing/movie.jpg"
                            ),
                            reply_markup=reply_markup,
                        )
                    else:
                        raise
                query.bot.edit_message_caption(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
            elif convo["type"] == "users":
                if i <= 0:
                    i = 0
                reply_message, reply_markup = self._prepare_response_users(
                    cid,
                    convo["results"],
                    i,
                    5,
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=reply_message,
                    reply_markup=reply_markup,
                )
        elif op == "next":
            if convo["type"] in ["series", "movie"]:
                if i >= len(convo["results"]):
                    query.answer()
                    return
                r = convo["results"][i + 1]
                logger.debug(f"{r=}")
                reply_message, reply_markup = self._prepare_response(
                    convo["type"], r, cid, i + 1, len(convo["results"])
                )
                try:
                    query.message.edit_media(
                        media=InputMediaPhoto(r["remotePoster"]),
                        reply_markup=reply_markup,
                    )
                except BadRequest as e:
                    if str(e) == "Wrong type of the web page content":
                        logger.error(
                            f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                        )
                        query.message.edit_media(
                            media=InputMediaPhoto(
                                "https://artworks.thetvdb.com/banners/images/missing/movie.jpg"
                            ),
                            reply_markup=reply_markup,
                        )
                    else:
                        raise
                query.bot.edit_message_caption(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
            elif convo["type"] == "users":
                if i > len(convo["results"]):
                    query.answer()
                    return
                reply_message, reply_markup = self._prepare_response_users(
                    cid,
                    convo["results"],
                    i,
                    5,
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=reply_message,
                    reply_markup=reply_markup,
                )
        elif op == "add":
            r = convo["results"][i]
            additional_data = self._get_add_data(cid)
            logger.debug(f"{additional_data=}")
            paths = (
                self.sonarr._root_folders
                if convo["type"] == "series"
                else self.radarr._root_folders
                if convo["type"] == "movie"
                else []
            )
            if not additional_data.get("p"):
                if len(paths) > 1:
                    reply_message, reply_markup = self._prepare_response(
                        convo["type"],
                        r,
                        cid,
                        i,
                        len(convo["results"]),
                        add=True,
                        paths=paths,
                    )
                    try:
                        query.message.edit_media(
                            media=InputMediaPhoto(r["remotePoster"]),
                            reply_markup=reply_markup,
                        )
                    except BadRequest as e:
                        if str(e) == "Wrong type of the web page content":
                            logger.error(
                                f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                            )
                            query.message.edit_media(
                                media=InputMediaPhoto(
                                    "https://artworks.thetvdb.com/banners/images/missing/movie.jpg"
                                ),
                                reply_markup=reply_markup,
                            )
                        else:
                            raise
                    query.bot.edit_message_caption(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        caption=reply_message,
                        reply_markup=reply_markup,
                    )
                    query.answer()
                    return
                elif len(paths) == 1:
                    logger.debug(
                        f"Only one root folder enabled. Adding/Updating additional data for cid=[{cid}], key=[p], value=[{paths[0]['id']}]..."
                    )
                    self._update_add_data(cid, "p", paths[0]["path"])
                else:
                    self._delete_conversation(cid)
                    query.message.reply_text(
                        f"Error adding {convo['type']}: no root folders enabled for {'Sonarr' if convo['type'] == 'series' else 'Radarr'}! Please check your Searcharr configuration and try again."
                    )
                    query.message.delete()
                    query.answer()
                    return
            else:
                try:
                    int(additional_data.get("p"))
                except ValueError:
                    # Value is already the full path
                    pass
                else:
                    # Translate id to actual path
                    path = next(
                        (
                            p["path"]
                            for p in paths
                            if p["id"] == int(additional_data["p"])
                        ),
                        None,
                    )
                    logger.debug(
                        f"Path id [{additional_data['p']}] lookup result: [{path}]"
                    )
                    if path:
                        self._update_add_data(cid, "p", path)

            if not additional_data.get("q"):
                quality_profiles = (
                    self.sonarr._quality_profiles
                    if convo["type"] == "series"
                    else self.radarr._quality_profiles
                )
                if len(quality_profiles) > 1:
                    # prepare response to prompt user to select quality profile, and return
                    reply_message, reply_markup = self._prepare_response(
                        convo["type"],
                        r,
                        cid,
                        i,
                        len(convo["results"]),
                        add=True,
                        quality_profiles=quality_profiles,
                    )
                    try:
                        query.message.edit_media(
                            media=InputMediaPhoto(r["remotePoster"]),
                            reply_markup=reply_markup,
                        )
                    except BadRequest as e:
                        if str(e) == "Wrong type of the web page content":
                            logger.error(
                                f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                            )
                            query.message.edit_media(
                                media=InputMediaPhoto(
                                    "https://artworks.thetvdb.com/banners/images/missing/movie.jpg"
                                ),
                                reply_markup=reply_markup,
                            )
                        else:
                            raise
                    query.bot.edit_message_caption(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        caption=reply_message,
                        reply_markup=reply_markup,
                    )
                    query.answer()
                    return
                elif len(quality_profiles) == 1:
                    logger.debug(
                        f"Only one quality profile enabled. Adding/Updating additional data for cid=[{cid}], key=[q], value=[{quality_profiles[0]['id']}]..."
                    )
                    self._update_add_data(cid, "q", quality_profiles[0]["id"])
                else:
                    self._delete_conversation(cid)
                    query.message.reply_text(
                        f"Error adding {convo['type']}: no quality profiles enabled for {'Sonarr' if convo['type'] == 'series' else 'Radarr'}! Please check your Searcharr configuration and try again."
                    )
                    query.message.delete()
                    query.answer()
                    return

            if (
                convo["type"] == "series"
                and settings.sonarr_season_monitor_prompt
                and additional_data.get("m", False) is False
            ):
                # m = monitor season(s)
                monitor_options = [
                    "All Seasons",
                    "First Season Only",
                    "Latest Season Only",
                ]
                # prepare response to prompt user to select quality profile, and return
                reply_message, reply_markup = self._prepare_response(
                    convo["type"],
                    r,
                    cid,
                    i,
                    len(convo["results"]),
                    add=True,
                    monitor_options=monitor_options,
                )
                try:
                    query.message.edit_media(
                        media=InputMediaPhoto(r["remotePoster"]),
                        reply_markup=reply_markup,
                    )
                except BadRequest as e:
                    if str(e) == "Wrong type of the web page content":
                        logger.error(
                            f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                        )
                        query.message.edit_media(
                            media=InputMediaPhoto(
                                "https://artworks.thetvdb.com/banners/images/missing/movie.jpg"
                            ),
                            reply_markup=reply_markup,
                        )
                    else:
                        raise
                query.bot.edit_message_caption(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
                query.answer()
                return

            if convo["type"] == "series":
                all_tags = self.sonarr.get_filtered_tags(
                    settings.sonarr_user_selectable_tags
                )
                allow_user_to_select_tags = settings.sonarr_allow_user_to_select_tags
                forced_tags = settings.sonarr_forced_tags
            elif convo["type"] == "movie":
                all_tags = self.radarr.get_filtered_tags(
                    settings.radarr_user_selectable_tags
                )
                allow_user_to_select_tags = settings.radarr_allow_user_to_select_tags
                forced_tags = settings.radarr_forced_tags
            if allow_user_to_select_tags and not additional_data.get("td"):
                if not len(all_tags):
                    logger.warning(
                        f"User tagging is enabled, but no tags found. Make sure there are tags in {'Sonarr' if convo['type'] == 'series' else 'Radarr'} matching your Searcharr configuration."
                    )
                elif not additional_data.get("tt"):
                    reply_message, reply_markup = self._prepare_response(
                        convo["type"],
                        r,
                        cid,
                        i,
                        len(convo["results"]),
                        add=True,
                        tags=all_tags,
                    )
                    try:
                        query.message.edit_media(
                            media=InputMediaPhoto(r["remotePoster"]),
                            reply_markup=reply_markup,
                        )
                    except BadRequest as e:
                        if str(e) == "Wrong type of the web page content":
                            logger.error(
                                f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
                            )
                            query.message.edit_media(
                                media=InputMediaPhoto(
                                    "https://artworks.thetvdb.com/banners/images/missing/movie.jpg"
                                ),
                                reply_markup=reply_markup,
                            )
                        else:
                            raise
                    query.bot.edit_message_caption(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        caption=reply_message,
                        reply_markup=reply_markup,
                    )
                    query.answer()
                    return
                else:
                    tag_ids = (
                        additional_data.get("t", "").split(",")
                        if len(additional_data.get("t", ""))
                        else []
                    )
                    tag_ids.append(additional_data["tt"])
                    logger.debug(f"Adding tag [{additional_data['tt']}]")
                    self._update_add_data(cid, "t", ",".join(tag_ids))
                    return

            tags = (
                additional_data.get("t").split(",")
                if len(additional_data.get("t", ""))
                else []
            )
            logger.debug(f"{tags=}")
            if convo["type"] == "series":
                get_tag_id = self.sonarr.get_tag_id
                tag_with_username = settings.sonarr_tag_with_username
            elif convo["type"] == "movie":
                get_tag_id = self.radarr.get_tag_id
                tag_with_username = settings.radarr_tag_with_username
            if tag_with_username:
                tag = f"searcharr-{query.from_user.username if query.from_user.username else query.from_user.id}"
                if tag_id := get_tag_id(tag):
                    tags.append(str(tag_id))
                else:
                    self.logger.warning(
                        f"Tag lookup/creation failed for [{tag}]. This tag will not be added to the {convo['type']}."
                    )
            for tag in forced_tags:
                if tag_id := get_tag_id(tag):
                    tags.append(str(tag_id))
                else:
                    self.logger.warning(
                        f"Tag lookup/creation failed for forced tag [{tag}]. This tag will not be added to the {convo['type']}."
                    )
            self._update_add_data(cid, "t", ",".join(list(set(tags))))

            logger.debug("All data is accounted for, proceeding to add...")
            try:
                if convo["type"] == "series":
                    added = self.sonarr.add_series(
                        series_info=r,
                        monitored=settings.sonarr_add_monitored,
                        search=settings.sonarr_search_on_add,
                        additional_data=self._get_add_data(cid),
                    )
                elif convo["type"] == "movie":
                    added = self.radarr.add_movie(
                        movie_info=r,
                        monitored=settings.radarr_add_monitored,
                        search=settings.radarr_search_on_add,
                        min_avail=settings.radarr_min_availability,
                        additional_data=self._get_add_data(cid),
                    )
                else:
                    added = False
            except Exception as e:
                logger.error(f"Error adding {convo['type']}: {e}")
                added = False
            logger.debug(f"Result of attempt to add {convo['type']}: {added}")
            if added:
                self._delete_conversation(cid)
                query.message.reply_text(f"Successfully added {r['title']}!")
                query.message.delete()
            else:
                query.message.reply_text(
                    f"Unspecified error encountered while adding {convo['type']}!"
                )
        elif op == "remove_user":
            if auth_level != 2:
                query.message.reply_text(
                    "You do not have admin permissions... Please authenticate with `/start <admin password>` and then try again."
                )
                query.message.delete()
                query.answer()
                return
            try:
                self._remove_user(i)
                # query.message.reply_text(
                #    f"Successfully removed all access for user id [{i}]!"
                # )
                # self._delete_conversation(cid)
                # query.message.delete()
                convo.update({"results": self._get_users()})
                self._create_conversation(
                    id=cid,
                    username=str(query.message.from_user.username),
                    kind="users",
                    results=convo["results"],
                )
                reply_message, reply_markup = self._prepare_response_users(
                    cid,
                    convo["results"],
                    0,
                    5,
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"Successfully removed all access for user id [{i}]! "
                    + reply_message,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(f"Error removing all access for user id [{i}]: {e}")
                query.message.reply_text(
                    f"Unspecified error encountered while removing user id [{i}]!"
                )
        elif op == "make_admin":
            if auth_level != 2:
                query.message.reply_text(
                    "You do not have admin permissions... Please authenticate with `/start <admin password>` and then try again."
                )
                query.message.delete()
                query.answer()
                return
            try:
                self._update_admin_access(i, 1)
                # query.message.reply_text(f"Added admin access for user id [{i}]!")
                # self._delete_conversation(cid)
                # query.message.delete()
                convo.update({"results": self._get_users()})
                self._create_conversation(
                    id=cid,
                    username=str(query.message.from_user.username),
                    kind="users",
                    results=convo["results"],
                )
                reply_message, reply_markup = self._prepare_response_users(
                    cid,
                    convo["results"],
                    0,
                    5,
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"Added admin access for user id [{i}]! " + reply_message,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(f"Error adding admin access for user id [{i}]: {e}")
                query.message.reply_text(
                    f"Unspecified error encountered while adding admin access for user id [{i}]!"
                )
        elif op == "remove_admin":
            if auth_level != 2:
                query.message.reply_text(
                    "You do not have admin permissions... Please authenticate with `/start <admin password>` and then try again."
                )
                query.message.delete()
                query.answer()
                return
            try:
                self._update_admin_access(i, "")
                # query.message.reply_text(f"Removed admin access for user id [{i}]!")
                # self._delete_conversation(cid)
                # query.message.delete()
                convo.update({"results": self._get_users()})
                self._create_conversation(
                    id=cid,
                    username=str(query.message.from_user.username),
                    kind="users",
                    results=convo["results"],
                )
                reply_message, reply_markup = self._prepare_response_users(
                    cid,
                    convo["results"],
                    0,
                    5,
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"Removed admin access for user id [{i}]! " + reply_message,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(f"Error removing admin access for user id [{i}]: {e}")
                query.message.reply_text(
                    f"Unspecified error encountered while removing admin access for user id [{i}]!"
                )

        query.answer()

    def _prepare_response(
        self,
        kind,
        r,
        cid,
        i,
        total_results,
        add=False,
        paths=None,
        quality_profiles=None,
        monitor_options=None,
        tags=None,
    ):
        keyboard = []
        keyboardNavRow = []
        if i > 0:
            keyboardNavRow.append(
                InlineKeyboardButton("< Prev", callback_data=f"{cid}^^^{i}^^^prev")
            )
        if kind == "series" and r["tvdbId"]:
            keyboardNavRow.append(
                InlineKeyboardButton(
                    "tvdb", url=f"https://thetvdb.com/series/{r['titleSlug']}"
                )
            )
        elif kind == "movie" and r["tmdbId"]:
            keyboardNavRow.append(
                InlineKeyboardButton(
                    "TMDB", url=f"https://www.themoviedb.org/movie/{r['tmdbId']}"
                )
            )
        if r["imdbId"]:
            keyboardNavRow.append(
                InlineKeyboardButton(
                    "IMDb", url=f"https://imdb.com/title/{r['imdbId']}"
                )
            )
        if total_results > 1 and i < total_results - 1:
            keyboardNavRow.append(
                InlineKeyboardButton("Next >", callback_data=f"{cid}^^^{i}^^^next")
            )
        keyboard.append(keyboardNavRow)

        if add:
            if tags:
                for tag in tags[:12]:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"Add Tag: {tag['label']}",
                                callback_data=f"{cid}^^^{i}^^^add^^tt={tag['id']}",
                            )
                        ],
                    )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "Finished Tagging",
                            callback_data=f"{cid}^^^{i}^^^add^^td=1",
                        )
                    ],
                )
            elif monitor_options:
                for k, o in enumerate(monitor_options):
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"Monitor {o}",
                                callback_data=f"{cid}^^^{i}^^^add^^m={k}",
                            )
                        ],
                    )
            elif quality_profiles:
                for q in quality_profiles:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"Add Quality: {q['name']}",
                                callback_data=f"{cid}^^^{i}^^^add^^q={q['id']}",
                            )
                        ],
                    )
            elif paths:
                for p in paths:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"Add to {p['path']}",
                                callback_data=f"{cid}^^^{i}^^^add^^p={p['id']}",
                            )
                        ],
                    )

        keyboardActRow = []
        if not add:
            if not r["id"]:
                keyboardActRow.append(
                    InlineKeyboardButton(
                        f"Add {kind.title()}!", callback_data=f"{cid}^^^{i}^^^add"
                    ),
                )
            else:
                keyboardActRow.append(
                    InlineKeyboardButton(
                        "Already Added!", callback_data=f"{cid}^^^{i}^^^noop"
                    ),
                )
        keyboardActRow.append(
            InlineKeyboardButton(
                "Cancel Search", callback_data=f"{cid}^^^{i}^^^cancel"
            ),
        )
        if len(keyboardActRow):
            keyboard.append(keyboardActRow)
        if not add and kind == "series" and "Anime" in r["genres"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "Add Series as Anime Type!",
                        callback_data=f"{cid}^^^{i}^^^add^^st=a",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)

        if kind == "series":
            reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''} - {r['seasonCount']} Season{'s' if r['seasonCount'] != 1 else ''}{' - ' + r['network'] if r['network'] else ''} - {r['status'].title()}\n\n{r['overview']}"[
                0:1024
            ]
        elif kind == "movie":
            reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''}{' - ' + str(r['runtime']) + ' min' if r['runtime'] else ''} - {r['status'].title()}\n\n{r['overview']}"[
                0:1024
            ]
        else:
            reply_message = "Something went wrong!"

        return (reply_message, reply_markup)

    def _prepare_response_users(self, cid, users, offset, num, total_results):
        keyboard = []
        for u in users[offset : offset + num]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "Remove", callback_data=f"{cid}^^^{u['id']}^^^remove_user"
                    ),
                    InlineKeyboardButton(
                        f"{u['username'] if u['username'] != 'None' else u['id']}",
                        callback_data=f"{cid}^^^{u['id']}^^^noop",
                    ),
                    InlineKeyboardButton(
                        "Remove Admin" if u["admin"] else "Make Admin",
                        callback_data=f"{cid}^^^{u['id']}^^^{'remove_admin' if u['admin'] else 'make_admin'}",
                    ),
                ]
            )
        keyboardNavRow = []
        if offset > 0:
            keyboardNavRow.append(
                InlineKeyboardButton(
                    "< Prev", callback_data=f"{cid}^^^{offset - num}^^^prev"
                ),
            )
        keyboardNavRow.append(
            InlineKeyboardButton("Done", callback_data=f"{cid}^^^{offset}^^^done"),
        )
        if total_results > 1 and offset + num < total_results:
            keyboardNavRow.append(
                InlineKeyboardButton(
                    "Next >", callback_data=f"{cid}^^^{offset + num}^^^next"
                ),
            )
        keyboard.append(keyboardNavRow)
        reply_markup = InlineKeyboardMarkup(keyboard)

        reply_message = f"Listing Searcharr users {offset + 1}-{min(offset + num, total_results)} of {total_results}."
        return (reply_message, reply_markup)

    def handle_error(self, update, context):
        logger.error(f"Caught error: {context.error}")
        try:
            update.callback_query.answer()
        except Exception:
            pass

    def cmd_help(self, update, context):
        logger.debug(f"Received help cmd from [{update.message.from_user.username}]")
        auth_level = self._authenticated(update.message.from_user.id)
        if not auth_level:
            update.message.reply_text(
                "Please authenticate with `/start <password>` and then try again."
            )
            return
        if settings.sonarr_enabled and settings.radarr_enabled:
            resp = f'Use {" OR ".join([f"/{c} <title>" for c in settings.radarr_movie_command_aliases])} to add a movie to Radarr, and {" OR ".join([f"/{c} <title>" for c in settings.sonarr_series_command_aliases])} to add a series to Sonarr.'
        elif settings.sonarr_enabled:
            resp = f'Use {" OR ".join([f"/{c} <title>" for c in settings.sonarr_series_command_aliases])} to add a series to Sonarr.'
        elif settings.radarr_enabled:
            resp = f'Use {" OR ".join([f"/{c} <title>" for c in settings.radarr_movie_command_aliases])} to add a movie to Radarr.'
        else:
            resp = "Sorry, but all of my features are currently disabled."

        if auth_level == 2:
            resp += " Since you are an admin, you can also use /users to manage users."

        update.message.reply_text(resp)

    def _strip_entities(self, message):
        text = message.text
        entities = message.parse_entities()
        logger.debug(f"{entities=}")
        for v in entities.values():
            text = text.replace(v, "")
        text = text.replace("  ", "").strip()
        logger.debug(f"Stripped entities from message [{message.text}]: [{text}]")
        return text

    def run(self):
        self._init_db()
        updater = Updater(self.token, use_context=True)

        updater.dispatcher.add_handler(CommandHandler("help", self.cmd_help))
        updater.dispatcher.add_handler(CommandHandler("start", self.cmd_start))
        for c in settings.radarr_movie_command_aliases:
            logger.debug(f"Registering [/{c}] as a movie command")
            updater.dispatcher.add_handler(CommandHandler(c, self.cmd_movie))
        for c in settings.sonarr_series_command_aliases:
            logger.debug(f"Registering [/{c}] as a series command")
            updater.dispatcher.add_handler(CommandHandler(c, self.cmd_series))
        updater.dispatcher.add_handler(CommandHandler("users", self.cmd_users))
        updater.dispatcher.add_handler(CallbackQueryHandler(self.callback))
        if not self.DEV_MODE:
            updater.dispatcher.add_error_handler(self.handle_error)
        else:
            logger.info(
                "Developer mode is enabled; skipping registration of error handler--exceptions will be raised."
            )

        updater.start_polling()
        updater.idle()

    def _create_conversation(self, id, username, kind, results):
        con, cur = self._get_con_cur()
        q = "INSERT OR REPLACE INTO conversations (id, username, type, results) VALUES (?, ?, ?, ?)"
        qa = (id, username, kind, json.dumps(results))
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(
                f"Error executing database query to create conversation [{q}]: {e}"
            )
            raise

    def _generate_cid(self):
        q = "SELECT * FROM conversations WHERE id=?"
        con, cur = self._get_con_cur()
        while True:
            u = uuid.uuid4().hex[:8]
            try:
                r = cur.execute(q, (u,))
            except sqlite3.Error as e:
                r = None
                logger.error(
                    f"Error executing database query to check conversation id uniqueness [{q}]: {e}"
                )

            if not r:
                return None
            elif not len(r.fetchall()):
                con.close()
                return u
            else:
                logger.warning("Detected conversation id collision. Interesting.")

    def _get_conversation(self, id):
        q = "SELECT * FROM conversations WHERE id=?;"
        qa = (id,)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q, qa)
        except sqlite3.Error as e:
            r = None
            logger.error(
                f"Error executing database query to look up conversation from the database [{q}]: {e}"
            )

        if r:
            record = r.fetchone()
            if record:
                logger.debug(f"Found conversation {record['id']} in the database")
                record.update({"results": json.loads(record["results"])})
            con.close()
            return record

        logger.debug(f"Found no conversation for id [{id}]")
        return None

    def _delete_conversation(self, id):
        self._clear_add_data(id)
        q = "DELETE FROM conversations WHERE id=?;"
        qa = (id,)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            con, cur = self._get_con_cur()
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(
                f"Error executing database query to delete conversation from the database [{q}]: {e}"
            )
            return False

    def _get_add_data(self, cid):
        q = "SELECT * FROM add_data WHERE cid=?;"
        qa = (cid,)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q, qa)
        except sqlite3.Error as e:
            r = None
            logger.error(
                f"Error executing database query to look up conversation add data from the database [{q}]: {e}"
            )

        if r:
            records = r.fetchall()
            con.close()
            logger.debug(f"Query response: {records}")
            return {x["key"]: x["value"] for x in records}
        else:
            return {}

    def _update_add_data(self, cid, key, value):
        con, cur = self._get_con_cur()
        q = "INSERT OR REPLACE INTO add_data (cid, key, value) VALUES (?, ?, ?)"
        qa = (cid, key, value)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error executing database query [{q}]: {e}")
            raise

    def _clear_add_data(self, cid):
        q = "DELETE FROM add_data WHERE cid=?;"
        qa = (cid,)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            con, cur = self._get_con_cur()
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(
                f"Error executing database query to delete conversation add data from the database [{q}]: {e}"
            )
            return False

    def _add_user(self, id, username, admin=""):
        con, cur = self._get_con_cur()
        q = "INSERT OR REPLACE INTO users (id, username, admin) VALUES (?, ?, ?);"
        qa = (id, username, admin)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error executing database query [{q}]: {e}")
            raise

    def _remove_user(self, id):
        con, cur = self._get_con_cur()
        q = "DELETE FROM users where id=?;"
        qa = (id,)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error executing database query [{q}]: {e}")
            raise

    def _get_users(self, admin=False):
        adminQ = " where IFNULL(admin, '') != ''" if admin else ""
        q = f"SELECT * FROM users{adminQ};"
        logger.debug(f"Executing query: [{q}] with no args...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q)
        except sqlite3.Error as e:
            r = None
            logger.error(
                f"Error executing database query to look up users from the database [{q}]: {e}"
            )

        if r:
            records = r.fetchall()
            con.close()
            return records

        logger.debug(
            f"Found no {'admin ' if admin else ''}users in the database (this seems wrong)."
        )
        return []

    def _update_admin_access(self, user_id, admin=""):
        con, cur = self._get_con_cur()
        q = "UPDATE users set admin=? where id=?;"
        qa = (str(admin), user_id)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error executing database query [{q}]: {e}")
            raise

    def _authenticated(self, user_id):
        # Return True if user is authenticated
        # Else return False
        q = "SELECT * FROM users WHERE id=?;"
        qa = (user_id,)
        logger.debug(f"Executing query: [{q}] with args: [{qa}]...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q, qa)
        except sqlite3.Error as e:
            r = None
            logger.error(
                f"Error executing database query to look up user from the database [{q}]: {e}"
            )
            return False

        if r:
            record = r.fetchone()
            logger.debug(f"Query result for user lookup: {record}")
            con.close()
            if record and record["id"] == user_id:
                return 2 if record["admin"] else 1

        logger.debug(f"Did not find user [{user_id}] in the database.")
        return False

    def _dict_factory(self, cursor, row):
        """From sqlite3 documentation:
        https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.row_factory
        """
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _get_con_cur(self):
        # Connect to local DB and return tuple containing connection and cursor
        if not os.path.isdir(DBPATH):
            try:
                logger.debug(
                    "The data directory does not exist. Attempting to create it..."
                )
                os.mkdir(DBPATH)
            except Exception as e:
                logger.error(f"Error creating data directory: {e}.")
                raise

        try:
            con = sqlite3.connect(os.path.join(DBPATH, DBFILE), timeout=30)
            con.execute("PRAGMA journal_mode = off;")
            con.row_factory = self._dict_factory
            cur = con.cursor()
            logger.debug(
                f"Database connection established [{os.path.join(DBPATH, DBFILE)}]."
            )
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

        return (con, cur)

    def _init_db(self):
        con, cur = self._get_con_cur()
        queries = [
            """CREATE TABLE IF NOT EXISTS conversations (
                id text primary key,
                username text not null,
                type text,
                results text
            );""",
            """CREATE TABLE IF NOT EXISTS users (
                id integer primary key,
                username text not null,
                admin text,
                permissions text
            );""",
            """CREATE TABLE IF NOT EXISTS add_data (
                cid text,
                key text,
                value text,
                primary key (cid, key)
            );""",
        ]
        for q in queries:
            logger.debug(f"Executing query: [{q}] with no args...")
            try:
                with DBLOCK:
                    cur.execute(q)
            except sqlite3.Error as e:
                logger.error(f"Error executing database query [{q}]: {e}")
                raise

        con.commit()
        con.close()


if __name__ == "__main__":
    args = parse_args()
    logger = set_up_logger("searcharr", args.verbose, args.console_logging)
    tgr = Searcharr(settings.tgram_token)
    tgr.run()
