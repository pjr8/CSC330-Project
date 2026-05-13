from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from email_notifications import send_group_message_notification


class EmailNotificationsTestCase(unittest.TestCase):
    def test_missing_smtp_settings_do_not_crash(self) -> None:
        output = io.StringIO()

        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            send_group_message_notification(
                recipients=["student@southernct.edu"],
                group_title="Software Design Studio",
                sender_name="Test User",
                content="Can everyone review the schema?",
            )

        self.assertIn("Email notifications are not configured", output.getvalue())


if __name__ == "__main__":
    unittest.main()
