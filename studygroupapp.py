from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from flask import Flask, abort, redirect, render_template, request, session, url_for

from accounts import accounts_bp
from app_store import SQLiteStudyGroupStore
from messages import messages_bp
from study_groups import study_groups_bp


CREATE_GROUP_MODALITIES = ("In person", "Hybrid", "Virtual")
PUBLIC_ENDPOINTS = {"index", "register", "accounts.signup", "static"}
CREATE_GROUP_REQUIRED_FIELDS = {
    "title": "Enter a study group title.",
    "subject": "Enter the course or subject.",
    "description": "Add a short description.",
    "meetingDate": "Choose a meeting date.",
    "startTime": "Choose a start time.",
    "endTime": "Choose an end time.",
    "modality": "Choose a meeting format.",
    "maxMembers": "Enter a group capacity.",
}


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=str(Path(app.instance_path) / "studygroups.sqlite3"),
    )

    if test_config is not None:
        app.config.update(test_config)

    store = app.config.get("DATA_STORE")
    if store is None:
        store = SQLiteStudyGroupStore(app.config["DATABASE"])
        store.initialize()
        app.config["DATA_STORE"] = store

    app.config.setdefault("ACCOUNT_STORE", store)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(study_groups_bp)
    app.register_blueprint(messages_bp)

    def data_store() -> SQLiteStudyGroupStore:
        return app.config["DATA_STORE"]

    def current_user():
        return data_store().get_user(session.get("user_id"))

    @app.context_processor
    def inject_session_user():
        user = current_user()
        return {
            "is_logged_in": user is not None,
            "session_user": user,
        }

    @app.before_request
    def require_login_for_app_pages():
        endpoint = request.endpoint
        if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
            return None

        if current_user() is not None:
            return None

        session.clear()
        return redirect(url_for("index"))

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()

            if not email or not password:
                return render_template("login.html", error="Please fill out all fields.")

            if not email.lower().endswith("@southernct.edu"):
                return render_template("login.html", error="Please use your SCSU email.")

            user = data_store().authenticate_user(email, password)
            if user is not None:
                session["user_id"] = str(user.id)
                return redirect(url_for("home"))

            return render_template("login.html", error="Invalid email or password.")

        if current_user() is not None:
            return redirect(url_for("home"))

        return render_template("login.html")

    @app.route("/home")
    def home():
        user = current_user()
        _, groups = data_store().study_group_listing_data(str(user.id))
        return render_template("home.html", user=user, groups=groups[:3])

    @app.route("/create", methods=["GET", "POST"])
    def create_group():
        user = current_user()

        if request.method == "POST":
            form_data = _create_group_form_data()
            errors = _validate_create_group_form(form_data)

            if not errors:
                data_store().create_study_group(
                    session.get("user_id"),
                    title=form_data["title"],
                    subject=form_data["subject"],
                    description=form_data["description"],
                    start_at=_parse_create_group_datetime(
                        form_data["meetingDate"],
                        form_data["startTime"],
                    ),
                    end_at=_parse_create_group_datetime(
                        form_data["meetingDate"],
                        form_data["endTime"],
                    ),
                    modality=form_data["modality"],
                    location=form_data["location"],
                    meeting_link=form_data["meetingLink"],
                    max_members=int(form_data["maxMembers"]),
                )
                return redirect(url_for("study_groups.listings"))

            return render_template(
                "study_groups/create.html",
                current_user=user,
                form_data=form_data,
                errors=errors,
                error_summary=_error_summary(errors),
                modalities=CREATE_GROUP_MODALITIES,
            )

        return render_template(
            "study_groups/create.html",
            current_user=user,
            form_data=_empty_create_group_form_data(),
            errors={},
            error_summary=[],
            modalities=CREATE_GROUP_MODALITIES,
        )

    @app.route("/browse")
    def browse_groups():
        return redirect(url_for("study_groups.listings"))

    @app.route("/profile")
    @app.route("/profile/<uuid:user_id>")
    def profile(user_id: UUID | None = None):
        session_user = current_user()
        user = session_user if user_id is None else data_store().get_user(user_id)
        if user is None:
            abort(404)

        return render_template(
            "profile.html",
            user=user,
            is_own_profile=user.id == session_user.id,
        )

    @app.route("/update-profile", methods=["GET", "POST"])
    def update_profile():
        user = current_user()

        if request.method == "POST":
            interests = request.form.get("interests", "")
            data_store().update_user_profile(
                user.id,
                first_name=request.form.get("firstName", "").strip(),
                last_name=request.form.get("lastName", "").strip(),
                major=request.form.get("major", "").strip(),
                bio=request.form.get("bio", "").strip(),
                contact_info=request.form.get("contactInfo", "").strip(),
                interests=[
                    interest.strip()
                    for interest in interests.split(",")
                    if interest.strip()
                ],
            )
            return redirect(url_for("profile"))

        return render_template("update_profile.html", user=user)

    @app.route("/register")
    def register():
        return redirect(url_for("accounts.signup"))

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    return app


