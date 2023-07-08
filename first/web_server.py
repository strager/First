import flask
from uuid import uuid4
from urllib.parse import quote_plus
import first.config

twitch_config = first.config.cfg["twitch"]

def create_app() -> flask.Flask:
    app = flask.Flask(__name__)

    @app.route("/")
    def hello_world():
        return "<p>Hello, World!</p>"

    @app.get("/login")
    def log_in_view():
        return flask.render_template('login.html')

    @app.post("/login")
    def log_in():
        state = ""
        scopes = ["channel:read:redemptions", "channel:manage:redemptions"]
        url = (
            f"https://id.twitch.tv/oauth2/authorize?response_type=code"
            f"&client_id={quote_plus(twitch_config['client_id'])}"
            f"&redirect_uri={quote_plus(twitch_config['redirect_uri'])}"
            f"&scope={quote_plus(' '.join(scopes))}"
            f"&state={quote_plus(state)}"
        )
        return flask.redirect(url, code=303)

    return app

if __name__ == "__main__":
    create_app()
