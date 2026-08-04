"""
Searcharr
Sonarr & Radarr Telegram Bot
Main Callback Router
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from bot.utils.conversation import get_conversation
from bot.utils.log import set_up_logger

# Import service-specific callback handlers
from bot.callbacks.sonarr_callbacks import handle_sonarr_callback
from bot.callbacks.sportarr_callbacks import handle_sportarr_callback
from bot.callbacks.radarr_callbacks import handle_radarr_callback
from bot.callbacks.user_callbacks import handle_user_callback

logger = set_up_logger("callbacks.handler")


def main_callback_handler(bot):
    """Create a callback handler function that routes to the appropriate service handler.
    
    Args:
        bot: The SearcharrBot instance
        
    Returns:
        function: Callback handler function
    """
    async def handle_callback(update, context):
        # Extract callback data
        query = update.callback_query
        data = query.data.split("^^^")
        
        if len(data) < 3:
            logger.error(f"Invalid callback data: {query.data}")
            await query.answer()
            return
        
        # Parse callback components
        cid, i, op = data[0], int(data[1]), data[2]
        
        # Extract operation flags if present
        op_flags = {}
        if len(data) > 3 and data[3]:
            for flag in data[3].split("^"):
                if "=" in flag:
                    k, v = flag.split("=")
                    op_flags[k] = v
        
        # Get conversation data
        convo = get_conversation(cid)
        if not convo:
            logger.warning(f"No conversation found with id: {cid}")
            await query.answer()
            return
        
        # All operations are now handled by their respective callback handlers
        
        # Route to appropriate handler based on conversation type
        try:
            if convo["type"] == "series":
                await handle_sonarr_callback(update, context, bot, convo, cid, i, op, op_flags)
            elif convo["type"] == "sport":
                await handle_sportarr_callback(update, context, bot, convo, cid, i, op, op_flags)
            elif convo["type"] == "movie":
                await handle_radarr_callback(update, context, bot, convo, cid, i, op, op_flags)
            elif convo["type"] == "users":
                await handle_user_callback(update, context, bot, convo, cid, i, op, op_flags)
            else:
                logger.error(f"Unknown conversation type: {convo['type']}")
                await query.answer()
        
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            if bot.dev_mode:
                raise
            await query.answer()
    
    return handle_callback