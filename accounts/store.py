from __future__ import annotations

from models import User


class InMemoryAccountStore:
    """Small account store boundary that can be replaced by SQLite later."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, User] = {}

    def find_by_email(self, email: str) -> User | None:
        return self._users_by_email.get(self.normalize_email(email))

    def create_user(self, user: User) -> User:
        email = self.normalize_email(user.scsuEmail)
        if email in self._users_by_email:
            raise ValueError("duplicate_email")

        user.scsuEmail = email
        self._users_by_email[email] = user
        return user

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()
