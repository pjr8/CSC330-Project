import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from flask import render_template

from studygroupapp import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class HeaderParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self._current_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "img":
            self.images.append(attributes)
        if tag == "a":
            attributes["text"] = ""
            self.links.append(attributes)
            self._current_link = attributes

    def handle_data(self, data: str) -> None:
        if self._current_link is not None:
            self._current_link["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._current_link = None


class AuthHeaderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "app.sqlite3"),
                "SECRET_KEY": "test-secret",
            }
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def render_header(self, active_page: str = "messages") -> str:
        with self.app.test_request_context("/messages"):
            return render_template(
                "partials/_app_header.html",
                active_page=active_page,
            )

    def parsed_header(self, active_page: str = "messages") -> HeaderParser:
        parser = HeaderParser()
        parser.feed(self.render_header(active_page))
        return parser

    def test_header_uses_single_official_scsu_logo_image(self) -> None:
        parser = self.parsed_header()

        self.assertEqual(len(parser.images), 1)
        self.assertEqual(parser.images[0]["src"], "/static/images/scsu-logo.png")
        self.assertEqual(
            parser.images[0]["alt"],
            "Southern Connecticut State University",
        )
        self.assertNotIn(">SC<", self.render_header())

    def test_header_exposes_logged_in_navigation_links(self) -> None:
        parser = self.parsed_header()
        nav_links = {
            link["text"].strip(): link["href"]
            for link in parser.links
            if link["text"].strip()
        }

        self.assertEqual(
            nav_links,
            {
                "Home": "/home",
                "Listings": "/listings",
                "Messages": "/messages",
                "Profile": "/profile",
                "Logout": "/logout",
            },
        )

    def test_header_marks_active_navigation_link(self) -> None:
        parser = self.parsed_header(active_page="listings")
        active_links = [
            link
            for link in parser.links
            if link.get("aria-current") == "page"
        ]

        self.assertEqual(len(active_links), 1)
        self.assertEqual(active_links[0]["text"].strip(), "Listings")
        self.assertIn("app-header__nav-link--active", active_links[0]["class"])

    def test_logged_out_app_pages_redirect_to_login(self) -> None:
        client = self.app.test_client()

        for path in (
            "/home",
            "/listings",
            "/create",
            "/messages",
            "/profile",
            "/update-profile",
            "/study-groups/not-a-real-group",
        ):
            with self.subTest(path=path):
                response = client.get(path)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/")

    def test_header_css_defines_required_brand_colors_and_mobile_wrapping(self) -> None:
        css = (PROJECT_ROOT / "static/css/header.css").read_text(encoding="utf-8")

        for color in ("#003399", "#00ADEB", "#FFCC40"):
            self.assertIn(color, css)
        self.assertIn("flex-wrap: wrap", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn(".app-header__nav-link--active", css)


if __name__ == "__main__":
    unittest.main()
