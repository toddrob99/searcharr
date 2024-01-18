"""
Searcharr
Sonarr, Radarr & Readarr Telegram Bot
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
from datetime import datetime

from telegram import InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import BadRequest
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

from log import set_up_logger
import radarr
import sonarr
import readarr
import settings
import util
from util import xlate, xlate_aliases
from commands import Command
from buttons import KeyboardButtons

__version__ = "3.2.2"

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
        util.log.info(f"Searcharr v{__version__} - Logging started!")
        self._lang = util.load_language()
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
                util.log.debug(
                    f"Looking up/validating Sonarr quality profile id for [{i}]..."
                )
                foundProfile = self.sonarr.lookup_quality_profile(i)
                if not foundProfile:
                    util.log.error(f"Sonarr quality profile id/name [{i}] is invalid!")
                else:
                    util.log.debug(
                        f"Found Sonarr quality profile for [{i}]: [{foundProfile}]"
                    )
                    quality_profiles.append(foundProfile)
            if not len(quality_profiles):
                util.log.warning(
                    f"No valid Sonarr quality profile(s) provided! Using all of the quality profiles I found in Sonarr: {self.sonarr._quality_profiles}"
                )
            else:
                util.log.debug(
                    f"Using the following Sonarr quality profile(s): {[(x['id'], x['name']) for x in quality_profiles]}"
                )
                self.sonarr._quality_profiles = quality_profiles

            root_folders = []
            if not hasattr(settings, "sonarr_series_paths"):
                settings.sonarr_series_paths = []
                util.log.warning(
                    'No sonarr_series_paths setting detected. Please set one in settings.py (sonarr_series_paths=["/path/1", "/path/2"]). Proceeding with all root folders configured in Sonarr.'
                )
            if not isinstance(settings.sonarr_series_paths, list):
                settings.sonarr_series_paths = [settings.sonarr_series_paths]
            for i in settings.sonarr_series_paths:
                util.log.debug(f"Looking up/validating Sonarr root folder for [{i}]...")
                foundPath = self.sonarr.lookup_root_folder(i)
                if not foundPath:
                    util.log.error(f"Sonarr root folder path/id [{i}] is invalid!")
                else:
                    util.log.debug(f"Found Sonarr root folder for [{i}]: [{foundPath}]")
                    root_folders.append(foundPath)
            if not len(root_folders):
                util.log.warning(
                    f"No valid Sonarr root folder(s) provided! Using all of the root folders I found in Sonarr: {self.sonarr._root_folders}"
                )
            else:
                util.log.debug(
                    f"Using the following Sonarr root folder(s): {[(x['id'], x['path']) for x in root_folders]}"
                )
                self.sonarr._root_folders = root_folders
            if not hasattr(settings, "sonarr_tag_with_username"):
                settings.sonarr_tag_with_username = True
                util.log.warning(
                    "No sonarr_tag_with_username setting found. Please add sonarr_tag_with_username to settings.py (sonarr_tag_with_username=True or sonarr_tag_with_username=False). Defaulting to True."
                )
            if not hasattr(settings, "sonarr_series_command_aliases"):
                settings.sonarr_series_command_aliases = ["series"]
                util.log.warning(
                    'No sonarr_series_command_aliases setting found. Please add sonarr_series_command_aliases to settings.py (e.g. sonarr_series_command_aliases=["series", "tv"]. Defaulting to ["series"].'
                )
            if not hasattr(settings, "sonarr_season_monitor_prompt"):
                settings.sonarr_season_monitor_prompt = False
                util.log.warning(
                    "No sonarr_season_monitor_prompt setting found. Please add sonarr_season_monitor_prompt to settings.py (e.g. sonarr_season_monitor_prompt=True if you want users to choose whether to monitor all/first/latest season(s). Defaulting to False."
                )
            if not hasattr(settings, "sonarr_forced_tags"):
                settings.sonarr_forced_tags = []
                util.log.warning(
                    'No sonarr_forced_tags setting found. Please add sonarr_forced_tags to settings.py (e.g. sonarr_forced_tags=["tag-1", "tag-2"]) if you want specific tags added to each series. Defaulting to empty list ([]).'
                )
            if not hasattr(settings, "sonarr_allow_user_to_select_tags"):
                settings.sonarr_allow_user_to_select_tags = False
                util.log.warning(
                    "No sonarr_allow_user_to_select_tags setting found. Please add sonarr_allow_user_to_select_tags to settings.py (e.g. sonarr_allow_user_to_select_tags=True) if you want users to be able to select tags when adding a series. Defaulting to False."
                )
            if not hasattr(settings, "sonarr_user_selectable_tags"):
                settings.sonarr_user_selectable_tags = []
                util.log.warning(
                    'No sonarr_user_selectable_tags setting found. Please add sonarr_user_selectable_tags to settings.py (e.g. sonarr_user_selectable_tags=["tag-1", "tag-2"]) if you want to limit the tags a user can select. Defaulting to empty list ([]), which will present the user with all tags.'
                )
            for t in settings.sonarr_user_selectable_tags:
                if t_id := self.sonarr.get_tag_id(t):
                    util.log.debug(
                        f"Tag id [{t_id}] for user-selectable Sonarr tag [{t}]"
                    )
            for t in settings.sonarr_forced_tags:
                if t_id := self.sonarr.get_tag_id(t):
                    util.log.debug(f"Tag id [{t_id}] for forced Sonarr tag [{t}]")
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
                util.log.debug(
                    f"Looking up/validating Radarr quality profile id for [{i}]..."
                )
                foundProfile = self.radarr.lookup_quality_profile(i)
                if not foundProfile:
                    util.log.error(f"Radarr quality profile id/name [{i}] is invalid!")
                else:
                    util.log.debug(
                        f"Found Radarr quality profile for [{i}]: [{foundProfile}]"
                    )
                    quality_profiles.append(foundProfile)
            if not len(quality_profiles):
                util.log.warning(
                    f"No valid Radarr quality profile(s) provided! Using all of the quality profiles I found in Radarr: {self.radarr._quality_profiles}"
                )
            else:
                util.log.debug(
                    f"Using the following Radarr quality profile(s): {[(x['id'], x['name']) for x in quality_profiles]}"
                )
                self.radarr._quality_profiles = quality_profiles

            root_folders = []
            if not hasattr(settings, "radarr_movie_paths"):
                settings.radarr_movie_paths = []
                util.log.warning(
                    'No radarr_movie_paths setting detected. Please set one in settings.py (radarr_movie_paths=["/path/1", "/path/2"]). Proceeding with all root folders configured in Radarr.'
                )
            if not isinstance(settings.radarr_movie_paths, list):
                settings.radarr_movie_paths = [settings.radarr_movie_paths]
            for i in settings.radarr_movie_paths:
                util.log.debug(f"Looking up/validating Radarr root folder for [{i}]...")
                foundPath = self.radarr.lookup_root_folder(i)
                if not foundPath:
                    util.log.error(f"Radarr root folder path/id [{i}] is invalid!")
                else:
                    util.log.debug(f"Found Radarr root folder for [{i}]: [{foundPath}]")
                    root_folders.append(foundPath)
            if not len(root_folders):
                util.log.warning(
                    f"No valid Radarr root folder(s) provided! Using all of the root folders I found in Radarr: {self.radarr._root_folders}"
                )
            else:
                util.log.debug(
                    f"Using the following Radarr root folder(s): {[(x['id'], x['path']) for x in root_folders]}"
                )
                self.radarr._root_folders = root_folders
            if not hasattr(settings, "radarr_tag_with_username"):
                settings.radarr_tag_with_username = True
                util.log.warning(
                    "No radarr_tag_with_username setting found. Please add radarr_tag_with_username to settings.py (radarr_tag_with_username=True or radarr_tag_with_username=False). Defaulting to True."
                )
            if not hasattr(settings, "radarr_min_availability"):
                settings.radarr_min_availability = "released"
                util.log.warning(
                    'No radarr_min_availability setting found. Please add radarr_min_availability to settings.py (options: "released", "announced", "inCinema"). Defaulting to "released".'
                )
            if not hasattr(settings, "radarr_movie_command_aliases"):
                settings.radarr_movie_command_aliases = ["movie"]
                util.log.warning(
                    'No radarr_movie_command_aliases setting found. Please add radarr_movie_command_aliases to settings.py (e.g. radarr_movie_command_aliases=["movie", "mv"]. Defaulting to ["movie"].'
                )
            if not hasattr(settings, "radarr_forced_tags"):
                settings.radarr_forced_tags = []
                util.log.warning(
                    'No radarr_forced_tags setting found. Please add radarr_forced_tags to settings.py (e.g. radarr_forced_tags=["tag-1", "tag-2"]) if you want specific tags added to each movie. Defaulting to empty list ([]).'
                )
            if not hasattr(settings, "radarr_allow_user_to_select_tags"):
                settings.radarr_allow_user_to_select_tags = True
                util.log.warning(
                    "No radarr_allow_user_to_select_tags setting found. Please add radarr_allow_user_to_select_tags to settings.py (e.g. radarr_allow_user_to_select_tags=False) if you do not want users to be able to select tags when adding a movie. Defaulting to True."
                )
            if not hasattr(settings, "radarr_user_selectable_tags"):
                settings.radarr_user_selectable_tags = []
                util.log.warning(
                    'No radarr_user_selectable_tags setting found. Please add radarr_user_selectable_tags to settings.py (e.g. radarr_user_selectable_tags=["tag-1", "tag-2"]) if you want to limit the tags a user can select. Defaulting to empty list ([]), which will present the user with all tags.'
                )
            for t in settings.radarr_user_selectable_tags:
                if t_id := self.radarr.get_tag_id(t):
                    util.log.debug(
                        f"Tag id [{t_id}] for user-selectable Radarr tag [{t}]"
                    )
            for t in settings.radarr_forced_tags:
                if t_id := self.radarr.get_tag_id(t):
                    util.log.debug(f"Tag id [{t_id}] for forced Radarr tag [{t}]")
        if hasattr(settings, "readarr_enabled"):
            self.readarr = (
                readarr.Readarr(
                    settings.readarr_url, settings.readarr_api_key, args.verbose
                )
                if settings.readarr_enabled
                else None
            )
        else:
            settings.readarr_enabled = False
            self.readarr = None
            util.log.warning(
                "No readarr_enabled setting found. If you want Searcharr to support Readarr, please refer to the sample settings on github and add settings for Readarr to settings.py."
            )
        if self.readarr:
            quality_profiles = []
            if not isinstance(settings.readarr_quality_profile_id, list):
                settings.readarr_quality_profile_id = [
                    settings.readarr_quality_profile_id
                ]
            for i in settings.readarr_quality_profile_id:
                util.log.debug(
                    f"Looking up/validating Readarr quality profile id for [{i}]..."
                )
                foundProfile = self.readarr.lookup_quality_profile(i)
                if not foundProfile:
                    util.log.error(f"Readarr quality profile id/name [{i}] is invalid!")
                else:
                    util.log.debug(
                        f"Found Readarr quality profile for [{i}]: [{foundProfile}]"
                    )
                    quality_profiles.append(foundProfile)
            if not len(quality_profiles):
                util.log.warning(
                    f"No valid Readarr quality profile(s) provided! Using all of the quality profiles I found in Readarr: {self.readarr._quality_profiles}"
                )
            else:
                util.log.debug(
                    f"Using the following Readarr quality profile(s): {[(x['id'], x['name']) for x in quality_profiles]}"
                )
                self.readarr._quality_profiles = quality_profiles
            metadata_profiles = []
            if not isinstance(settings.readarr_metadata_profile_id, list):
                settings.readarr_metadata_profile_id = [
                    settings.readarr_metadata_profile_id
                ]
            for i in settings.readarr_metadata_profile_id:
                util.log.debug(
                    f"Looking up/validating Readarr metadata profile id for [{i}]..."
                )
                foundProfile = self.readarr.lookup_metadata_profile(i)
                if not foundProfile:
                    util.log.error(f"Readarr metadata profile id/name [{i}] is invalid!")
                else:
                    util.log.debug(
                        f"Found Readarr metadata profile for [{i}]: [{foundProfile}]"
                    )
                    metadata_profiles.append(foundProfile)
            if not len(metadata_profiles):
                util.log.warning(
                    f"No valid Readarr metadata profile(s) provided! Using all of the metadata profiles I found in Readarr: {self.readarr._metadata_profiles}"
                )
            else:
                util.log.debug(
                    f"Using the following Readarr metadata profile(s): {[(x['id'], x['name']) for x in metadata_profiles]}"
                )
                self.readarr._metadata_profiles = metadata_profiles

            root_folders = []
            if not hasattr(settings, "readarr_book_paths"):
                settings.readarr_book_paths = []
                util.log.warning(
                    'No readarr_book_paths setting detected. Please set one in settings.py (readarr_book_paths=["/path/1", "/path/2"]). Proceeding with all root folders configured in Readarr.'
                )
            if not isinstance(settings.readarr_book_paths, list):
                settings.readarr_book_paths = [settings.readarr_book_paths]
            for i in settings.readarr_book_paths:
                util.log.debug(f"Looking up/validating Readarr root folder for [{i}]...")
                foundPath = self.readarr.lookup_root_folder(i)
                if not foundPath:
                    util.log.error(f"Readarr root folder path/id [{i}] is invalid!")
                else:
                    util.log.debug(f"Found Readarr root folder for [{i}]: [{foundPath}]")
                    root_folders.append(foundPath)
            if not len(root_folders):
                util.log.warning(
                    f"No valid Readarr root folder(s) provided! Using all of the root folders I found in Readarr: {self.readarr._root_folders}"
                )
            else:
                util.log.debug(
                    f"Using the following Readarr root folder(s): {[(x['id'], x['path']) for x in root_folders]}"
                )
                self.readarr._root_folders = root_folders
            if not hasattr(settings, "readarr_tag_with_username"):
                settings.readarr_tag_with_username = True
                util.log.warning(
                    "No readarr_tag_with_username setting found. Please add readarr_tag_with_username to settings.py (readarr_tag_with_username=True or readarr_tag_with_username=False). Defaulting to True."
                )
            if not hasattr(settings, "readarr_book_command_aliases"):
                settings.readarr_book_command_aliases = ["book"]
                util.log.warning(
                    'No readarr_book_command_aliases setting found. Please add readarr_book_command_aliases to settings.py (e.g. readarr_book_command_aliases=["book", "bk"]. Defaulting to ["book"].'
                )
            if not hasattr(settings, "readarr_forced_tags"):
                settings.readarr_forced_tags = []
                util.log.warning(
                    'No readarr_forced_tags setting found. Please add readarr_forced_tags to settings.py (e.g. readarr_forced_tags=["tag-1", "tag-2"]) if you want specific tags added to each book. Defaulting to empty list ([]).'
                )
            if not hasattr(settings, "readarr_allow_user_to_select_tags"):
                settings.readarr_allow_user_to_select_tags = True
                util.log.warning(
                    "No readarr_allow_user_to_select_tags setting found. Please add readarr_allow_user_to_select_tags to settings.py (e.g. readarr_allow_user_to_select_tags=False) if you do not want users to be able to select tags when adding a book. Defaulting to True."
                )
            if not hasattr(settings, "readarr_user_selectable_tags"):
                settings.readarr_user_selectable_tags = []
                util.log.warning(
                    'No readarr_user_selectable_tags setting found. Please add readarr_user_selectable_tags to settings.py (e.g. readarr_user_selectable_tags=["tag-1", "tag-2"]) if you want to limit the tags a user can select. Defaulting to empty list ([]), which will present the user with all tags.'
                )
            for t in settings.readarr_user_selectable_tags:
                if t_id := self.readarr.get_tag_id(t):
                    util.log.debug(
                        f"Tag id [{t_id}] for user-selectable Readarr tag [{t}]"
                    )
            for t in settings.readarr_forced_tags:
                if t_id := self.readarr.get_tag_id(t):
                    util.log.debug(f"Tag id [{t_id}] for forced Readarr tag [{t}]")

        self.conversations = {}
        if not hasattr(settings, "searcharr_admin_password"):
            settings.searcharr_admin_password = uuid.uuid4().hex
            util.log.warning(
                f'No admin password detected. Please set one in settings.py (searcharr_admin_password="your admin password"). Using {settings.searcharr_admin_password} as the admin password for this session.'
            )
        if settings.searcharr_password == "":
            util.log.warning(
                'Password is blank. This will allow anyone to add series/movies/books using your bot. If this is unexpected, set a password in settings.py (searcharr_password="your password").'
            )
        if not hasattr(settings, "searcharr_start_command_aliases"):
            settings.searcharr_start_command_aliases = ["start"]
            util.log.warning(
                'No searcharr_start_command_aliases setting found. Please add searcharr_start_command_aliases to settings.py (e.g. searcharr_start_command_aliases=["start"]. Defaulting to ["start"].'
            )
        if not hasattr(settings, "searcharr_help_command_aliases"):
            settings.searcharr_help_command_aliases = ["help"]
            util.log.warning(
                'No searcharr_help_command_aliases setting found. Please add searcharr_help_command_aliases to settings.py (e.g. searcharr_help_command_aliases=["help"]. Defaulting to ["help"].'
            )
        if not hasattr(settings, "searcharr_users_command_aliases"):
            settings.searcharr_users_command_aliases = ["users"]
            util.log.warning(
                'No searcharr_users_command_aliases setting found. Please add searcharr_users_command_aliases to settings.py (e.g. searcharr_users_command_aliases=["users"]. Defaulting to ["users"].'
            )

    def callback(self, update, context):
        query = update.callback_query
        util.log.debug(
            f"Received callback from [{query.from_user.username}]: [{query.data}]"
        )
        auth_level = self._authenticated(query.from_user.id)
        if not auth_level:
            query.message.reply_text(
                xlate_aliases("auth_required", settings.searcharr_start_command_aliases, "password")
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
            query.message.reply_text(xlate("convo_not_found"))
            query.message.delete()
            query.answer()
            return

        cid, i, op = query.data.split("^^^")
        if "^^" in op:
            op, op_flags = op.split("^^")
            op_flags = dict(parse_qsl(op_flags))
            if op == "add":
                for k, v in op_flags.items():
                    util.log.debug(
                        f"Adding/Updating additional data for cid=[{cid}], key=[{k}], value=[{v}]..."
                    )
                    self._update_add_data(cid, k, v)
        i = int(i)
        if op == "noop":
            pass
        elif op == "cancel":
            self._delete_conversation(cid)
            query.message.reply_text(xlate("search_canceled"))
            query.message.delete()
        elif op == "done":
            self._delete_conversation(cid)
            query.message.delete()
        elif op == "prev":
            if convo["type"] in ["series", "movie", "book"]:
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
                    if str(e) in self._bad_request_poster_error_messages:
                        util.log.error(
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
                    i - 1,
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=reply_message,
                    reply_markup=reply_markup,
                )
        elif op == "next":
            if convo["type"] in ["series", "movie", "book"]:
                if i >= len(convo["results"]):
                    query.answer()
                    return
                r = convo["results"][i + 1]
                util.log.debug(f"{r=}")
                reply_message, reply_markup = self._prepare_response(
                    convo["type"], r, cid, i + 1, len(convo["results"])
                )
                try:
                    query.message.edit_media(
                        media=InputMediaPhoto(r["remotePoster"]),
                        reply_markup=reply_markup,
                    )
                except BadRequest as e:
                    if str(e) in self._bad_request_poster_error_messages:
                        util.log.error(
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
                # if i >= len(convo["results"])/5:
                #    query.answer()
                #    return
                reply_message, reply_markup = self._prepare_response_users(
                    cid,
                    convo["results"],
                    i + 1,
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
            util.log.debug(f"{additional_data=}")
            paths = (
                self.sonarr._root_folders
                if convo["type"] == "series"
                else self.radarr._root_folders
                if convo["type"] == "movie"
                else self.readarr._root_folders
                if convo["type"] == "book"
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
                        if str(e) in self._bad_request_poster_error_messages:
                            util.log.error(
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
                    util.log.debug(
                        f"Only one root folder enabled. Adding/Updating additional data for cid=[{cid}], key=[p], value=[{paths[0]['id']}]..."
                    )
                    self._update_add_data(cid, "p", paths[0]["path"])
                else:
                    self._delete_conversation(cid)
                    query.message.reply_text(
                        xlate(
                            "no_root_folders",
                            kind=xlate(convo["type"]),
                            app="Sonarr"
                            if convo["type"] == "series"
                            else "Radarr"
                            if convo["type"] == "movie"
                            else "Readarr"
                            if convo["type"] == "book"
                            else "???",
                        )
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
                    util.log.debug(
                        f"Path id [{additional_data['p']}] lookup result: [{path}]"
                    )
                    if path:
                        self._update_add_data(cid, "p", path)

            if not additional_data.get("q"):
                quality_profiles = (
                    self.sonarr._quality_profiles
                    if convo["type"] == "series"
                    else self.radarr._quality_profiles
                    if convo["type"] == "movie"
                    else self.readarr._quality_profiles
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
                        if str(e) in self._bad_request_poster_error_messages:
                            util.log.error(
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
                    util.log.debug(
                        f"Only one quality profile enabled. Adding/Updating additional data for cid=[{cid}], key=[q], value=[{quality_profiles[0]['id']}]..."
                    )
                    self._update_add_data(cid, "q", quality_profiles[0]["id"])
                else:
                    self._delete_conversation(cid)
                    query.message.reply_text(
                        xlate(
                            "no_quality_profiles",
                            kind=xlate(convo["type"]),
                            app="Sonarr"
                            if convo["type"] == "series"
                            else "Radarr"
                            if convo["type"] == "movie"
                            else "Readarr",
                        )
                    )
                    query.message.delete()
                    query.answer()
                    return

            if convo["type"] == "book" and not additional_data.get("m"):
                metadata_profiles = self.readarr._metadata_profiles
                if len(metadata_profiles) > 1:
                    # prepare response to prompt user to select quality profile, and return
                    reply_message, reply_markup = self._prepare_response(
                        convo["type"],
                        r,
                        cid,
                        i,
                        len(convo["results"]),
                        add=True,
                        metadata_profiles=metadata_profiles,
                    )
                    try:
                        query.message.edit_media(
                            media=InputMediaPhoto(r["remotePoster"]),
                            reply_markup=reply_markup,
                        )
                    except BadRequest as e:
                        if str(e) in self._bad_request_poster_error_messages:
                            util.log.error(
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
                elif len(metadata_profiles) == 1:
                    util.log.debug(
                        f"Only one metadata profile enabled. Adding/Updating additional data for cid=[{cid}], key=[m], value=[{metadata_profiles[0]['id']}]..."
                    )
                    self._update_add_data(cid, "m", metadata_profiles[0]["id"])
                else:
                    self._delete_conversation(cid)
                    query.message.reply_text(
                        xlate(
                            "no_metadata_profiles",
                            kind=xlate(convo["type"]),
                            app="Sonarr"
                            if convo["type"] == "series"
                            else "Radarr"
                            if convo["type"] == "movie"
                            else "Readarr",
                        )
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
                    xlate("all_seasons"),
                    xlate("first_season"),
                    xlate("latest_season"),
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
                    if str(e) in self._bad_request_poster_error_messages:
                        util.log.error(
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
                    settings.sonarr_user_selectable_tags,
                    settings.sonarr_forced_tags,
                )
                allow_user_to_select_tags = settings.sonarr_allow_user_to_select_tags
                forced_tags = settings.sonarr_forced_tags
            elif convo["type"] == "movie":
                all_tags = self.radarr.get_filtered_tags(
                    settings.radarr_user_selectable_tags,
                    settings.radarr_forced_tags,
                )
                allow_user_to_select_tags = settings.radarr_allow_user_to_select_tags
                forced_tags = settings.radarr_forced_tags
            elif convo["type"] == "book":
                all_tags = self.readarr.get_filtered_tags(
                    settings.readarr_user_selectable_tags,
                    settings.readarr_forced_tags,
                )
                allow_user_to_select_tags = settings.readarr_allow_user_to_select_tags
                forced_tags = settings.readarr_forced_tags
            if allow_user_to_select_tags and not additional_data.get("td"):
                if not len(all_tags):
                    util.log.warning(
                        f"User tagging is enabled, but no tags found. Make sure there are tags{' in Sonarr' if convo['type'] == 'series' else ' in Radarr' if convo['type'] == 'movie' else ' in Readarr' if convo['type'] == 'book' else ''} matching your Searcharr configuration."
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
                        if str(e) in self._bad_request_poster_error_messages:
                            util.log.error(
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
                    util.log.debug(f"Adding tag [{additional_data['tt']}]")
                    self._update_add_data(cid, "t", ",".join(tag_ids))
                    return

            tags = (
                additional_data.get("t").split(",")
                if len(additional_data.get("t", ""))
                else []
            )
            util.log.debug(f"{tags=}")
            if convo["type"] == "series":
                get_tag_id = self.sonarr.get_tag_id
                tag_with_username = settings.sonarr_tag_with_username
            elif convo["type"] == "movie":
                get_tag_id = self.radarr.get_tag_id
                tag_with_username = settings.radarr_tag_with_username
            elif convo["type"] == "book":
                get_tag_id = self.readarr.get_tag_id
                tag_with_username = settings.readarr_tag_with_username
            if tag_with_username:
                tag = f"searcharr-{query.from_user.username if query.from_user.username else query.from_user.id}"
                if tag_id := get_tag_id(tag):
                    tags.append(str(tag_id))
                else:
                    self.util.log.warning(
                        f"Tag lookup/creation failed for [{tag}]. This tag will not be added to the {convo['type']}."
                    )
            for tag in forced_tags:
                if tag_id := get_tag_id(tag):
                    tags.append(str(tag_id))
                else:
                    self.util.log.warning(
                        f"Tag lookup/creation failed for forced tag [{tag}]. This tag will not be added to the {convo['type']}."
                    )
            self._update_add_data(cid, "t", ",".join(list(set(tags))))

            util.log.debug("All data is accounted for, proceeding to add...")
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
                elif convo["type"] == "book":
                    added = self.readarr.add_book(
                        book_info=r,
                        monitored=settings.readarr_add_monitored,
                        search=settings.readarr_search_on_add,
                        additional_data=self._get_add_data(cid),
                    )
                else:
                    added = False
            except Exception as e:
                util.log.error(f"Error adding {convo['type']}: {e}")
                added = False
            util.log.debug(f"Result of attempt to add {convo['type']}: {added}")
            if added:
                self._delete_conversation(cid)
                query.message.reply_text(xlate("added", title=r["title"]))
                query.message.delete()
            else:
                query.message.reply_text(
                    xlate("unknown_error_adding", kind=convo["type"])
                )
        elif op == "remove_user":
            if auth_level != 2:
                query.message.reply_text(
                    xlate(
                        "admin_auth_required",
                        commands=" OR ".join(
                            [
                                f"`/{c} <{xlate('admin_password')}>`"
                                for c in settings.searcharr_start_command_aliases
                            ]
                        ),
                    )
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
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"{xlate('removed_user', user=i)} {reply_message}",
                    reply_markup=reply_markup,
                )
            except Exception as e:
                util.log.error(f"Error removing all access for user id [{i}]: {e}")
                query.message.reply_text(
                    xlate("unknown_error_removing_user", user=i)
                )
        elif op == "make_admin":
            if auth_level != 2:
                query.message.reply_text(
                    xlate(
                        "admin_auth_required",
                        commands=" OR ".join(
                            [
                                f"`/{c} <{xlate('admin_password')}>`"
                                for c in settings.searcharr_start_command_aliases
                            ]
                        ),
                    )
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
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"{xlate('added_admin_access', user=i)} {reply_message}",
                    reply_markup=reply_markup,
                )
            except Exception as e:
                util.log.error(f"Error adding admin access for user id [{i}]: {e}")
                query.message.reply_text(
                    xlate("unknown_error_adding_admin", user=i)
                )
        elif op == "remove_admin":
            if auth_level != 2:
                query.message.reply_text(
                    xlate(
                        "admin_auth_required",
                        commands=" OR ".join(
                            [
                                f"`/{c} <{xlate('admin_password')}>`"
                                for c in settings.searcharr_start_command_aliases
                            ]
                        ),
                    )
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
                    len(convo["results"]),
                )
                context.bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"{xlate('removed_admin_access', user=i)} {reply_message}",
                    reply_markup=reply_markup,
                )
            except Exception as e:
                util.log.error(f"Error removing admin access for user id [{i}]: {e}")
                query.message.reply_text(
                    xlate("unknown_error_removing_admin", user=i)
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
        metadata_profiles=None,
        monitor_options=None,
        tags=None,
    ):
        buttons = KeyboardButtons()
        keyboard = []
        keyboardNavRow = []
        if i > 0:
            keyboardNavRow.append(
                buttons.nav.prev(cid, i)
            )
        if kind == "series" and r["tvdbId"]:
            keyboardNavRow.append(
                buttons.ext.tvdb(r)
            )
        elif kind == "movie" and r["tmdbId"]:
            keyboardNavRow.append(
                buttons.ext.tmdb(r)
            )
        elif kind == "book" and r["links"]:
            for link in r["links"]:
                keyboardNavRow.append(
                    buttons.ext.link(link)
                )
        if kind == "series" or kind == "movie":
            keyboardNavRow.append(
                buttons.ext.imdb(r)
            )
        if total_results > 1 and i < total_results - 1:
            keyboardNavRow.append(
                buttons.nav.next(cid, i)
            )
        keyboard.append(keyboardNavRow)

        if add:
            if tags:
                for tag in tags[:12]:
                    keyboard.append(
                        [buttons.add.tag(tag, cid, i)]
                    )
                keyboard.append(
                    [buttons.add.finished_tagging(cid, i)]
                )
            elif monitor_options:
                for k, o in enumerate(monitor_options):
                    keyboard.append(
                        [buttons.add.monitor(o, k, cid, i)]
                    )
            elif quality_profiles:
                for q in quality_profiles:
                    keyboard.append(
                        [buttons.add.quality(q, cid, i)]
                    )
            elif metadata_profiles:
                for m in metadata_profiles:
                    keyboard.append(
                        [buttons.add.metadata(m, cid, i)]
                    )
            elif paths:
                for p in paths:
                    keyboard.append(
                        [buttons.add.path(p, cid, i)]
                    )

        keyboardActRow = []
        if not add:
            if not r["id"]:
                keyboardActRow.append(
                    buttons.act.add(kind, cid, i)
                )
            else:
                keyboardActRow.append(
                    buttons.act.already_added(cid, i)
                )
        keyboardActRow.append(
            buttons.act.cancel(cid, i)
        )
        if len(keyboardActRow):
            keyboard.append(keyboardActRow)

        if not add and kind == "series" and "Anime" in r["genres"]:
            keyboard.append([buttons.act.series_anime(cid, i)])

        reply_markup = InlineKeyboardMarkup(keyboard)

        if kind == "series":
            reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''} - {r['seasonCount']} Season{'s' if r['seasonCount'] != 1 else ''}{' - ' + r['network'] if r['network'] else ''} - {r['status'].title()}\n\n{r['overview']}"[
                0:1024
            ]
        elif kind == "movie":
            reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''}{' - ' + str(r['runtime']) + ' min' if r['runtime'] else ''} - {r['status'].title()}\n\n{r['overview']}"[
                0:1024
            ]
        elif kind == "book":
            try:
                release = datetime.strptime(
                    r["releaseDate"], "%Y-%m-%dT%H:%M:%SZ"
                ).strftime("%b %d, %Y")
            except (ValueError, TypeError):
                release = "???"
            reply_message = f"{r['author']['authorName']} - {r['title']}{' - ' + r['disambiguation'] if r['disambiguation'] else ''}{' - ' + r['seriesTitle'] if r['seriesTitle'] else ''} ({release})\n\n{r['overview']}"[
                0:1024
            ]
        else:
            reply_message = xlate("unexpected_error")

        return (reply_message, reply_markup)

    def _prepare_response_users(self, cid, users, i, total_results):
        buttons = KeyboardButtons()
        keyboard = []
        for u in users[i * 5 : (i * 5) + 5]:
            keyboard.append(
                [
                    buttons.user.remove(u, cid),
                    buttons.user.username(u, cid),
                    buttons.user.admin(u, cid),
                ]
            )
        keyboardNavRow = []
        if i > 0:
            keyboardNavRow.append(
                buttons.nav.prev(cid, i)
            )
        keyboardNavRow.append(
            buttons.nav.done(cid, i)
        )
        if total_results / 5 > 1 and (i + 1) * 5 < total_results:
            keyboardNavRow.append(
                buttons.nav.next(cid, i)
            )
        keyboard.append(keyboardNavRow)
        reply_markup = InlineKeyboardMarkup(keyboard)

        reply_message = xlate(
            "listing_users_pagination",
            page_info=f"{i * 5 + 1}-{min((i + 1) * 5, total_results)} of {total_results}",
        )
        return (reply_message, reply_markup)

    def handle_error(self, update, context):
        util.log.error(f"Caught error: {context.error}")
        try:
            update.callback_query.answer()
        except Exception:
            pass

    def run(self):
        self._init_db()
        updater = Updater(self.token, use_context=True)
        self.commands = Command._dict
        for command in self.commands.values():
            command._inject_dependency(searcharr_instance=self)
            for c in command._command_aliases:
                util.log.debug(f"Registering [/{c}] as a {command._name} command")
                updater.dispatcher.add_handler(CommandHandler(c, command._execute))

        updater.dispatcher.add_handler(CallbackQueryHandler(self.callback))
        if not self.DEV_MODE:
            updater.dispatcher.add_error_handler(self.handle_error)
        else:
            util.log.info(
                "Developer mode is enabled; skipping registration of error handler--exceptions will be raised."
            )

        updater.start_polling()
        updater.idle()

    def _create_conversation(self, id, username, kind, results):
        con, cur = self._get_con_cur()
        q = "INSERT OR REPLACE INTO conversations (id, username, type, results) VALUES (?, ?, ?, ?)"
        qa = (id, username, kind, json.dumps(results))
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(
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
                util.log.error(
                    f"Error executing database query to check conversation id uniqueness [{q}]: {e}"
                )

            if not r:
                return None
            elif not len(r.fetchall()):
                con.close()
                return u
            else:
                util.log.warning("Detected conversation id collision. Interesting.")

    def _get_conversation(self, id):
        q = "SELECT * FROM conversations WHERE id=?;"
        qa = (id,)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q, qa)
        except sqlite3.Error as e:
            r = None
            util.log.error(
                f"Error executing database query to look up conversation from the database [{q}]: {e}"
            )

        if r:
            record = r.fetchone()
            if record:
                util.log.debug(f"Found conversation {record['id']} in the database")
                record.update({"results": json.loads(record["results"])})
            con.close()
            return record

        util.log.debug(f"Found no conversation for id [{id}]")
        return None

    def _delete_conversation(self, id):
        self._clear_add_data(id)
        q = "DELETE FROM conversations WHERE id=?;"
        qa = (id,)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            con, cur = self._get_con_cur()
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(
                f"Error executing database query to delete conversation from the database [{q}]: {e}"
            )
            return False

    def _get_add_data(self, cid):
        q = "SELECT * FROM add_data WHERE cid=?;"
        qa = (cid,)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q, qa)
        except sqlite3.Error as e:
            r = None
            util.log.error(
                f"Error executing database query to look up conversation add data from the database [{q}]: {e}"
            )

        if r:
            records = r.fetchall()
            con.close()
            util.log.debug(f"Query response: {records}")
            return {x["key"]: x["value"] for x in records}
        else:
            return {}

    def _update_add_data(self, cid, key, value):
        con, cur = self._get_con_cur()
        q = "INSERT OR REPLACE INTO add_data (cid, key, value) VALUES (?, ?, ?)"
        qa = (cid, key, value)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(f"Error executing database query [{q}]: {e}")
            raise

    def _clear_add_data(self, cid):
        q = "DELETE FROM add_data WHERE cid=?;"
        qa = (cid,)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            con, cur = self._get_con_cur()
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(
                f"Error executing database query to delete conversation add data from the database [{q}]: {e}"
            )
            return False

    def _add_user(self, id, username, admin=""):
        con, cur = self._get_con_cur()
        q = "INSERT OR REPLACE INTO users (id, username, admin) VALUES (?, ?, ?);"
        qa = (id, username, admin)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(f"Error executing database query [{q}]: {e}")
            raise

    def _remove_user(self, id):
        con, cur = self._get_con_cur()
        q = "DELETE FROM users where id=?;"
        qa = (id,)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(f"Error executing database query [{q}]: {e}")
            raise

    def _get_users(self, admin=False):
        adminQ = " where IFNULL(admin, '') != ''" if admin else ""
        q = f"SELECT * FROM users{adminQ};"
        util.log.debug(f"Executing query: [{q}] with no args...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q)
        except sqlite3.Error as e:
            r = None
            util.log.error(
                f"Error executing database query to look up users from the database [{q}]: {e}"
            )

        if r:
            records = r.fetchall()
            con.close()
            return records

        util.log.debug(
            f"Found no {'admin ' if admin else ''}users in the database (this seems wrong)."
        )
        return []

    def _update_admin_access(self, user_id, admin=""):
        con, cur = self._get_con_cur()
        q = "UPDATE users set admin=? where id=?;"
        qa = (str(admin), user_id)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]")
        try:
            with DBLOCK:
                cur.execute(q, qa)
                con.commit()
                con.close()
                return True
        except sqlite3.Error as e:
            util.log.error(f"Error executing database query [{q}]: {e}")
            raise

    def _authenticated(self, user_id):
        # Return True if user is authenticated
        # Else return False
        q = "SELECT * FROM users WHERE id=?;"
        qa = (user_id,)
        util.log.debug(f"Executing query: [{q}] with args: [{qa}]...")
        try:
            con, cur = self._get_con_cur()
            r = cur.execute(q, qa)
        except sqlite3.Error as e:
            r = None
            util.log.error(
                f"Error executing database query to look up user from the database [{q}]: {e}"
            )
            return False

        if r:
            record = r.fetchone()
            util.log.debug(f"Query result for user lookup: {record}")
            con.close()
            if record and record["id"] == user_id:
                return 2 if record["admin"] else 1

        util.log.debug(f"Did not find user [{user_id}] in the database.")
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
                util.log.debug(
                    "The data directory does not exist. Attempting to create it..."
                )
                os.mkdir(DBPATH)
            except Exception as e:
                util.log.error(f"Error creating data directory: {e}.")
                raise

        try:
            con = sqlite3.connect(os.path.join(DBPATH, DBFILE), timeout=30)
            con.execute("PRAGMA journal_mode = off;")
            con.row_factory = self._dict_factory
            cur = con.cursor()
            util.log.debug(
                f"Database connection established [{os.path.join(DBPATH, DBFILE)}]."
            )
        except sqlite3.Error as e:
            util.log.error(f"Error connecting to database: {e}")
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
            util.log.debug(f"Executing query: [{q}] with no args...")
            try:
                with DBLOCK:
                    cur.execute(q)
            except sqlite3.Error as e:
                util.log.error(f"Error executing database query [{q}]: {e}")
                raise

        con.commit()
        con.close()

    _bad_request_poster_error_messages = [
        "Wrong type of the web page content",
        "Wrong file identifier/http url specified",
        "Media_empty",
    ]


if __name__ == "__main__":
    args = parse_args()
    util.log = set_up_logger("searcharr", args.verbose, args.console_logging)
    util.load_language()
    tgr = Searcharr(settings.tgram_token)
    tgr.run()
