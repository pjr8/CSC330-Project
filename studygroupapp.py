from flask import Flask, render_template
from models import User  # type: ignore

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/profile")
def profile():
    user = User(
        firstName="Bianka",
        lastName="Edouard",
        scsuEmail="student@example.com",
        major="Computer Science",
        bio="Student interested in web development, Python, and building useful campus tools.",
        interests=["Flask", "UI design", "algorithms"]
    )

    return render_template("profile.html", user=user)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)