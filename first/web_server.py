import flask
from uuid import uuid4
from first.twitch import Twitch, AuthenticatedTwitch
from urllib.parse import quote_plus
from first.authdb import AuthDb, AuthDbUserTokenProvider, UserId
import first.config
from werkzeug.exceptions import HTTPException
import logging
import requests
import typing
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread, TwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate, TwitchEventSubDelegate

# TODO(strager): Fancier logging.
logging.basicConfig(level=logging.INFO)

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

def create_app_for_testing(
    authdb: AuthDb = AuthDb(":memory:"),
    eventsub_websocket_manager: typing.Optional[TwitchEventSubWebSocketManager] = None,
    # Used only if eventsub_websocket_manager is None.
    eventsub_delegate: TwitchEventSubDelegate = stub_twitch_eventsub_delegate,
) -> flask.Flask:
    if eventsub_websocket_manager is None:
        eventsub_websocket_manager = TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, eventsub_delegate)
    return create_app_from_dependencies(authdb=authdb, eventsub_websocket_manager=eventsub_websocket_manager)

def create_app() -> flask.Flask:
    """Create the Flask app for production. Named 'create_app' because that's
    the name that Flask looks for.
    """
    eventsub_delegate = stub_twitch_eventsub_delegate # TODO(strager)
    eventsub_websocket_manager = TwitchEventSubWebSocketManager(TwitchEventSubWebSocketThread, eventsub_delegate)
    return create_app_from_dependencies(
        authdb=AuthDb(),
        eventsub_websocket_manager=eventsub_websocket_manager
    )

def create_app_from_dependencies(
    authdb: AuthDb,
    eventsub_websocket_manager: TwitchEventSubWebSocketManager,
) -> flask.Flask:
    app = flask.Flask(__name__)

    @app.route("/")
    def hello_world():
        return flask.render_template('index.html')

    @app.get("/login")
    def log_in_view():
        return flask.render_template('login.html')

    @app.get("/admin")
    def admin_view():
        return flask.render_template('admin/index.html')

    @app.get("/admin/eventsub")
    def admin_eventsub():
        return flask.render_template('admin/eventsub.html', eventsub_connections=eventsub_websocket_manager.get_all_threads_for_testing())

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

        twitch = Twitch()
        user_id = twitch.get_authenticated_user_id(access_token=access_token)
        authdb.update_or_create_user(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        start_eventsub_for_user(user_id)

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

    def start_eventsub_for_user(user_id: UserId) -> None:
        twitch = AuthenticatedTwitch(AuthDbUserTokenProvider(authdb, user_id))
        eventsub_websocket_manager.stop_connections_for_user(user_id)
        ws_connection = eventsub_websocket_manager.create_new_connection(twitch)
        ws_connection.add_subscription(
            type="channel.channel_points_custom_reward_redemption.add",
            version="1",
            condition={
                "broadcaster_user_id": user_id,
            },
        )
        ws_connection.start_thread()

    def get_twitch_oauth_redirect_uri() -> str:
        return flask.url_for(oauth_twitch.__name__, _external=True)

    def set_up() -> None:
        for user_id in authdb.get_all_user_ids_slow():
            start_eventsub_for_user(user_id)

    set_up()
    return app

if __name__ == "__main__":
    create_app()
