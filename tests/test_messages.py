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
        self.loaded_groups: list[str] = []
        self.threads = [
            {
                "conversation_id": "chat-software",
                "group_id": "group-software",
                "group_title": "Software Design Studio",
                "group_subject": "CSC 330 - Software Engineering",
                "group_location": "Buley Library, Room 205",
                "member_count": 3,
                "last_message": "I will review the Flask handlers before we meet.",
                "last_sent_at": "2026-05-04T15:15:00",
            },
            {
                "conversation_id": "chat-calculus",
                "group_id": "group-calculus",
                "group_title": "Calculus II Problem Session",
                "group_subject": "MAT 221 - Calculus II",
                "group_location": "Engleman Hall, A112",
                "member_count": 2,
                "last_message": "",
                "last_sent_at": "",
            },
        ]
        self.thread_messages = {
            "chat-software": {
                "conversation": self.threads[0],
                "messages": [
                    {
                        "id": "m-1",
                        "sender_name": "Alex Mitchell",
                        "content": "I added the route test checklist.",
                        "sent_at": "2026-05-04T15:00:00",
                        "is_mine": False,
                    },
                    {
                        "id": "m-2",
                        "sender_name": "Test User",
                        "content": "I will review the Flask handlers before we meet.",
                        "sent_at": "2026-05-04T15:15:00",
                        "is_mine": True,
                    },
                ],
            },
            "chat-calculus": {
                "conversation": self.threads[1],
                "messages": [],
            },
        }

    def user_for_session(self, user_id: str | None) -> FakeUser:
        return self.current_user

    def list_user_study_group_chats(self, current_user_id: str) -> list[dict[str, Any]]:
        return self.threads

    def get_study_group_chat_for_group(
        self,
        current_user_id: str,
        group_id: str,
    ) -> dict[str, Any] | None:
        self.loaded_groups.append(group_id)
        return next(
            (thread for thread in self.threads if thread["group_id"] == group_id),
            None,
        )

    def get_study_group_thread_messages(
        self,
        current_user_id: str,
        conversation_id: str,
    ) -> dict[str, object] | None:
        self.loaded_threads.append(conversation_id)
        return self.thread_messages.get(conversation_id)

    def send_study_group_message(
        self,
        current_user_id: str,
        *,
        group_id: str | None = None,
        conversation_id: str | None = None,
        content: str = "",
    ) -> dict[str, object] | None:
        self.sent_messages.append(
            {
                "current_user_id": current_user_id,
                "group_id": group_id,
                "conversation_id": conversation_id,
                "content": content,
            }
        )
        return {
            "conversation_id": conversation_id or "chat-new",
            "group_id": group_id or "group-new",
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

    def test_get_messages_renders_group_thread_and_external_stylesheet(self) -> None:
        response = self.client.get("/messages?chat=chat-software")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Software Design Studio", page)
        self.assertIn("CSC 330 - Software Engineering", page)
        self.assertIn("I added the route test checklist.", page)
        self.assertIn("I will review the Flask handlers before we meet.", page)
        self.assertIn("message-bubble--theirs", page)
        self.assertIn("message-bubble--mine", page)
        self.assertIn('name="conversation_id" value="chat-software"', page)
        self.assertIn('name="group_id" value="group-software"', page)
        self.assertIn("css/messages.css", page)
        self.assertNotIn("Direct messages", page)
        self.assertNotIn("<style", page)
        self.assertNotIn(" style=", page)
        self.assertEqual(self.store.loaded_threads, ["chat-software"])

    def test_group_search_filters_and_opens_matching_chat(self) -> None:
        response = self.client.get("/messages?q=calculus")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Calculus II Problem Session", page)
        self.assertNotIn("Software Design Studio", page)
        self.assertIn("Start the group chat", page)
        self.assertIn('name="conversation_id" value="chat-calculus"', page)
        self.assertEqual(self.store.loaded_threads, ["chat-calculus"])
        self.assertEqual(self.store.sent_messages, [])

    def test_group_deep_link_selects_group_chat(self) -> None:
        response = self.client.get("/messages?group=group-calculus")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Calculus II Problem Session", page)
        self.assertIn('name="conversation_id" value="chat-calculus"', page)
        self.assertEqual(self.store.loaded_groups, ["group-calculus"])
        self.assertEqual(self.store.loaded_threads, ["chat-calculus"])

    def test_send_to_existing_group_chat_uses_conversation_and_group_id(self) -> None:
        response = self.client.post(
            "/messages/send",
            data={
                "conversation_id": "chat-software",
                "group_id": "group-software",
                "content": "I am on my way.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/messages?chat=chat-software")
        self.assertEqual(
            self.store.sent_messages,
            [
                {
                    "current_user_id": "u-current",
                    "group_id": "group-software",
                    "conversation_id": "chat-software",
                    "content": "I am on my way.",
                }
            ],
        )

    def test_blank_message_redirects_without_sending(self) -> None:
        response = self.client.post(
            "/messages/send",
            data={
                "conversation_id": "chat-software",
                "group_id": "group-software",
                "content": "   ",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/messages?chat=chat-software")
        self.assertEqual(self.store.sent_messages, [])


if __name__ == "__main__":
    unittest.main()
