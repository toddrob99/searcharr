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
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

from log import set_up_logger
import radarr
import sonarr
import settings

__version__ = "1.1.1"

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
    return parser.parse_args()


class Searcharr(object):
    def __init__(self, token):
        self.token = token
        logger.debug(f"Searcharr v{__version__} - Logging started!")
        self.sonarr = (
            sonarr.Sonarr(settings.sonarr_url, settings.sonarr_api_key, args.verbose)
            if settings.sonarr_enabled
            else None
        )
        self.radarr = (
            radarr.Radarr(settings.radarr_url, settings.radarr_api_key, args.verbose)
            if settings.radarr_enabled
            else None
        )
        self.conversations = {}

    def cmd_start(self, update, context):
        logger.debug(f"Received start cmd from [{update.message.from_user.username}]")
        if self._authenticated(update.message.from_user.id):
            update.message.reply_text(
                "You are already authenticated. Try /help for usage info."
            )
            return
        password = self._strip_entities(update.message)
        if password == settings.searcharr_password:
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
                "Please include the movie title in the command, e.g. `/movie Title Here`"
            )
            return
        results = self.radarr.lookup_movie(title)
        cid = uuid.uuid4().hex
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
            context.bot.sendPhoto(
                chat_id=update.message.chat.id,
                photo=r["remotePoster"],
                caption=reply_message,
                reply_markup=reply_markup,
            )

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
                "Please include the series title in the command, e.g. `/series Title Here`"
            )
            return
        results = self.sonarr.lookup_series(title)
        cid = uuid.uuid4().hex
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
            context.bot.sendPhoto(
                chat_id=update.message.chat.id,
                photo=r["remotePoster"],
                caption=reply_message,
                reply_markup=reply_markup,
            )

    def callback(self, update, context):
        query = update.callback_query
        logger.debug(
            f"Received callback from [{query.from_user.username}]: [{query.data}]"
        )
        if not self._authenticated(query.from_user.id):
            query.message.reply_text(
                "I don't seem to know you... Please authenticate with `/start <password>` and then try again."
            )
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
        i = int(i)
        if op == "noop":
            pass
        elif op == "cancel":
            self._delete_conversation(cid)
            # self.conversations.pop(cid)
            query.message.reply_text("Search canceled!")
            query.message.delete()
        elif op == "prev":
            if i <= 0:
                return
            r = convo["results"][i - 1]
            reply_message, reply_markup = self._prepare_response(
                convo["type"], r, cid, i - 1, len(convo["results"])
            )
            query.message.edit_media(
                media=InputMediaPhoto(r["remotePoster"]),
                reply_markup=reply_markup,
            )
            query.bot.edit_message_caption(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                caption=reply_message,
                reply_markup=reply_markup,
            )
        elif op == "next":
            if i >= len(convo["results"]):
                return
            r = convo["results"][i + 1]
            logger.debug(f"{r=}")
            reply_message, reply_markup = self._prepare_response(
                convo["type"], r, cid, i + 1, len(convo["results"])
            )
            query.message.edit_media(
                media=InputMediaPhoto(r["remotePoster"]),
                reply_markup=reply_markup,
            )
            query.bot.edit_message_caption(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                caption=reply_message,
                reply_markup=reply_markup,
            )
        elif op == "add":
            paths = (
                self.sonarr.get_root_folders()
                if convo["type"] == "series"
                else self.radarr.get_root_folders()
                if convo["type"] == "movie"
                else []
            )
            r = convo["results"][i]
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
                query.message.edit_media(
                    media=InputMediaPhoto(r["remotePoster"]),
                    reply_markup=reply_markup,
                )
                query.bot.edit_message_caption(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    caption=reply_message,
                    reply_markup=reply_markup,
                )
            elif len(paths) == 1:
                try:
                    if convo["type"] == "series":
                        added = self.sonarr.add_series(
                            series_info=r,
                            path=paths[0]["path"],
                            quality=settings.sonarr_quality_profile_id,
                            monitored=settings.sonarr_add_monitored,
                            search=settings.sonarr_search_on_add,
                        )
                    elif convo["type"] == "movie":
                        added = self.radarr.add_movie(
                            movie_info=r,
                            path=paths[0]["path"],
                            quality=settings.radarr_quality_profile_id,
                            monitored=settings.radarr_add_monitored,
                            search=settings.radarr_search_on_add,
                        )
                except Exception as e:
                    logger.error(f"Error adding {convo['type']}: {e}")
                    added = False
                if added:
                    self._delete_conversation(cid)
                    query.message.reply_text(f"Successfully added {r['title']}!")
                    query.message.delete()
                else:
                    query.message.reply_text(
                        f"Unspecified error encountered while adding {convo['type']}!"
                    )
            else:
                self._delete_conversation(cid)
                query.message.reply_text(
                    "Error adding series: no root folders found in Sonarr! Please check your configuration in Sonarr and try again."
                )
                query.message.delete()
        elif op.startswith("addto:"):
            r = convo["results"][i]
            path = op.split(":")[1]
            try:
                added = self.sonarr.add_series(
                    series_info=r,
                    path=path,
                    quality=settings.sonarr_quality_profile_id,
                    monitored=settings.sonarr_add_monitored,
                    search=settings.sonarr_search_on_add,
                )
            except Exception as e:
                logger.error(f"Error adding series: {e}")
                added = False
            logger.debug(f"Result of attempt to add series: {added}")
            if added:
                self._delete_conversation(cid)
                query.message.reply_text(f"Successfully added {r['title']}!")
                query.message.delete()
            else:
                query.message.reply_text(
                    f"Unspecified error encountered while adding {convo['type']}!"
                )

        query.answer()

    def _prepare_response(self, kind, r, cid, i, total_results, add=False, paths=None):
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
            if not paths and kind == "series":
                paths = self.sonarr.get_root_folders()
            elif not paths and kind == "movie":
                paths = self.radarr.get_root_folders()
            for p in paths:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"Add to {p['path']}",
                            callback_data=f"{cid}^^^{i}^^^addto:{p['path']}",
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

    def handle_error(self, update, context):
        logger.error(f"Caught error: {context.error}")
        try:
            update.callback_query.answer()
        except Exception:
            pass

    def cmd_help(self, update, context):
        logger.debug(f"Received help cmd from [{update.message.from_user.username}]")
        if not self._authenticated(update.message.from_user.id):
            update.message.reply_text(
                "Please authenticate with `/start <password>` and then try again."
            )
            return
        if settings.sonarr_enabled and settings.radarr_enabled:
            update.message.reply_text(
                "Use /movie <title> to add a movie to Radarr, and /series <title> to add a series to Sonarr."
            )
        elif settings.sonarr_enabled:
            update.message.reply_text("Use /series <title> to add a series to Sonarr.")
        elif settings.radarr_enabled:
            update.message.reply_text("Use /movie <title> to add a movie to Radarr.")
        else:
            update.message.reply_text(
                "Sorry, but all of my features are currently disabled."
            )

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
        updater.dispatcher.add_handler(CommandHandler("movie", self.cmd_movie))
        updater.dispatcher.add_handler(CommandHandler("series", self.cmd_series))
        updater.dispatcher.add_handler(CallbackQueryHandler(self.callback))
        # updater.dispatcher.add_error_handler(self.handle_error)

        updater.start_polling()
        updater.idle()

    def _create_conversation(self, id, username, kind, results):
        con, cur = self._get_con_cur()
        q = "INSERT INTO conversations (id, username, type, results) VALUES (?, ?, ?, ?)"
        qa = (id, username, kind, json.dumps(results))
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
                f"Error executing database query to look up conversation from the database [{q}]: {e}"
            )
            return False

    def _add_user(self, id, username):
        con, cur = self._get_con_cur()
        q = "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)"
        qa = (id, username)
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
                f"Error executing database query to look up conversation from the database [{q}]: {e}"
            )
            return False

        if r:
            record = r.fetchone()
            logger.debug(f"Query result for conversation lookup: {record}")
            con.close()
            if record and record["id"] == user_id:
                return True

        logger.debug(f"Did not find user [{id}] in the database.")
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
        q = """CREATE TABLE IF NOT EXISTS conversations (
            id text primary key,
            username text not null,
            type text,
            results text
        );"""
        logger.debug(f"Executing query: [{q}] with no args...")
        try:
            with DBLOCK:
                cur.execute(q)
        except sqlite3.Error as e:
            logger.error(f"Error executing database query [{q}]: {e}")
            raise

        q = """CREATE TABLE IF NOT EXISTS users (
            id integer primary key,
            username text not null,
            admin text,
            permissions text
        );"""
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
