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
        sarah = store.find_by_email("sarah.lee@southernct.edu")
        assert sarah is not None

        first_client.post(
            "/messages/send",
            data={
                "recipient_id": str(sarah.id),
                "content": "Can you review the database schema?",
            },
        )

        second_app = self.create_test_app()
        second_client = second_app.test_client()
        self.login_client(second_client)
        response = second_client.get("/messages")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Can you review the database schema?",
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


if __name__ == "__main__":
    unittest.main()
