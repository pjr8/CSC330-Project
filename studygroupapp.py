from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, redirect, render_template, request, session, url_for

from accounts import accounts_bp
from app_store import SQLiteStudyGroupStore
from study_groups import study_groups_bp


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

    def data_store() -> SQLiteStudyGroupStore:
        return app.config["DATA_STORE"]

    def current_user():
        return data_store().user_for_session(session.get("user_id"))

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

        return render_template("login.html")

    @app.route("/home")
    def home():
        user = current_user()
        _, groups = data_store().study_group_listing_data(str(user.id))
        return render_template("home.html", user=user, groups=groups[:3])

    @app.route("/create")
    def create_group():
        return redirect(url_for("study_groups.listings"))

    @app.route("/browse")
    def browse_groups():
        return redirect(url_for("study_groups.listings"))

    @app.route("/messages", methods=["GET", "POST"])
    def messages():
        store = data_store()
        user = current_user()
        conversations = store.list_conversations()
        conversation_name = request.args.get("user") or (
            conversations[0] if conversations else "John Smith"
        )

        if request.method == "POST":
            store.add_outgoing_message(
                conversation_name,
                request.form.get("message", ""),
                str(user.id),
            )
            return redirect(url_for("messages", user=conversation_name))

        if conversation_name not in conversations:
            conversations.append(conversation_name)

        return render_template(
            "messages.html",
            messages=store.messages_for_conversation(conversation_name, str(user.id)),
            conversations=conversations,
            current_user=conversation_name,
        )

    @app.route("/profile")
    def profile():
        return render_template("profile.html", user=current_user())

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


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
