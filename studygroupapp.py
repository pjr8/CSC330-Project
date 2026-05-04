from flask import Flask, render_template, request, redirect

def create_app() -> Flask:
    app = Flask(__name__)

    # Temporary message storage
    messages_list = [
        {"sender": "John Smith", "text": "Hey, are we meeting today?"},
        {"sender": "You", "text": "Yes, at 3 PM in the library."}
    ]

    @app.route("/")
    def index() -> str:
        return "Study Group App"

    @app.route("/messages", methods=["GET", "POST"])
    def messages():
        if request.method == "POST":
            new_message = request.form.get("message")

            if new_message:
                messages_list.append({"sender": "You", "text": new_message})

            return redirect("/messages")

        return render_template("messages.html", messages=messages_list)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
