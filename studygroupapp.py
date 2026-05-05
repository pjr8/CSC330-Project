from flask import Flask, render_template, request, redirect, url_for
from models import User, StudyGroup

from study_groups import study_groups_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(study_groups_bp)

    test_user = User(
        scsuEmail="test@southernct.edu",
        passwordHash="1234",
        firstName="Test",
        lastName="User",
        major="Computer Science",
    )

    profile_user = {
        "firstName": "Bianka",
        "lastName": "Edouard",
        "major": "Computer Science",
        "bio": "Student interested in web development, Python, and building useful campus tools.",
        "scsuEmail": "student@example.com",
        "interests": ["Flask", "UI design", "algorithms"],
        "contactInfo": "",
    }

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

    # Keep separate threads so the messaging page can switch between users.
    messages_dict = {
        "John Smith": [
            {"sender": "John Smith", "text": "Hey, are we meeting today?"},
            {"sender": "You", "text": "Yes, at 3 PM in the library."},
        ],
        "Sarah Lee": [],
        "Group Chat": [],
    }

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
        return redirect(url_for("study_groups.listings"))

    @app.route("/browse")
    def browse_groups():
        return redirect(url_for("study_groups.listings"))

    @app.route("/messages", methods=["GET", "POST"])
    def messages():
        user = request.args.get("user", "John Smith")
        if user not in messages_dict:
            user = "John Smith"

        if request.method == "POST":
            new_message = request.form.get("message", "").strip()

            if new_message:
                messages_dict[user].append({
                    "sender": "You",
                    "text": new_message,
                })

            return redirect(url_for("messages", user=user))

        return render_template(
            "messages.html",
            messages=messages_dict[user],
            current_user=user,
        )

    @app.route("/profile")
    def profile():
        return render_template("profile.html", user=profile_user)

    @app.route("/update-profile", methods=["GET", "POST"])
    def update_profile():
        if request.method == "POST":
            profile_user["firstName"] = request.form.get("firstName")
            profile_user["lastName"] = request.form.get("lastName")
            profile_user["major"] = request.form.get("major")
            profile_user["bio"] = request.form.get("bio")
            profile_user["contactInfo"] = request.form.get("contactInfo")

            interests = request.form.get("interests")
            profile_user["interests"] = [
                interest.strip()
                for interest in interests.split(",")
                if interest.strip()
            ] if interests else []

            return redirect(url_for("profile"))

        return render_template("update_profile.html", user=profile_user)

    @app.route("/register")
    def register():
        return render_template("register.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
