from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Blueprint, Flask

from messages import messages_bp


@dataclass
class FakeUser:
    id: str = "u-current"
    firstName: str = "Test"
    lastName: str = "User"

    def getFullName(self) -> str:
        return f"{self.firstName} {self.lastName}"


class FakeMessageStore:
    def __init__(self) -> None:
        self.current_user = FakeUser()
        self.sent_messages: list[dict[str, Any]] = []
        self.loaded_threads: list[str] = []
        self.searches: list[tuple[str, str]] = []
        self.threads = [
            {
                "conversation_id": "chat-1",
                "participant_id": "u-alex",
                "participant_name": "Alex Mitchell",
                "participant_major": "Computer Science",
                "last_message": "See you in the library.",
                "last_sent_at": "2026-05-04T10:05:00",
            }
        ]
        self.thread_messages = {
            "chat-1": {
                "conversation": self.threads[0],
                "messages": [
                    {
                        "id": "m-1",
                        "sender_name": "Alex Mitchell",
                        "content": "Are you bringing the notes?",
                        "sent_at": "2026-05-04T10:00:00",
                        "is_mine": False,
                    },
                    {
                        "id": "m-2",
                        "sender_name": "Test User",
                        "content": "Yes, I have the packet.",
                        "sent_at": "2026-05-04T10:05:00",
                        "is_mine": True,
                    },
                ],
            }
        }
        self.search_result = {
            "id": "u-rowan",
            "display_name": "Rowan Patel",
            "scsu_email": "rowan.patel@southernct.edu",
            "major": "Mathematics",
        }

    def user_for_session(self, user_id: str | None) -> FakeUser:
        return self.current_user

    def list_user_dm_threads(self, current_user_id: str) -> list[dict[str, str]]:
        return self.threads

    def search_users_for_dm(
        self,
        current_user_id: str,
        query: str,
    ) -> list[dict[str, str]]:
        self.searches.append((current_user_id, query))
        if query.lower() == "row":
            return [self.search_result]
        return []

    def get_dm_thread_messages(
        self,
        current_user_id: str,
        conversation_id: str,
    ) -> dict[str, object] | None:
        self.loaded_threads.append(conversation_id)
        return self.thread_messages.get(conversation_id)

    def send_direct_message(
        self,
        current_user_id: str,
        *,
        recipient_id: str | None = None,
        conversation_id: str | None = None,
        content: str = "",
    ) -> dict[str, object] | None:
        self.sent_messages.append(
            {
                "current_user_id": current_user_id,
                "recipient_id": recipient_id,
                "conversation_id": conversation_id,
                "content": content,
            }
        )
        return {
            "conversation_id": conversation_id or "chat-new",
            "message": {"content": content},
        }


class MessagesRouteTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeMessageStore()
        project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(
            __name__,
            template_folder=str(project_root / "templates"),
            static_folder=str(project_root / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            DATA_STORE=self.store,
        )
        self.register_header_routes()
        self.app.register_blueprint(messages_bp)
        self.client = self.app.test_client()

    def register_header_routes(self) -> None:
        @self.app.get("/home")
        def home():
            return ""

        study_groups = Blueprint("study_groups", __name__)

        @study_groups.get("/listings")
        def listings():
            return ""

        self.app.register_blueprint(study_groups)

        @self.app.get("/create")
        def create_group():
            return ""

        @self.app.get("/profile")
        def profile():
            return ""

        @self.app.get("/logout")
        def logout():
            return ""

    def test_get_messages_renders_thread_and_external_stylesheet(self) -> None:
        response = self.client.get("/messages?chat=chat-1")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Alex Mitchell", page)
        self.assertIn("Are you bringing the notes?", page)
        self.assertIn("Yes, I have the packet.", page)
        self.assertIn("message-bubble--theirs", page)
        self.assertIn("message-bubble--mine", page)
        self.assertIn('name="conversation_id" value="chat-1"', page)
        self.assertIn("css/messages.css", page)
        self.assertNotIn("<style", page)
        self.assertNotIn(" style=", page)
        self.assertEqual(self.store.loaded_threads, ["chat-1"])

    def test_search_recipient_stays_in_compose_state_without_creating_chat(self) -> None:
        response = self.client.get("/messages?q=row&recipient=u-rowan")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Rowan Patel", page)
        self.assertIn("Start a direct message", page)
        self.assertIn(
            "Send the first message to create this chat.",
            page,
        )
        self.assertIn('name="recipient_id" value="u-rowan"', page)
        self.assertIn("Alex Mitchell", page)
        self.assertEqual(self.store.searches, [("u-current", "row")])
        self.assertEqual(self.store.loaded_threads, [])
        self.assertEqual(self.store.sent_messages, [])

    def test_send_to_recipient_creates_chat_on_post(self) -> None:
        response = self.client.post(
            "/messages/send",
            data={
                "recipient_id": "u-rowan",
                "content": "Want to review calculus?",
                "q": "row",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/messages?chat=chat-new")
        self.assertEqual(
            self.store.sent_messages,
            [
                {
                    "current_user_id": "u-current",
                    "recipient_id": "u-rowan",
                    "conversation_id": None,
                    "content": "Want to review calculus?",
                }
            ],
        )

    def test_send_to_existing_chat_uses_conversation_id(self) -> None:
        response = self.client.post(
            "/messages/send",
            data={
                "conversation_id": "chat-1",
                "content": "I am on my way.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/messages?chat=chat-1")
        self.assertEqual(
            self.store.sent_messages,
            [
                {
                    "current_user_id": "u-current",
                    "recipient_id": None,
                    "conversation_id": "chat-1",
                    "content": "I am on my way.",
                }
            ],
        )

    def test_blank_message_redirects_without_sending(self) -> None:
        response = self.client.post(
            "/messages/send",
            data={
                "recipient_id": "u-rowan",
                "content": "   ",
                "q": "row",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "/messages?recipient=u-rowan&q=row",
        )
        self.assertEqual(self.store.sent_messages, [])


if __name__ == "__main__":
    unittest.main()
