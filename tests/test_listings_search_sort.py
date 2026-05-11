import tempfile
import unittest
from pathlib import Path

from app_store import SQLiteStudyGroupStore
from studygroupapp import create_app


class ListingsSearchSortTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "app.sqlite3")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database_path,
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()
        self.login_default_user()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def login_default_user(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        user = store.find_by_email("test@southernct.edu")
        assert user is not None
        with self.client.session_transaction() as session:
            session["user_id"] = str(user.id)

    def test_listings_render_search_and_sort_controls(self) -> None:
        response = self.client.get("/listings")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('name="q"', page)
        self.assertIn('name="sort"', page)
        self.assertIn("Soonest meeting", page)
        self.assertIn("Title A-Z", page)
        self.assertIn("Subject A-Z", page)
        self.assertIn("Most seats", page)
        self.assertIn('href="/create"', page)
        self.assertIn("Create study group", page)

    def test_search_filters_open_groups_by_course_title_location_or_host(self) -> None:
        response = self.client.get("/listings?q=chemistry")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("General Chemistry Lab Prep", page)
        self.assertNotIn("Anatomy Lab Review", page)
        self.assertNotIn("Calculus II Problem Session", page)
        self.assertIn("Showing <strong>1</strong> of <strong>5</strong>", page)

    def test_title_sort_orders_matching_groups_alphabetically(self) -> None:
        response = self.client.get("/listings?sort=title")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertLess(
            page.index("Anatomy Lab Review"),
            page.index("Calculus II Problem Session"),
        )
        self.assertLess(
            page.index("Calculus II Problem Session"),
            page.index("General Chemistry Lab Prep"),
        )
        self.assertIn('<option value="title" selected>Title A-Z</option>', page)

    def test_seat_sort_places_open_capacity_groups_first(self) -> None:
        response = self.client.get("/listings?sort=seats")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertLess(
            page.index("Research Writing Circle"),
            page.index("Anatomy Lab Review"),
        )
        self.assertIn('<option value="seats" selected>Most seats</option>', page)


if __name__ == "__main__":
    unittest.main()
