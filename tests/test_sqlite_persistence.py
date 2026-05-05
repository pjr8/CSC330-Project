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

    def test_signup_persists_user_to_sqlite(self) -> None:
        app = self.create_test_app()
        client = app.test_client()

        response = client.post(
            "/signup",
            data={
                "firstName": "Maya",
                "lastName": "Chen",
                "scsuEmail": "maya.chen@southernct.edu",
                "password": "study-pass-123",
                "confirmPassword": "study-pass-123",
                "major": "Computer Science",
                "interests": "Databases, Software testing",
                "bio": "I like persistent campus apps.",
            },
        )

        self.assertEqual(response.status_code, 302)

        store = SQLiteStudyGroupStore(self.database_path)
        user = store.find_by_email("maya.chen@southernct.edu")

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.firstName, "Maya")
        self.assertEqual(user.interests, ["Databases", "Software testing"])

    def test_messages_persist_across_app_instances(self) -> None:
        first_app = self.create_test_app()
        first_client = first_app.test_client()

        first_client.post(
            "/messages?user=Sarah%20Lee",
            data={"message": "Can you review the database schema?"},
        )

        second_app = self.create_test_app()
        second_client = second_app.test_client()
        response = second_client.get("/messages?user=Sarah%20Lee")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Can you review the database schema?",
            response.get_data(as_text=True),
        )

    def test_profile_updates_persist_across_app_instances(self) -> None:
        first_app = self.create_test_app()
        first_client = first_app.test_client()

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
        response = second_client.get("/profile")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Data Science", page)
        self.assertIn("Updated through SQLite.", page)


if __name__ == "__main__":
    unittest.main()
