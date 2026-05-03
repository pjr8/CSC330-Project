from flask import Flask, render_template, request, redirect, url_for
from models import User, StudyGroup

from study_groups import study_groups_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(study_groups_bp)

    test_user = User(
        scsuEmail="test@southernct.edu",
        passwordHash="1234",
        firstName="Test",
        lastName="User",
        major="Computer Science",
    )

    sample_groups = [
        StudyGroup(
            title="CSC 330 Study Group",
            subject="Software Engineering",
            description="Reviewing project requirements.",
        ),
        StudyGroup(
            title="CSC 212 Study Group",
            subject="Data Structures",
            description="Practice with linked lists and sorting.",
        ),
        StudyGroup(
            title="Networking Exam Prep",
            subject="Computer Networks",
            description="Reviewing IP, subnetting, and routing.",
        ),
    ]

    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()

            if not email or not password:
                return render_template("login.html", error="Please fill out all fields.")

            if not email.endswith("@southernct.edu"):
                return render_template("login.html", error="Please use your SCSU email.")

            if email == test_user.scsuEmail and password == test_user.passwordHash:
                return redirect(url_for("home"))

            return render_template("login.html", error="Invalid email or password.")

        return render_template("login.html")

    @app.route("/home")
    def home():
        return render_template("home.html", user=test_user, groups=sample_groups)

    @app.route("/create")
    def create_group():
        return "Create Group Page Coming Soon"

    @app.route("/browse")
    def browse_groups():
        return "Browse Groups Page Coming Soon"

    @app.route("/messages")
    def messages():
        return render_template("messages.html")

    @app.route("/register")
    def register():
        return render_template("register.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)