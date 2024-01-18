from util import xlate
from telegram import InlineKeyboardButton


class NavButtons(object):
    def prev(self, cid, i):
        return InlineKeyboardButton(
            xlate("prev_button"), callback_data=f"{cid}^^^{i}^^^prev"
        )

    def next(self, cid, i, total_results):
        return InlineKeyboardButton(
            xlate("next_button"), callback_data=f"{cid}^^^{i}^^^next"
        )
        
    def done(self, cid, i):
        return InlineKeyboardButton(
            xlate("done"), callback_data=f"{cid}^^^{i}^^^done"
        )

class ExternalButtons(object):
    def imdb(self, r):
        return InlineKeyboardButton(
            "IMDb", url=f"https://imdb.com/title/{r['imdbId']}"
        )

    def tvdb(self, r):
        return InlineKeyboardButton(
            "tvdb", url=f"https://thetvdb.com/series/{r['titleSlug']}"
        )

    def tmdb(self, r):
        return InlineKeyboardButton(
            "TMDB", url=f"https://www.themoviedb.org/movie/{r['tmdbId']}"
        )
        
    def link(self, link):
        return InlineKeyboardButton(
            link["name"], url=link["url"]
        )

class ActionButtons(object):
    def add(self, kind, cid, i):
        InlineKeyboardButton(
            xlate("add_button", kind=xlate(kind).title()),
            callback_data=f"{cid}^^^{i}^^^add",
        ),

    def already_added(self, cid, i):
        return InlineKeyboardButton(
            xlate("already_added_button"),
            callback_data=f"{cid}^^^{i}^^^noop",
        )
    
    def cancel(self, cid, i):
        return InlineKeyboardButton(
            xlate("cancel_search_button"),
            callback_data=f"{cid}^^^{i}^^^cancel",
        )
    
    def series_anime(self, cid, i):
        return InlineKeyboardButton(
            xlate("add_series_anime_button"),
            callback_data=f"{cid}^^^{i}^^^add^^st=a",
        )
    
class AddButtons(object):
    def tag(self, tag, cid, i):
        return InlineKeyboardButton(
            xlate("add_tag_button", tag=tag["label"]),
            callback_data=f"{cid}^^^{i}^^^add^^tt={tag['id']}",
        )
    
    def finished_tagging(self, cid, i):
        return InlineKeyboardButton(
            xlate("finished_tagging_button"),
            callback_data=f"{cid}^^^{i}^^^add^^td=1",
        )
    
    def monitor(self, o, k, cid, i):
        return InlineKeyboardButton(
            xlate("monitor_button", option=o),
            callback_data=f"{cid}^^^{i}^^^add^^m={k}",
        )
    
    def quality(self, q, cid, i):
        return InlineKeyboardButton(
            xlate("add_quality_button", quality=q["name"]),
            callback_data=f"{cid}^^^{i}^^^add^^q={q['id']}",
        )
    
    def metadata(self, m, cid, i):
        return InlineKeyboardButton(
            xlate("add_metadata_button", metadata=m["name"]),
            callback_data=f"{cid}^^^{i}^^^add^^m={m['id']}",
        )
    
    def path(self, p, cid, i):
        return InlineKeyboardButton(
            xlate("add_path_button", path=p["path"]),
            callback_data=f"{cid}^^^{i}^^^add^^p={p['id']}",
        )

class UserButtons(object):
    def remove(self, u, cid):
        return InlineKeyboardButton(
            xlate("remove_user_button"),
            callback_data=f"{cid}^^^{u['id']}^^^remove_user",
        )
    
    def username(self, u, cid):
        return InlineKeyboardButton(
            f"{u['username'] if u['username'] != 'None' else u['id']}",
            callback_data=f"{cid}^^^{u['id']}^^^noop",
        )
    
    def admin(self, u, cid):
        return InlineKeyboardButton(
            xlate("remove_admin_button") if u["admin"] else xlate("make_admin_button"),
            callback_data=f"{cid}^^^{u['id']}^^^{'remove_admin' if u['admin'] else 'make_admin'}",
        )

class KeyboardButtons(object):
    def __init__(self):
        self.nav_buttons = NavButtons()
        self.ext_buttons = ExternalButtons()
        self.act_buttons = ActionButtons()
        self.add_buttons = AddButtons()
        self.user_buttons = UserButtons()

    @property
    def nav(self):
        return self.nav_buttons
    
    @property
    def ext(self):
        return self.ext_buttons
    
    @property
    def act(self):
        return self.act_buttons
    
    @property
    def add(self):
        return self.add_buttons
    
    @property
    def user(self):
        return self.user_buttons