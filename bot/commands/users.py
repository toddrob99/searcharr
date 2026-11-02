"""
Searcharr
Sonarr & Radarr Telegram Bot
Users Command Handler
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
from bot.utils.auth import authenticated, get_users
from bot.utils.conversation import generate_cid, create_conversation
from bot.utils.formatting import prepare_response_users
from bot.utils.text import translate
from bot.utils.log import set_up_logger
import settings

logger = set_up_logger("commands.users")


async def users_command(update, context, bot):
    """Handle the /users command for user management.
    
    Args:
        update: The update with the message
        context: The callback context
        bot: The SearcharrBot instance
    """
    logger.debug(f"Received users cmd from [{update.message.from_user.username}]")
    
    # Check if the user is authenticated as admin
    auth_level = authenticated(update.message.from_user.id)
    if not auth_level:
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
    elif auth_level != 2:
        await update.message.reply_text(
            translate(
                "admin_auth_required",
                commands=" OR ".join(
                    [
                        f"`/{c} <{translate('admin_password')}>`"
                        for c in settings.searcharr_start_command_aliases
                    ]
                ),
            )
        )
        return
    
    # Get all users
    users = get_users()
    
    # Create a conversation for user management
    cid = generate_cid()
    create_conversation(
        id=cid,
        username=str(update.message.from_user.username),
        kind="users",
        results=users,
    )
    
    # Handle no users case
    if not users:
        await update.message.reply_text(translate("no_users_found"))
        return
    
    # Prepare response for user management
    reply_message, reply_markup = prepare_response_users(
        cid,
        users,
        0,  # Start from first page
        5,  # 5 users per page
        len(users),
    )
    
    # Keep the response in the originating forum topic.
    message_thread_id = (
        update.message.message_thread_id if update.message.is_topic_message else None
    )
    await context.bot.sendMessage(
        chat_id=update.message.chat.id,
        message_thread_id=message_thread_id,
        text=reply_message,
        reply_markup=reply_markup,
    )