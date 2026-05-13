import tempfile
import unittest
from pathlib import Path

from app_store import SQLiteStudyGroupStore
from studygroupapp import create_app


class SQLitePersistenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "app.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_test_app(self):
        return create_app(
            {
                "TESTING": True,
                "DATABASE": self.database_path,
                "SECRET_KEY": "test-secret",
            }
        )

    def login_client(self, client, email: str = "test@southernct.edu") -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        user = store.find_by_email(email)
        assert user is not None
        with client.session_transaction() as session:
            session["user_id"] = str(user.id)

    def test_signup_persists_user_to_sqlite(self) -> None:
        app = self.create_test_app()
        client = app.test_client()

        response = client.post(
            "/signup",
            data={
                "firstName": "Maya",
                "lastName": "Chen",
                "scsuEmail": "maya.chen@southernct.edu",
                "contactInfo": "maya.chen@southernct.edu",
                "password": "study-pass-123",
                "confirmPassword": "study-pass-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/home")
        home_response = client.get("/home")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn("Welcome, Maya", home_response.get_data(as_text=True))

        store = SQLiteStudyGroupStore(self.database_path)
        user = store.find_by_email("maya.chen@southernct.edu")

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.firstName, "Maya")
        self.assertEqual(user.interests, [])
        self.assertEqual(user.contactInfo, "maya.chen@southernct.edu")

    def test_messages_persist_across_app_instances(self) -> None:
        first_app = self.create_test_app()
        first_client = first_app.test_client()
        self.login_client(first_client)

        store = SQLiteStudyGroupStore(self.database_path)
        test_user = store.find_by_email("test@southernct.edu")
        assert test_user is not None
        software_thread = next(
            thread
            for thread in store.list_user_study_group_chats(test_user.id)
            if thread["group_title"] == "Software Design Studio"
        )

        first_client.post(
            "/messages/send",
            data={
                "conversation_id": software_thread["conversation_id"],
                "group_id": software_thread["group_id"],
                "content": "Can everyone review the database schema?",
            },
        )

        second_app = self.create_test_app()
        second_client = second_app.test_client()
        self.login_client(second_client)
        response = second_client.get(
            f"/messages?chat={software_thread['conversation_id']}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Can everyone review the database schema?",
            response.get_data(as_text=True),
        )

    def test_profile_updates_persist_across_app_instances(self) -> None:
        first_app = self.create_test_app()
        first_client = first_app.test_client()
        self.login_client(first_client)

        first_client.post(
            "/update-profile",
            data={
                "firstName": "Test",
                "lastName": "User",
                "major": "Data Science",
                "bio": "Updated through SQLite.",
                "interests": "SQLite, Flask",
                "contactInfo": "test@southernct.edu",
            },
        )

        second_app = self.create_test_app()
        second_client = second_app.test_client()
        self.login_client(second_client)
        response = second_client.get("/profile")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Data Science", page)
        self.assertIn("Updated through SQLite.", page)
        self.assertIn("profile-panel", page)

        edit_response = second_client.get("/update-profile")
        edit_page = edit_response.get_data(as_text=True)

        self.assertEqual(edit_response.status_code, 200)
        self.assertIn("Edit Profile", edit_page)
        self.assertIn('name="interests"', edit_page)
        self.assertIn("SQLite, Flask", edit_page)

    def test_group_message_notification_data_lists_other_active_members(self) -> None:
        app = self.create_test_app()
        store = app.config["DATA_STORE"]
        test_user = store.find_by_email("test@southernct.edu")
        assert test_user is not None
        software_thread = next(
            thread
            for thread in store.list_user_study_group_chats(test_user.id)
            if thread["group_title"] == "Software Design Studio"
        )

        notification_data = store.group_message_notification_data(
            software_thread["group_id"],
            test_user.id,
        )

        self.assertEqual(notification_data["group_title"], "Software Design Studio")
        self.assertEqual(notification_data["sender_name"], "Test User")
        self.assertEqual(
            notification_data["recipients"],
            ["alex.mitchell@southernct.edu", "priya.nair@southernct.edu"],
        )


if __name__ == "__main__":
    unittest.main()
