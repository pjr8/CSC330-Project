import unittest

from werkzeug.security import check_password_hash

from accounts import InMemoryAccountStore
from studygroupapp import create_app


class SignupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.store = InMemoryAccountStore()
        self.app.config.update(
            TESTING=True,
            ACCOUNT_STORE=self.store,
        )
        self.client = self.app.test_client()

    def valid_payload(self, **overrides: str) -> dict[str, str]:
        payload = {
            "firstName": "Jordan",
            "lastName": "Rivera",
            "scsuEmail": "jordan.rivera@southernct.edu",
            "password": "study-pass-123",
            "confirmPassword": "study-pass-123",
            "major": "Computer Science",
            "interests": "Software design, Mathematics, Research writing",
            "bio": "I like building campus tools and reviewing software projects.",
        }
        payload.update(overrides)
        return payload

    def test_get_signup_renders_required_fields(self) -> None:
        response = self.client.get("/signup")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for field_name in (
            "firstName",
            "lastName",
            "scsuEmail",
            "password",
            "confirmPassword",
            "major",
            "interests",
            "bio",
        ):
            self.assertIn(f'name="{field_name}"', page)

    def test_missing_fields_return_error(self) -> None:
        response = self.client.post("/signup", data=self.valid_payload(firstName=""))

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Please complete all required fields.", page)
        self.assertIn('aria-invalid="true"', page)

    def test_invalid_email_domains_are_rejected(self) -> None:
        invalid_addresses = (
            "student@example.com",
            "student@owls.southernct.edu",
        )

        for email in invalid_addresses:
            with self.subTest(email=email):
                response = self.client.post(
                    "/signup",
                    data=self.valid_payload(scsuEmail=email),
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "Use a valid @southernct.edu email address.",
                    response.get_data(as_text=True),
                )
                self.assertIsNone(self.store.find_by_email(email))

    def test_password_mismatch_is_rejected(self) -> None:
        response = self.client.post(
            "/signup",
            data=self.valid_payload(confirmPassword="different-pass"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Passwords must match.", response.get_data(as_text=True))
        self.assertIsNone(self.store.find_by_email("jordan.rivera@southernct.edu"))

    def test_valid_signup_creates_user_and_redirects_to_home(self) -> None:
        response = self.client.post(
            "/signup",
            data=self.valid_payload(scsuEmail="  Jordan.Rivera@SOUTHERNCT.EDU  "),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/home")

        user = self.store.find_by_email("jordan.rivera@southernct.edu")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.scsuEmail, "jordan.rivera@southernct.edu")
        self.assertEqual(user.firstName, "Jordan")
        self.assertEqual(user.lastName, "Rivera")
        self.assertEqual(user.major, "Computer Science")
        self.assertEqual(
            user.interests,
            ["Software design", "Mathematics", "Research writing"],
        )
        self.assertEqual(
            user.bio,
            "I like building campus tools and reviewing software projects.",
        )
        self.assertEqual(user.status, "active")
        self.assertEqual(user.role, "student")
        self.assertTrue(check_password_hash(user.passwordHash, "study-pass-123"))
        self.assertNotEqual(user.passwordHash, "study-pass-123")
        self.assertIsNotNone(user.preference)
        self.assertIs(user.preference.user, user)

    def test_duplicate_normalized_email_is_rejected(self) -> None:
        self.client.post("/signup", data=self.valid_payload())

        response = self.client.post(
            "/signup",
            data=self.valid_payload(
                firstName="Jamie",
                scsuEmail="JORDAN.RIVERA@SOUTHERNCT.EDU",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "An account with this SCSU email already exists.",
            response.get_data(as_text=True),
        )

        user = self.store.find_by_email("jordan.rivera@southernct.edu")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.firstName, "Jordan")


if __name__ == "__main__":
    unittest.main()
