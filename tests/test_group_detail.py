import tempfile
import unittest
from pathlib import Path

from app_store import SQLiteStudyGroupStore
from models import StudyGroup, User
from study_groups.view_models import study_group_view_model
from studygroupapp import create_app


class StudyGroupDetailTestCase(unittest.TestCase):
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
        self._sign_in_as("test@southernct.edu")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def login_default_user(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        user = store.find_by_email("test@southernct.edu")
        assert user is not None
        with self.client.session_transaction() as session:
            session["user_id"] = str(user.id)

    def test_listings_render_real_detail_links(self) -> None:
        group = self._group_named("Research Writing Circle")

        response = self.client.get("/listings")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn(f'href="/study-groups/{group.id}"', page)
        self.assertIn("Details", page)

    def test_detail_renders_information_and_gates_virtual_link(self) -> None:
        group = self._group_named("Anatomy Lab Review")

        response = self.client.get(f"/study-groups/{group.id}")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Anatomy Lab Review", page)
        self.assertIn("Priya Nair", page)
        self.assertIn("Wednesday, May 6 at 6:00 PM to 7:15 PM", page)
        self.assertIn("Hybrid", page)
        self.assertIn("Jennings Hall, Lab 148 + virtual option", page)
        self.assertIn("4 / 10 members", page)
        self.assertIn("Alex Mitchell", page)
        self.assertIn("Join group", page)
        self.assertIn('name="next" value="detail"', page)
        self.assertIn("Join this group to view the member-only virtual meeting link.", page)
        self.assertNotIn("https://example.edu/scsu-bio211-review", page)

    def test_member_detail_shows_virtual_link_and_joined_state(self) -> None:
        group = self._group_named("Research Writing Circle")

        response = self.client.get(f"/study-groups/{group.id}")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Joined", page)
        self.assertIn("Open virtual meeting", page)
        self.assertIn("https://example.edu/scsu-history-circle", page)

    def test_creator_detail_shows_delete_instead_of_leave(self) -> None:
        group = self._group_named("Calculus II Problem Session")

        response = self.client.get(f"/study-groups/{group.id}")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Owner", page)
        self.assertIn("Delete group", page)
        self.assertNotIn("Leave group", page)

    def test_join_from_detail_redirects_back_to_detail(self) -> None:
        group = self._group_named("General Chemistry Lab Prep")

        response = self.client.post(
            f"/study-groups/{group.id}/join",
            data={"next": "detail"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/study-groups/{group.id}")

        detail_response = self.client.get(f"/study-groups/{group.id}")
        self.assertIn("Joined", detail_response.get_data(as_text=True))

    def test_leave_from_detail_redirects_back_and_hides_member_access(self) -> None:
        group = self._group_named("Research Writing Circle")

        response = self.client.post(
            f"/study-groups/{group.id}/leave",
            data={"next": "detail"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/study-groups/{group.id}")

        detail_response = self.client.get(f"/study-groups/{group.id}")
        page = detail_response.get_data(as_text=True)
        self.assertIn("Join group", page)
        self.assertIn("Join this group to view the member-only virtual meeting link.", page)
        self.assertNotIn("Open virtual meeting", page)

    def test_creator_can_delete_group_from_detail(self) -> None:
        group = self._group_named("Calculus II Problem Session")

        response = self.client.post(f"/study-groups/{group.id}/delete")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/listings")

        listings_response = self.client.get("/listings")
        self.assertNotIn(
            "Calculus II Problem Session",
            listings_response.get_data(as_text=True),
        )
        detail_response = self.client.get(f"/study-groups/{group.id}")
        self.assertEqual(detail_response.status_code, 404)

    def test_non_creator_cannot_delete_group(self) -> None:
        group = self._group_named("Anatomy Lab Review")

        response = self.client.post(f"/study-groups/{group.id}/delete")

        self.assertEqual(response.status_code, 302)
        detail_response = self.client.get(f"/study-groups/{group.id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Anatomy Lab Review", detail_response.get_data(as_text=True))

    def test_full_group_detail_shows_full_state_for_non_member(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        test_user = store.find_by_email("test@southernct.edu")
        john = store.find_by_email("john.smith@southernct.edu")
        sarah = store.find_by_email("sarah.lee@southernct.edu")
        assert test_user is not None
        assert john is not None
        assert sarah is not None

        group = store.create_study_group(
            test_user.id,
            title="Two Seat Review",
            subject="CSC 330",
            description="A small review session.",
            start_at=None,
            end_at=None,
            modality="In person",
            location="Engleman Hall",
            meeting_link="",
            max_members=2,
        )
        store.join_study_group(john.id, group.id)

        with self.client.session_transaction() as session:
            session["user_id"] = str(sarah.id)

        response = self.client.get(f"/study-groups/{group.id}")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Full", page)
        self.assertNotIn("Join group", page)

    def test_unknown_group_returns_404(self) -> None:
        response = self.client.get("/study-groups/not-a-real-group")

        self.assertEqual(response.status_code, 404)

    def test_closed_group_cannot_be_joined_even_with_seats(self) -> None:
        current_user = User(firstName="Current", lastName="Student")
        host = User(firstName="Group", lastName="Host")
        group = StudyGroup(
            title="Closed Review",
            maxMembers=8,
            status="closed",
            creator=host,
        )

        view_model = study_group_view_model(group, current_user)

        self.assertTrue(view_model["has_available_seat"])
        self.assertFalse(view_model["can_join"])

    def _group_named(self, title: str):
        store = SQLiteStudyGroupStore(self.database_path)
        _, groups = store.study_group_listing_data(None)
        return next(group for group in groups if group.title == title)

    def _sign_in_as(self, email: str) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        user = store.find_by_email(email)
        assert user is not None
        with self.client.session_transaction() as session:
            session["user_id"] = str(user.id)


if __name__ == "__main__":
    unittest.main()
