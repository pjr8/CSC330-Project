from flask import Flask

from accounts import accounts_bp
from study_groups import study_groups_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(study_groups_bp)

    @app.route("/")
    def index() -> str:
        return "Study Group App"

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
