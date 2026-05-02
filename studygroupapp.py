from flask import Flask, render_template

def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        return "Study Group App"

    @app.route("/messages")
    def messages():
        return render_template("messages.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
