from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


REQUIRED_SMTP_SETTINGS = ("SMTP_HOST", "SMTP_PORT", "SMTP_FROM_EMAIL")


def send_group_message_notification(
    *,
    recipients: list[str],
    group_title: str,
    sender_name: str,
    content: str,
) -> None:
    recipients = [email for email in recipients if email]
    if not recipients:
        return

    missing_settings = [
        setting for setting in REQUIRED_SMTP_SETTINGS if not os.environ.get(setting)
    ]
    if missing_settings:
        print(
            "Email notifications are not configured; missing "
            + ", ".join(missing_settings)
        )
        return

    host = os.environ["SMTP_HOST"]
    try:
        port = int(os.environ["SMTP_PORT"])
    except ValueError:
        print("Email notifications are not configured; SMTP_PORT must be a number")
        return

    from_email = os.environ["SMTP_FROM_EMAIL"]
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    message = EmailMessage()
    message["Subject"] = f"New message in {group_title}"
    message["From"] = from_email
    message["To"] = ", ".join(recipients)
    message.set_content(
        f"{sender_name} posted a new message in {group_title}:\n\n{content}"
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        print(f"Email notification could not be sent: {exc}")
