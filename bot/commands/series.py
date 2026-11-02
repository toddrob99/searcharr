"""
Searcharr
Sonarr & Radarr Telegram Bot
Series Command Handler
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from telegram.error import BadRequest

from bot.utils.conversation import generate_cid, create_conversation
from bot.utils.auth import authenticated
from bot.utils.text import strip_entities, translate
from bot.utils.formatting import prepare_response
import settings


async def series_command(update, context, bot):
    """Handle the /series command to search for and add TV series."""
    logger = bot.logger
    logger.debug(f"Received series cmd from [{update.message.from_user.username}]")
    
    # Check authentication
    if not authenticated(update.message.from_user.id):
        await update.message.reply_text(
            translate(
                "auth_required",
                commands=" OR ".join(
                    [
                        f"`/{c} <{translate('password')}>`"
                        for c in settings.searcharr_start_command_aliases
                    ]
                ),
            )
        )
        return
    
    # Check if sonarr is enabled
    if not settings.sonarr_enabled:
        await update.message.reply_text(translate("sonarr_disabled"))
        return
    
    # Extract title from message
    title = strip_entities(update.message)
    if not title:
        x_title = translate("title").title()
        await update.message.reply_text(
            translate(
                "include_series_title_in_cmd",
                commands=" OR ".join(
                    [
                        f"`/{c} {x_title}`"
                        for c in settings.sonarr_series_command_aliases
                    ]
                ),
            )
        )
        return
    
    # Look up series
    results = bot.sonarr.lookup_series(title)

    # Handle no results before touching the database
    if not results:
        await update.message.reply_text(translate("no_matching_series"))
        return

    cid = generate_cid()
    if not cid:
        await update.message.reply_text(translate("unexpected_error"))
        return

    create_conversation(
        id=cid,
        username=str(update.message.from_user.username),
        kind="series",
        results=results,
    )
    
    # Prepare response for first result
    r = results[0]
    reply_message, reply_markup = prepare_response(
        "series", r, cid, 0, len(results)
    )
    
    # Keep the response in the originating forum topic.
    message_thread_id = (
        update.message.message_thread_id if update.message.is_topic_message else None
    )
    try:
        await context.bot.sendPhoto(
            chat_id=update.message.chat.id,
            message_thread_id=message_thread_id,
            photo=r["remotePoster"],
            caption=reply_message,
            reply_markup=reply_markup,
        )
    except BadRequest as e:
        if str(e) in [
            "Wrong type of the web page content",
            "Wrong file identifier/http url specified",
            "Media_empty",
        ]:
            logger.error(
                f"Error sending photo [{r['remotePoster']}]: BadRequest: {e}. Attempting to send with default poster..."
            )
            await context.bot.sendPhoto(
                chat_id=update.message.chat.id,
                message_thread_id=message_thread_id,
                photo="https://artworks.thetvdb.com/banners/images/missing/movie.jpg",
                caption=reply_message,
                reply_markup=reply_markup,
            )
        else:
            raise