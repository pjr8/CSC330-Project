import tempfile
import unittest
from pathlib import Path

from app_store import SQLiteStudyGroupStore
from studygroupapp import create_app


class CreateStudyGroupTestCase(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def valid_payload(self, **overrides: str) -> dict[str, str]:
        payload = {
            "title": "Algorithms Exam Review",
            "subject": "CSC 212 - Data Structures",
            "description": "Practice problems for trees, heaps, graphs, and runtime analysis.",
            "meetingDate": "2026-05-12",
            "startTime": "14:00",
            "endTime": "15:30",
            "modality": "In person",
            "location": "Buley Library, Room 205",
            "meetingLink": "",
            "maxMembers": "8",
        }
        payload.update(overrides)
        return payload

    def test_get_create_renders_form_fields(self) -> None:
        response = self.client.get("/create")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Create Study Group", page)
        self.assertIn("images/scsu-logo.png", page)
        for field_name in (
            "title",
            "subject",
            "description",
            "meetingDate",
            "startTime",
            "endTime",
            "modality",
            "location",
            "meetingLink",
            "maxMembers",
        ):
            self.assertIn(f'name="{field_name}"', page)

    def test_missing_required_fields_return_errors(self) -> None:
        response = self.client.post("/create", data=self.valid_payload(title=""))

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Enter a study group title.", page)
        self.assertIn('aria-invalid="true"', page)

    def test_end_time_must_follow_start_time(self) -> None:
        response = self.client.post(
            "/create",
            data=self.valid_payload(startTime="15:00", endTime="14:30"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "End time must be after the start time.",
            response.get_data(as_text=True),
        )

    def test_valid_submission_persists_group_and_redirects_to_listings(self) -> None:
        response = self.client.post("/create", data=self.valid_payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/listings")

        store = SQLiteStudyGroupStore(self.database_path)
        current_user, groups = store.study_group_listing_data(None)
        created_group = next(
            group for group in groups if group.title == "Algorithms Exam Review"
        )

        self.assertEqual(created_group.subject, "CSC 212 - Data Structures")
        self.assertEqual(created_group.modality, "In person")
        self.assertEqual(created_group.location, "Buley Library, Room 205")
        self.assertEqual(created_group.maxMembers, 8)
        self.assertIsNotNone(created_group.creator)
        assert created_group.creator is not None
        self.assertEqual(created_group.creator.getFullName(), "Test User")
        self.assertTrue(
            any(
                membership.member is not None
                and membership.member.id == current_user.id
                and membership.role == "host"
                for membership in created_group.memberships
            )
        )


if __name__ == "__main__":
    unittest.main()
