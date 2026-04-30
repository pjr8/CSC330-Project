from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        return "Study Group App"

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
