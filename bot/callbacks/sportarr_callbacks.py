"""
Searcharr
Sonarr & Radarr Telegram Bot
Sportarr-Specific Callback Handlers
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from bot.utils.conversation import get_add_data, update_add_data, delete_conversation
from bot.utils.formatting import prepare_response
from bot.utils.text import translate
from bot.utils.log import set_up_logger
from bot.callbacks.base import (
    handle_navigation,
    handle_cancel,
    check_path_selection,
    check_quality_selection,
    handle_tag_selection,
    process_tags,
    update_media_message
)
import settings

logger = set_up_logger("callbacks.sportarr")

# Create a config object for Sportarr-specific settings
SPORTARR_CONFIG = {
    "tag_with_username": settings.sportarr_tag_with_username,
    "forced_tags": settings.sportarr_forced_tags,
    "allow_user_to_select_tags": settings.sportarr_allow_user_to_select_tags,
    "user_selectable_tags": settings.sportarr_user_selectable_tags,
    "add_monitored": settings.sportarr_add_monitored,
    "search_on_add": settings.sportarr_search_on_add,
    "season_monitor_prompt": settings.sportarr_season_monitor_prompt
}


async def handle_sportarr_callback(update, context, bot, convo, cid, i, op, op_flags):
    """Handle callbacks related to Sportarr (series).
    
    Args:
        update: The update with the callback query
        context: The callback context
        bot: The SearcharrBot instance
        convo: The conversation data
        cid: The conversation ID
        i: The current index
        op: The operation
        op_flags: Additional operation flags
    """
    query = update.callback_query
    
    # Handle operations
    if op == "add":
        await handle_add_sport(update, context, bot, convo, cid, i, op_flags)
    elif op == "prev" or op == "next":
        await handle_navigation(update, context, "sport", convo, cid, i, op)
    elif op == "cancel" or op == "done":
        await handle_cancel(update, context, convo, cid, i, op)
    else:
        # Default action for unrecognized operations
        await query.answer()


async def handle_add_sport(update, context, bot, convo, cid, i, op_flags):
    """Handle adding a series to Sportarr.
    
    Args:
        update: The update with the callback query
        context: The callback context
        bot: The SearcharrBot instance
        convo: The conversation data
        cid: The conversation ID
        i: The current index
        op_flags: Additional operation flags
    """
    query = update.callback_query
    service = bot.sportarr
    
    # Get the series result
    r = convo["results"][i]
    
    # If we have flags, process them first
    if op_flags:
        for k, v in op_flags.items():
            logger.debug(f"Adding/Updating additional data for cid=[{cid}], key=[{k}], value=[{v}]...")
            update_add_data(cid, k, v)
        
        # If this is a tag selection, handle it and return
        if op_flags.get("tt") or op_flags.get("td"):
            handled = await handle_tag_selection(update, context, service, SPORTARR_CONFIG, convo, cid, i, op_flags)
            if handled:
                return
    
    # Get the additional data that has been collected so far
    additional_data = get_add_data(cid)
    logger.debug(f"Additional data: {additional_data}")
    
    # Step 1: Check for root folder selection
    if not await check_path_selection(update, context, service, "sport", convo, cid, i):
        return
    
    # Step 2: Check for quality profile selection
    if not await check_quality_selection(update, context, service, "sport", convo, cid, i):
        return
    
    # Step 3: Check for season monitor options
    if (
        SPORTARR_CONFIG["season_monitor_prompt"]
        and additional_data.get("m", False) is False
    ):
        # Need to prompt user to select season monitoring option
        monitor_options = [
            translate("all_seasons"),
            translate("first_season"),
            translate("latest_season"),
        ]
        reply_message, reply_markup = prepare_response(
            "sport",
            r,
            cid,
            i,
            len(convo["results"]),
            add=True,
            monitor_options=monitor_options,
        )
        await update_media_message(
                query.message,
                r["remotePoster"],
                caption=reply_message,
                reply_markup=reply_markup
            )
        await query.answer()
        return
    
    # Step 4: Check for tag selection
    if SPORTARR_CONFIG["allow_user_to_select_tags"] and not additional_data.get("td"):
        all_tags = service.get_filtered_tags(
            SPORTARR_CONFIG["user_selectable_tags"],
            SPORTARR_CONFIG["forced_tags"],
        )
        
        if not all_tags:
            logger.warning(
                "User tagging is enabled, but no tags found. Make sure there are tags in Sportarr matching your Searcharr configuration."
            )
        elif not additional_data.get("tt"):
            # Need to prompt user to select tags
            reply_message, reply_markup = prepare_response(
                "sport",
                r,
                cid,
                i,
                len(convo["results"]),
                add=True,
                tags=all_tags,
            )
            await update_media_message(
                query.message,
                r["remotePoster"],
                caption=reply_message,
                reply_markup=reply_markup
            )
            await query.answer()
            return
    
    # Step 5: Process tags (username tag and forced tags)
    await process_tags(service, SPORTARR_CONFIG, cid, query.from_user)
    
    # Step 6: All data collected, add the series
    logger.debug("All data is accounted for, proceeding to add...")
    try:
        added = service.add_series(
            series_info=r,
            monitored=SPORTARR_CONFIG["add_monitored"],
            search=SPORTARR_CONFIG["search_on_add"],
            additional_data=get_add_data(cid),
        )
    except Exception as e:
        logger.error(f"Error adding series: {e}")
        added = False
    
    logger.debug(f"Result of attempt to add series: {added}")
    
    # Step 7: Handle the result
    if added:
        delete_conversation(cid)
        await query.message.reply_text(translate("added", title=r["title"]))
        await query.message.delete()
    else:
        await query.message.reply_text(
            translate("unknown_error_adding", kind="sport")
        )
    
    await query.answer()