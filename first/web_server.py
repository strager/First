import flask
from uuid import uuid4
from urllib.parse import quote_plus
import first.config
from werkzeug.exceptions import HTTPException
import logging

twitch_config = first.config.cfg["twitch"]

logger = logging.getLogger(__name__)

class UnexpectedTwitchOAuthError(HTTPException):
    code = 500

    def __init__(self, error: str, error_description: str) -> None:
        super().__init__()
        self.error = error
        self.error_description = error_description

    @property
    def description(self) -> str:
        return f"Error from Twitch: {self.error_description} (code: {self.error})"

def create_app() -> flask.Flask:
    app = flask.Flask(__name__)

    @app.route("/")
    def hello_world():
        return "<p>Hello, World!</p>"

    @app.get("/login")
    def log_in_view():
        return flask.render_template('login.html')

    @app.get("/oauth/twitch")
    def oauth_twitch():
        error = flask.request.args.get('error', None)
        if error is not None:
            raise UnexpectedTwitchOAuthError(error, flask.request.args.get('error_description', ''))
        return "hello"

    @app.post("/login")
    def log_in():
        state = ""
        scopes = ["channel:read:redemptions", "channel:manage:redemptions"]
        redirect_uri = flask.url_for(oauth_twitch.__name__, _external=True)
        url = (
            f"https://id.twitch.tv/oauth2/authorize?response_type=code"
            f"&client_id={quote_plus(twitch_config['client_id'])}"
            f"&redirect_uri={quote_plus(redirect_uri)}"
            f"&scope={quote_plus(' '.join(scopes))}"
            f"&state={quote_plus(state)}"
        )
        return flask.redirect(url, code=303)

    @app.errorhandler(UnexpectedTwitchOAuthError)
    def unexpected_twitch_oauth_error(error):
        # TODO(security): HTML-escape.
        logger.error(error)
        return error.description, 500

    return app

if __name__ == "__main__":
    create_app()
