from flask import Flask, render_template, request, redirect

def create_app():
    app = Flask(__name__)

    # Multi-user chats
    messages_dict = {
        "John Smith": [
            {"sender": "John Smith", "text": "Hey, are we meeting today?"},
            {"sender": "You", "text": "Yes, at 3 PM in the library."}
        ],
        "Sarah Lee": [],
        "Group Chat": []
    }

    @app.route("/messages", methods=["GET", "POST"])
    def messages():
        user = request.args.get("user", "John Smith")

        if request.method == "POST":
            new_message = request.form.get("message")

            if new_message:
                messages_dict[user].append({
                    "sender": "You",
                    "text": new_message
                })

            return redirect(f"/messages?user={user}")

        return render_template(
            "messages.html",
            messages=messages_dict[user],
            current_user=user
        )

    @app.route("/register", methods=["GET", "POST"])
    def register():
        notice = None

        if request.method == "POST":
            notice = "This main branch now includes the register page layout, but account storage is not wired up here yet."

        return render_template("register.html", notice=notice)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
