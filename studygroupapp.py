from flask import Flask, request, redirect, render_template, url_for

app = Flask(__name__)

# temporary "global user" for testing
user_data = {
    "firstName": "Bianka",
    "lastName": "Edouard",
    "major": "Computer Science",
    "bio": "Student interested in web development, Python, and building useful campus tools.",
    "scsuEmail": "student@example.com",
    "interests": ["Flask", "UI design", "algorithms"]
}


@app.route("/profile")
def profile():
    return render_template("profile.html", user=user_data)


@app.route("/update-profile", methods=["GET", "POST"])
def update_profile():
    if request.method == "POST":

        user_data["firstName"] = request.form.get("firstName")
        user_data["lastName"] = request.form.get("lastName")
        user_data["major"] = request.form.get("major")
        user_data["bio"] = request.form.get("bio")
        user_data["contactInfo"] = request.form.get("contactInfo")

        interests = request.form.get("interests")
        user_data["interests"] = [i.strip() for i in interests.split(",")] if interests else []

        return redirect(url_for("profile"))

    return render_template("update_profile.html", user=user_data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")