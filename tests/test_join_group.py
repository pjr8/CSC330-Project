import tempfile
import unittest
from pathlib import Path

from app_store import SQLiteStudyGroupStore
from studygroupapp import create_app


class JoinStudyGroupTestCase(unittest.TestCase):
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

    def test_join_button_posts_membership_and_redirects_to_listings(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        current_user, groups = store.study_group_listing_data(None)
        group = next(
            group for group in groups if group.title == "General Chemistry Lab Prep"
        )

        self.assertFalse(self._is_active_member(group, current_user))

        response = self.client.post(f"/study-groups/{group.id}/join")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/listings")

        current_user, groups = store.study_group_listing_data(None)
        joined_group = next(
            group for group in groups if group.title == "General Chemistry Lab Prep"
        )
        self.assertTrue(self._is_active_member(joined_group, current_user))

    def test_joined_groups_render_joined_state(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        _, groups = store.study_group_listing_data(None)
        group = next(
            group for group in groups if group.title == "General Chemistry Lab Prep"
        )

        self.client.post(f"/study-groups/{group.id}/join")
        response = self.client.get("/listings")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("General Chemistry Lab Prep", page)
        self.assertIn("Joined", page)
        self.assertIn("Leave", page)

    def test_leave_button_marks_membership_left_and_redirects_to_listings(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        current_user, groups = store.study_group_listing_data(None)
        group = next(
            group for group in groups if group.title == "Research Writing Circle"
        )

        self.assertTrue(self._is_active_member(group, current_user))

        response = self.client.post(f"/study-groups/{group.id}/leave")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/listings")

        current_user, groups = store.study_group_listing_data(None)
        left_group = next(
            group for group in groups if group.title == "Research Writing Circle"
        )
        self.assertFalse(self._is_active_member(left_group, current_user))
        self.assertEqual(self._membership_status(left_group, current_user), "left")

    def test_creator_cannot_leave_owned_group(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        current_user, groups = store.study_group_listing_data(None)
        group = next(
            group for group in groups if group.title == "Calculus II Problem Session"
        )

        self.assertTrue(self._is_active_member(group, current_user))
        self.assertFalse(store.leave_study_group(current_user.id, group.id))

        current_user, groups = store.study_group_listing_data(None)
        owned_group = next(
            group for group in groups if group.title == "Calculus II Problem Session"
        )
        self.assertTrue(self._is_active_member(owned_group, current_user))

    def test_left_group_can_be_rejoined(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        current_user, groups = store.study_group_listing_data(None)
        group = next(
            group for group in groups if group.title == "Research Writing Circle"
        )

        self.assertTrue(store.leave_study_group(current_user.id, group.id))
        self.assertTrue(store.join_study_group(current_user.id, group.id))

        current_user, groups = store.study_group_listing_data(None)
        rejoined_group = next(
            group for group in groups if group.title == "Research Writing Circle"
        )
        self.assertTrue(self._is_active_member(rejoined_group, current_user))

    def test_full_group_rejects_join(self) -> None:
        store = SQLiteStudyGroupStore(self.database_path)
        test_user = store.find_by_email("test@southernct.edu")
        john = store.find_by_email("john.smith@southernct.edu")
        sarah = store.find_by_email("sarah.lee@southernct.edu")
        assert test_user is not None
        assert john is not None
        assert sarah is not None

        group = store.create_study_group(
            test_user.id,
            title="Small Review",
            subject="CSC 330",
            description="Two-person review session.",
            start_at=None,
            end_at=None,
            modality="In person",
            location="Engleman Hall",
            meeting_link="",
            max_members=2,
        )

        self.assertTrue(store.join_study_group(john.id, group.id))
        self.assertFalse(store.join_study_group(sarah.id, group.id))

    @staticmethod
    def _is_active_member(group, user) -> bool:
        return any(
            membership.member is not None
            and membership.member.id == user.id
            and membership.status == "active"
            for membership in group.memberships
        )

    @staticmethod
    def _membership_status(group, user) -> str | None:
        membership = next(
            (
                membership
                for membership in group.memberships
                if membership.member is not None and membership.member.id == user.id
            ),
            None,
        )
        return membership.status if membership is not None else None


if __name__ == "__main__":
    unittest.main()
