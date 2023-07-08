import flask
from uuid import uuid4
from urllib.parse import quote_plus
from first.authdb import AuthDb
import first.config
from werkzeug.exceptions import HTTPException
import logging
import requests
import typing

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

def create_app(authdb: AuthDb = AuthDb()) -> flask.Flask:
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

        code = flask.request.args.get("code", None)
        # TODO(strager): Check code for validity.

        # TODO(strager): Check scopes parameter.

        # TODO[twitch-oauth-state]: Check state parameter.

        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": twitch_config["client_id"],
            "client_secret": twitch_config["client_secret"],
            "redirect_uri": get_twitch_oauth_redirect_uri(),
        }
        response = requests.post("https://id.twitch.tv/oauth2/token", data=data).json()
        access_token = response['access_token']
        refresh_token = response['refresh_token']

        response = requests.get("https://api.twitch.tv/helix/users", headers={
            "Authorization": f"Bearer {access_token}",
            "Client-Id": twitch_config["client_id"],
        }).json()
        user_id = response["data"][0]["id"]
        authdb.add_new_user(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        # TODO(strager): Redirect to the user's dashboard.
        return flask.redirect("/")

    @app.post("/login")
    def log_in():
        # TODO[twitch-oauth-state]: Set a state to avoid CSRF.
        state = ""
        scopes = ["channel:read:redemptions", "channel:manage:redemptions"]
        url = (
            f"https://id.twitch.tv/oauth2/authorize?response_type=code"
            f"&client_id={quote_plus(twitch_config['client_id'])}"
            f"&redirect_uri={quote_plus(get_twitch_oauth_redirect_uri())}"
            f"&scope={quote_plus(' '.join(scopes))}"
            f"&state={quote_plus(state)}"
        )
        return flask.redirect(url, code=303)

    @app.errorhandler(UnexpectedTwitchOAuthError)
    def unexpected_twitch_oauth_error(error):
        # TODO(security): HTML-escape.
        logger.error(error)
        return error.description, 500


    def get_twitch_oauth_redirect_uri() -> str:
        return flask.url_for(oauth_twitch.__name__, _external=True)

    return app

if __name__ == "__main__":
    create_app()
