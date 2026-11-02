"""Check command routing without a Telegram account or application settings."""

import importlib
import sys
import unittest
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from telegram import Chat, Message, Update, User
from telegram.error import BadRequest


CHAT_CASES = (
    ("private", "private", None, None, None),
    ("group reply chain", "group", False, 900, None),
    ("forum General", "supergroup", False, 1, None),
    ("forum topic", "supergroup", True, 42, 42),
    ("another topic", "supergroup", True, 73, 73),
)


class TopicRoutingTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(sys.modules, {"settings": ModuleType("settings")}):
            with patch("bot.utils.log.set_up_logger", return_value=Mock()):
                cls.commands = {
                    name: importlib.import_module(f"bot.commands.{name}")
                    for name in ("movie", "series", "users")
                }

    def make_update(self, chat_type, is_topic, thread_id):
        message = Message(
            message_id=100,
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            chat=Chat(id=123 if chat_type == "private" else -123, type=chat_type),
            from_user=User(id=456, first_name="Tester", is_bot=False, username="tester"),
            is_topic_message=is_topic,
            message_thread_id=thread_id,
        )
        return Update(update_id=1, message=message)

    async def run_search(self, command, update, send_photo):
        module = self.commands[command]
        results = [{"remotePoster": "https://example.com/poster.jpg"}]
        bot = Mock()
        bot.radarr.lookup_movie.return_value = results
        bot.sonarr.lookup_series.return_value = results
        context = SimpleNamespace(bot=SimpleNamespace(sendPhoto=send_photo))
        with patch.multiple(
            module,
            settings=SimpleNamespace(radarr_enabled=True, sonarr_enabled=True),
            authenticated=Mock(return_value=1),
            strip_entities=Mock(return_value="Example"),
            generate_cid=Mock(return_value="test-cid"),
            create_conversation=Mock(),
            prepare_response=Mock(return_value=("Search result", None)),
        ):
            await getattr(module, f"{command}_command")(update, context, bot)

    async def test_search_cards_and_fallback_posters_keep_the_correct_topic(self):
        for command in ("movie", "series"):
            for label, chat_type, is_topic, thread_id, expected in CHAT_CASES:
                for fallback in (False, True):
                    with self.subTest(command=command, chat=label, fallback=fallback):
                        update = self.make_update(chat_type, is_topic, thread_id)
                        send_photo = AsyncMock()
                        if fallback:
                            send_photo.side_effect = [
                                BadRequest("Wrong file identifier/http url specified"),
                                None,
                            ]
                        await self.run_search(command, update, send_photo)
                        self.assertEqual(send_photo.await_count, 2 if fallback else 1)
                        for call in send_photo.await_args_list:
                            self.assertEqual(call.kwargs["chat_id"], update.message.chat.id)
                            self.assertEqual(call.kwargs.get("message_thread_id"), expected)
                        if fallback:
                            self.assertNotEqual(
                                send_photo.await_args_list[0].kwargs["photo"],
                                send_photo.await_args_list[1].kwargs["photo"],
                            )

    async def test_users_menu_keeps_the_correct_topic(self):
        module = self.commands["users"]
        for label, chat_type, is_topic, thread_id, expected in CHAT_CASES:
            with self.subTest(chat=label):
                update = self.make_update(chat_type, is_topic, thread_id)
                send_message = AsyncMock()
                context = SimpleNamespace(bot=SimpleNamespace(sendMessage=send_message))
                with patch.multiple(
                    module,
                    authenticated=Mock(return_value=2),
                    get_users=Mock(return_value=[{"id": 456}]),
                    generate_cid=Mock(return_value="test-cid"),
                    create_conversation=Mock(),
                    prepare_response_users=Mock(return_value=("Users", None)),
                ):
                    await module.users_command(update, context, Mock())
                send_message.assert_awaited_once()
                self.assertEqual(send_message.await_args.kwargs["chat_id"], update.message.chat.id)
                self.assertEqual(send_message.await_args.kwargs.get("message_thread_id"), expected)

    async def test_invalid_topic_is_not_retried_in_general(self):
        for command in ("movie", "series"):
            with self.subTest(command=command):
                update = self.make_update("supergroup", True, 42)
                send_photo = AsyncMock(side_effect=BadRequest("Message thread not found"))
                with self.assertRaisesRegex(BadRequest, "Message thread not found"):
                    await self.run_search(command, update, send_photo)
                send_photo.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
