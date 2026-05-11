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
            "contactInfo": "jordan.rivera@southernct.edu",
            "password": "study-pass-123",
            "confirmPassword": "study-pass-123",
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
            "contactInfo",
            "password",
            "confirmPassword",
        ):
            self.assertIn(f'name="{field_name}"', page)

        for field_name in ("major", "interests", "bio"):
            self.assertNotIn(f'name="{field_name}"', page)
        self.assertNotIn("/home</span>", page)
        self.assertNotIn("Next step", page)

    def test_missing_fields_return_error(self) -> None:
        response = self.client.post("/signup", data=self.valid_payload(firstName=""))

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Please complete all required fields.", page)
        self.assertIn('aria-invalid="true"', page)
        self.assertIsNone(self.store.find_by_email("jordan.rivera@southernct.edu"))

    def test_contact_info_is_required(self) -> None:
        response = self.client.post(
            "/signup",
            data=self.valid_payload(contactInfo=""),
        )

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Please complete all required fields.", page)
        self.assertIn('id="contactInfo"', page)
        self.assertIn('aria-invalid="true"', page)
        self.assertIsNone(self.store.find_by_email("jordan.rivera@southernct.edu"))

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

    def test_invalid_passwords_are_rejected_without_creating_user(self) -> None:
        cases = (
            (
                "missing password",
                {"password": ""},
                "Please complete all required fields.",
            ),
            (
                "whitespace password",
                {"password": "        "},
                "Please complete all required fields.",
            ),
            (
                "leading password space",
                {
                    "password": " study-pass-123",
                    "confirmPassword": " study-pass-123",
                },
                "Password cannot start or end with spaces.",
            ),
            (
                "trailing password space",
                {
                    "password": "study-pass-123 ",
                    "confirmPassword": "study-pass-123 ",
                },
                "Password cannot start or end with spaces.",
            ),
            (
                "short password",
                {"password": "short7", "confirmPassword": "short7"},
                "Password must be at least 8 characters.",
            ),
        )

        for index, (name, overrides, expected_message) in enumerate(cases):
            email = f"jordan.rivera{index}@southernct.edu"
            with self.subTest(name=name):
                response = self.client.post(
                    "/signup",
                    data=self.valid_payload(scsuEmail=email, **overrides),
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_message, response.get_data(as_text=True))
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
            data=self.valid_payload(
                scsuEmail="  Jordan.Rivera@SOUTHERNCT.EDU  ",
                major="Computer Science",
                interests="Software design, Mathematics, Research writing",
                bio="I like building campus tools and reviewing software projects.",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/home")

        user = self.store.find_by_email("jordan.rivera@southernct.edu")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.scsuEmail, "jordan.rivera@southernct.edu")
        self.assertEqual(user.firstName, "Jordan")
        self.assertEqual(user.lastName, "Rivera")
        self.assertEqual(user.major, "")
        self.assertEqual(user.interests, [])
        self.assertEqual(user.bio, "")
        self.assertEqual(user.contactInfo, "jordan.rivera@southernct.edu")
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