def _create_group_form_data() -> dict[str, str]:
    return {
        "title": request.form.get("title", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "description": request.form.get("description", "").strip(),
        "meetingDate": request.form.get("meetingDate", "").strip(),
        "startTime": request.form.get("startTime", "").strip(),
        "endTime": request.form.get("endTime", "").strip(),
        "modality": request.form.get("modality", "").strip(),
        "location": request.form.get("location", "").strip(),
        "meetingLink": request.form.get("meetingLink", "").strip(),
        "maxMembers": request.form.get("maxMembers", "").strip(),
    }


def _empty_create_group_form_data() -> dict[str, str]:
    return {field_name: "" for field_name in _create_group_form_data_keys()}


def _create_group_form_data_keys() -> tuple[str, ...]:
    return (
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
    )


def _validate_create_group_form(form_data: dict[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}

    for field_name, message in CREATE_GROUP_REQUIRED_FIELDS.items():
        if not form_data[field_name]:
            errors[field_name] = message

    modality = form_data["modality"]
    if modality and modality not in CREATE_GROUP_MODALITIES:
        errors["modality"] = "Choose a valid meeting format."

    if modality in {"In person", "Hybrid"} and not form_data["location"]:
        errors["location"] = "Enter a campus location for in-person meetings."

    if modality in {"Hybrid", "Virtual"} and not form_data["meetingLink"]:
        errors["meetingLink"] = "Enter a meeting link for virtual access."

    start_at = _parse_create_group_datetime(
        form_data["meetingDate"],
        form_data["startTime"],
    )
    end_at = _parse_create_group_datetime(
        form_data["meetingDate"],
        form_data["endTime"],
    )
    if form_data["meetingDate"] and form_data["startTime"] and start_at is None:
        errors["startTime"] = "Enter a valid start date and time."
    if form_data["meetingDate"] and form_data["endTime"] and end_at is None:
        errors["endTime"] = "Enter a valid end date and time."
    if start_at is not None and end_at is not None and end_at <= start_at:
        errors["endTime"] = "End time must be after the start time."

    if form_data["maxMembers"]:
        try:
            max_members = int(form_data["maxMembers"])
        except ValueError:
            errors["maxMembers"] = "Enter a capacity between 2 and 30."
        else:
            if max_members < 2 or max_members > 30:
                errors["maxMembers"] = "Enter a capacity between 2 and 30."

    return errors


def _parse_create_group_datetime(date_value: str, time_value: str) -> datetime | None:
    if not date_value or not time_value:
        return None

    try:
        return datetime.fromisoformat(f"{date_value}T{time_value}")
    except ValueError:
        return None


def _error_summary(errors: dict[str, str]) -> list[str]:
    unique_messages: list[str] = []
    for message in errors.values():
        if message not in unique_messages:
            unique_messages.append(message)
    return unique_messages


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
