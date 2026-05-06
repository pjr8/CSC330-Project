import tempfile
import unittest
from pathlib import Path

from app_store import SQLiteStudyGroupStore


class DirectMessageStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "app.sqlite3")
        self.store = SQLiteStudyGroupStore(self.database_path)
        self.store.initialize()
        self.test_user = self.store.find_by_email("test@southernct.edu")
        self.john = self.store.find_by_email("john.smith@southernct.edu")
        self.sarah = self.store.find_by_email("sarah.lee@southernct.edu")
        assert self.test_user is not None
        assert self.john is not None
        assert self.sarah is not None

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_search_users_excludes_current_user_and_matches_name(self) -> None:
        results = self.store.search_users_for_dm(self.test_user.id, "test")

        self.assertEqual(results, [])

        results = self.store.search_users_for_dm(self.test_user.id, "Sarah")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Sarah Lee")
        self.assertEqual(results[0]["email"], "sarah.lee@southernct.edu")

    def test_seeded_sidebar_only_shows_threads_with_messages(self) -> None:
        threads = self.store.list_user_dm_threads(self.test_user.id)
        names = [thread["participant_name"] for thread in threads]

        self.assertIn("John Smith", names)
        self.assertNotIn("Sarah Lee", names)
        self.assertNotIn("Group Chat", names)

    def test_send_direct_message_creates_and_reuses_thread(self) -> None:
        first = self.store.send_direct_message(
            self.test_user.id,
            recipient_id=self.sarah.id,
            content="Can you review the database schema?",
        )
        assert first is not None
        second = self.store.send_direct_message(
            self.test_user.id,
            recipient_id=self.sarah.id,
            content="I added the migration notes.",
        )
        assert second is not None

        self.assertEqual(first["conversation_id"], second["conversation_id"])

        thread = self.store.get_dm_thread_messages(
            self.test_user.id,
            str(first["conversation_id"]),
        )
        self.assertIsNotNone(thread)
        assert thread is not None
        self.assertEqual(thread["conversation"]["participant_name"], "Sarah Lee")
        self.assertEqual(
            [message["content"] for message in thread["messages"]],
            [
                "Can you review the database schema?",
                "I added the migration notes.",
            ],
        )

    def test_empty_self_and_unauthorized_messages_are_rejected(self) -> None:
        self.assertIsNone(
            self.store.send_direct_message(
                self.test_user.id,
                recipient_id=self.sarah.id,
                content="   ",
            )
        )
        self.assertIsNone(
            self.store.send_direct_message(
                self.test_user.id,
                recipient_id=self.test_user.id,
                content="Note to self",
            )
        )

        thread = self.store.send_direct_message(
            self.test_user.id,
            recipient_id=self.sarah.id,
            content="This is private to Sarah.",
        )
        assert thread is not None

        self.assertIsNone(
            self.store.get_dm_thread_messages(
                self.john.id,
                str(thread["conversation_id"]),
            )
        )
        self.assertIsNone(
            self.store.send_direct_message(
                self.john.id,
                conversation_id=str(thread["conversation_id"]),
                content="I should not be able to post here.",
            )
        )


if __name__ == "__main__":
    unittest.main()
