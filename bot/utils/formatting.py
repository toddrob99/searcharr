"""
Searcharr
Sonarr & Radarr Telegram Bot
Message Formatting Utilities
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.text import translate
from bot.utils.log import set_up_logger

logger = set_up_logger("formatting")


def prepare_response(
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
    """Prepare a response message and keyboard markup.
    
    Args:
        kind (str): The type of content ("series", "movie")
        r (dict): The content data
        cid (str): The conversation ID
        i (int): The current index
        total_results (int): The total number of results
        add (bool, optional): Whether this is for adding content. Defaults to False.
        paths (list, optional): List of path options. Defaults to None.
        quality_profiles (list, optional): List of quality profile options. Defaults to None.
        monitor_options (list, optional): List of monitor options. Defaults to None.
        tags (list, optional): List of tag options. Defaults to None.
        
    Returns:
        tuple: (message_text, reply_markup)
    """
    keyboard = []
    keyboardNavRow = []
    
    # Add navigation buttons
    if i > 0:
        keyboardNavRow.append(
            InlineKeyboardButton(
                translate("prev_button"), callback_data=f"{cid}^^^{i}^^^prev"
            )
        )
    
    # Add content-specific links
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
    # Add IMDb links for movies and series (sport results carry alias ids,
    # not real TVDB/IMDb entries, so no external links for them)
    if kind in ["series", "movie"]:
        if r["imdbId"]:
            keyboardNavRow.append(
                InlineKeyboardButton(
                    "IMDb", url=f"https://imdb.com/title/{r['imdbId']}"
                )
            )
    
    # Add next button if not on last result
    if total_results > 1 and i < total_results - 1:
        keyboardNavRow.append(
            InlineKeyboardButton(
                translate("next_button"), callback_data=f"{cid}^^^{i}^^^next"
            )
        )
    
    # Add navigation row to keyboard
    keyboard.append(keyboardNavRow)

    # Process "add" mode options
    if add:
        if tags:
            # Add tag selection buttons
            for tag in tags[:12]:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            translate("add_tag_button", tag=tag["label"]),
                            callback_data=f"{cid}^^^{i}^^^add^^^tt={tag['id']}",
                        )
                    ],
                )
            # Add "finished tagging" button
            keyboard.append(
                [
                    InlineKeyboardButton(
                        translate("finished_tagging_button"),
                        callback_data=f"{cid}^^^{i}^^^add^^^td=1",
                    )
                ],
            )
        elif monitor_options:
            # Add monitor options buttons
            for k, o in enumerate(monitor_options):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            translate("monitor_button", option=o),
                            callback_data=f"{cid}^^^{i}^^^add^^^m={k}",
                        )
                    ],
                )
        elif quality_profiles:
            # Add quality profile selection buttons
            for q in quality_profiles:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            translate("add_quality_button", quality=q["name"]),
                            callback_data=f"{cid}^^^{i}^^^add^^^q={q['id']}",
                        )
                    ],
                )
        elif paths:
            # Add path selection buttons
            for p in paths:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            translate("add_path_button", path=p["path"]),
                            callback_data=f"{cid}^^^{i}^^^add^^^p={p['id']}",
                        )
                    ],
                )

    # Add action buttons
    keyboardActRow = []
    if not add:
        if not r["id"]:
            keyboardActRow.append(
                InlineKeyboardButton(
                    translate("add_button", kind=translate(kind).title()),
                    callback_data=f"{cid}^^^{i}^^^add",
                ),
            )
        else:
            keyboardActRow.append(
                InlineKeyboardButton(
                    translate("already_added_button"),
                    callback_data=f"{cid}^^^{i}^^^noop",
                ),
            )
    
    # Add cancel button
    keyboardActRow.append(
        InlineKeyboardButton(
            translate("cancel_search_button"),
            callback_data=f"{cid}^^^{i}^^^cancel",
        ),
    )
    
    # Add action row if it has buttons
    if keyboardActRow:
        keyboard.append(keyboardActRow)
    
    # Add anime option for series
    if not add and kind == "series" and "Anime" in r.get("genres", []):
        keyboard.append(
            [
                InlineKeyboardButton(
                    translate("add_series_anime_button"),
                    callback_data=f"{cid}^^^{i}^^^add^^^st=a",
                )
            ]
        )

    # Create reply markup
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Create message text based on content type
    if kind == "series":
        reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''} - {r['seasonCount']} Season{'s' if r['seasonCount'] != 1 else ''}{' - ' + r['network'] if r['network'] else ''} - {r['status'].title()}\n\n{r['overview']}"[
            0:1024
        ]
    elif kind == "sport":
        reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''} - {r['seasonCount']} Season{'s' if r['seasonCount'] != 1 else ''} - {r['status'].title()}\n\n{r['overview']}"[
            0:1024
        ]
    elif kind == "movie":
        reply_message = f"{r['title']}{' (' + str(r['year']) + ')' if r['year'] and str(r['year']) not in r['title'] else ''}{' - ' + str(r['runtime']) + ' min' if r['runtime'] else ''} - {r['status'].title()}\n\n{r['overview']}"[
            0:1024
        ]
    else:
        reply_message = translate("unexpected_error")

    return (reply_message, reply_markup)


def prepare_response_users(cid, users, offset, num, total_results):
    """Prepare a response message and keyboard markup for user management.
    
    Args:
        cid (str): The conversation ID
        users (list): List of user data
        offset (int): The starting index
        num (int): The number of users to display
        total_results (int): The total number of users
        
    Returns:
        tuple: (message_text, reply_markup)
    """
    keyboard = []
    
    # Add user management buttons for each user
    for u in users[offset : offset + num]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    translate("remove_user_button"),
                    callback_data=f"{cid}^^^{u['id']}^^^remove_user",
                ),
                InlineKeyboardButton(
                    f"{u['username'] if u['username'] != 'None' else u['id']}",
                    callback_data=f"{cid}^^^{u['id']}^^^noop",
                ),
                InlineKeyboardButton(
                    translate("remove_admin_button")
                    if u["admin"]
                    else translate("make_admin_button"),
                    callback_data=f"{cid}^^^{u['id']}^^^{'remove_admin' if u['admin'] else 'make_admin'}",
                ),
            ]
        )
    
    # Add navigation buttons
    keyboardNavRow = []
    if offset > 0:
        keyboardNavRow.append(
            InlineKeyboardButton(
                translate("prev_button"),
                callback_data=f"{cid}^^^{offset - num}^^^prev",
            ),
        )
    
    # Add done button
    keyboardNavRow.append(
        InlineKeyboardButton(
            translate("done"), callback_data=f"{cid}^^^{offset}^^^done"
        ),
    )
    
    # Add next button if not at end
    if total_results > 1 and offset + num < total_results:
        keyboardNavRow.append(
            InlineKeyboardButton(
                translate("next_button"),
                callback_data=f"{cid}^^^{offset + num}^^^next",
            ),
        )
    
    # Add navigation row
    keyboard.append(keyboardNavRow)
    
    # Create reply markup
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Create message text
    reply_message = translate(
        "listing_users_pagination",
        page_info=f"{offset + 1}-{min(offset + num, total_results)} of {total_results}",
    )
    
    return (reply_message, reply_markup)