from flask import Flask, render_template, request, redirect, session, url_for
from sqlalchemy import and_, or_
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from models import Message, StudyGroup, User
from seed_data import DEMO_EMAIL, seed_database
from study_groups import study_groups_bp


def _get_current_user() -> User:
    user_id = session.get("user_id")
    if user_id is not None:
        current_user = db.session.get(User, user_id)
        if current_user is not None:
            return current_user

    current_user = User.query.filter_by(scsuEmail=DEMO_EMAIL).first()
    if current_user is None:
        raise RuntimeError("Demo user was not seeded into the database.")
    return current_user


def _password_matches(user: User, password: str) -> bool:
    stored_password = user.passwordHash
    if stored_password == password:
        user.passwordHash = generate_password_hash(password)
        db.session.commit()
        return True

    return check_password_hash(stored_password, password)


def _get_message_contacts(current_user: User) -> list[User]:
    return (
        User.query.filter(User.id != current_user.id)
        .order_by(User.firstName.asc(), User.lastName.asc())
        .all()
    )


def _find_contact_by_name(contacts: list[User], full_name: str | None) -> User | None:
    if not contacts:
        return None
    if not full_name:
        return contacts[0]
    for contact in contacts:
        if contact.getFullName() == full_name:
            return contact
    return contacts[0]


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///scsu_study_groups.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "scsu-study-group-dev"

    db.init_app(app)
    app.register_blueprint(study_groups_bp)

    with app.app_context():
        db.create_all()
        seed_database()

    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()

            if not email or not password:
                return render_template("login.html", error="Please fill out all fields.")

            if not email.endswith("@southernct.edu") and not email.endswith(
                "@owls.southernct.edu"
            ):
                return render_template("login.html", error="Please use your SCSU email.")

            user = User.query.filter_by(scsuEmail=email).first()
            if user is None or not _password_matches(user, password):
                return render_template("login.html", error="Invalid email or password.")

            session["user_id"] = user.id
            return redirect(url_for("home"))

        return render_template("login.html")

    @app.route("/home")
    def home():
        current_user = _get_current_user()
        sample_groups = StudyGroup.query.order_by(StudyGroup.startAt.asc()).limit(3).all()
        return render_template("home.html", user=current_user, groups=sample_groups)

    @app.route("/create")
    def create_group():
        return redirect(url_for("study_groups.listings"))

    @app.route("/browse")
    def browse_groups():
        return redirect(url_for("study_groups.listings"))

    @app.route("/messages", methods=["GET", "POST"])
    def messages():
        current_user = _get_current_user()
        contacts = _get_message_contacts(current_user)
        default_contact_name = contacts[0].getFullName() if contacts else None
        selected_contact = _find_contact_by_name(
            contacts, request.args.get("user", default_contact_name)
        )

        if selected_contact is None:
            return render_template(
                "messages.html",
                messages=[],
                contacts=[],
                current_user="",
                signed_in_user=current_user.getFullName(),
            )

        if request.method == "POST":
            new_message = request.form.get("message", "").strip()

            if new_message:
                db.session.add(
                    Message(
                        sender=current_user,
                        recipient=selected_contact,
                        content=new_message,
                    )
                )
                db.session.commit()

            return redirect(url_for("messages", user=selected_contact.getFullName()))

        conversation = (
            Message.query.filter(
                or_(
                    and_(
                        Message.sender_id == current_user.id,
                        Message.recipient_id == selected_contact.id,
                    ),
                    and_(
                        Message.sender_id == selected_contact.id,
                        Message.recipient_id == current_user.id,
                    ),
                )
            )
            .order_by(Message.sentAt.asc())
            .all()
        )

        return render_template(
            "messages.html",
            messages=conversation,
            contacts=contacts,
            current_user=selected_contact.getFullName(),
            signed_in_user=current_user.getFullName(),
        )

    @app.route("/profile")
    def profile():
        return render_template("profile.html", user=_get_current_user())

    @app.route("/update-profile", methods=["GET", "POST"])
    def update_profile():
        current_user = _get_current_user()

        if request.method == "POST":
            interests = request.form.get("interests", "")
            current_user.updateProfile(
                firstName=request.form.get("firstName", "").strip(),
                lastName=request.form.get("lastName", "").strip(),
                major=request.form.get("major", "").strip(),
                bio=request.form.get("bio", "").strip(),
                contactInfo=request.form.get("contactInfo", "").strip(),
                interests=[
                    interest.strip()
                    for interest in interests.split(",")
                    if interest.strip()
                ],
            )
            db.session.commit()

            return redirect(url_for("profile"))

        return render_template("update_profile.html", user=current_user)

    @app.route("/register", methods=["GET"])
    def register():
        return render_template("register.html")

    @app.route("/register", methods=["POST"])
    def register_user():
        first_name = request.form.get("firstName", "").strip()
        last_name = request.form.get("lastName", "").strip()
        major = request.form.get("major", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not first_name or not last_name or not email or not password:
            return render_template(
                "register.html",
                error="Please fill out all required fields.",
            )

        if not email.endswith("@southernct.edu") and not email.endswith(
            "@owls.southernct.edu"
        ):
            return render_template(
                "register.html",
                error="Please register with your SCSU email.",
            )

        if User.query.filter_by(scsuEmail=email).first() is not None:
            return render_template(
                "register.html",
                error="An account with that email already exists.",
            )

        user = User(
            scsuEmail=email,
            passwordHash=generate_password_hash(password),
            firstName=first_name,
            lastName=last_name,
            major=major,
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id

        return redirect(url_for("home"))

    @app.route("/logout")
    def logout():
        session.pop("user_id", None)
        return redirect(url_for("login"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
