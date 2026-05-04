from __future__ import annotations

import re
from typing import Protocol

from flask import Blueprint, current_app, redirect, render_template, request
from werkzeug.security import generate_password_hash

from models import User

from .store import InMemoryAccountStore


SCSU_EMAIL_PATTERN = re.compile(r"^[^@\s]+@southernct\.edu$")
REQUIRED_FIELDS = (
    "firstName",
    "lastName",
    "scsuEmail",
    "password",
    "confirmPassword",
    "major",
    "interests",
    "bio",
)


class AccountStore(Protocol):
    def find_by_email(self, email: str) -> User | None:
        ...

    def create_user(self, user: User) -> User:
        ...


accounts_bp = Blueprint("accounts", __name__)
default_account_store = InMemoryAccountStore()


@accounts_bp.route("/signup", methods=["GET", "POST"])
def signup() -> str:
    if request.method == "POST":
        form_data = _sticky_form_data()
        errors = _validate_signup_form()

        if not errors:
            store = _account_store()
            normalized_email = InMemoryAccountStore.normalize_email(
                request.form.get("scsuEmail", "")
            )

            if store.find_by_email(normalized_email) is not None:
                errors["scsuEmail"] = "An account with this SCSU email already exists."
            else:
                user = User(
                    scsuEmail=normalized_email,
                    passwordHash=generate_password_hash(
                        request.form.get("password", "")
                    ),
                    firstName=form_data["firstName"],
                    lastName=form_data["lastName"],
                    major=form_data["major"],
                    interests=_parse_interests(form_data["interests"]),
                    bio=form_data["bio"],
                )
                store.create_user(user)
                return redirect("/home")

        return render_template(
            "accounts/signup.html",
            form_data=form_data,
            errors=errors,
            error_summary=_error_summary(errors),
        )

    return render_template(
        "accounts/signup.html",
        form_data=_empty_form_data(),
        errors={},
        error_summary=[],
    )


def _account_store() -> AccountStore:
    return current_app.config.get("ACCOUNT_STORE", default_account_store)


def _validate_signup_form() -> dict[str, str]:
    errors: dict[str, str] = {}

    for field_name in REQUIRED_FIELDS:
        if not request.form.get(field_name, "").strip():
            errors[field_name] = "Please complete all required fields."

    email = InMemoryAccountStore.normalize_email(request.form.get("scsuEmail", ""))
    if email and SCSU_EMAIL_PATTERN.fullmatch(email) is None:
        errors["scsuEmail"] = "Use a valid @southernct.edu email address."

    password = request.form.get("password", "")
    confirm_password = request.form.get("confirmPassword", "")
    if password and confirm_password and password != confirm_password:
        errors["confirmPassword"] = "Passwords must match."

    return errors


def _sticky_form_data() -> dict[str, str]:
    return {
        "firstName": request.form.get("firstName", "").strip(),
        "lastName": request.form.get("lastName", "").strip(),
        "scsuEmail": InMemoryAccountStore.normalize_email(
            request.form.get("scsuEmail", "")
        ),
        "major": request.form.get("major", "").strip(),
        "interests": request.form.get("interests", "").strip(),
        "bio": request.form.get("bio", "").strip(),
    }


def _empty_form_data() -> dict[str, str]:
    return {
        "firstName": "",
        "lastName": "",
        "scsuEmail": "",
        "major": "",
        "interests": "",
        "bio": "",
    }


def _parse_interests(interests: str) -> list[str]:
    return [
        interest.strip()
        for interest in interests.split(",")
        if interest.strip()
    ]


def _error_summary(errors: dict[str, str]) -> list[str]:
    unique_messages: list[str] = []
    for message in errors.values():
        if message not in unique_messages:
            unique_messages.append(message)
    return unique_messages
