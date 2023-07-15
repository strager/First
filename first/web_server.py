import flask
import secrets
import binascii
from uuid import uuid4
from first.twitch import Twitch, AuthenticatedTwitch, TwitchUserId
from urllib.parse import quote_plus
from first.authdb import TwitchAuthDb, TwitchAuthDbUserTokenProvider
import first.config
from werkzeug.exceptions import HTTPException
import logging
import requests
import typing
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread, TwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate, TwitchEventSubDelegate
from first.pointsdb import PointsDb
import datetime
import functools
import base64
from first.accountdb import FirstAccountDb, FirstAccountId

# TODO(strager): Fancier logging.
logging.basicConfig(level=logging.INFO)

twitch_config = first.config.cfg["twitch"]
website_config = first.config.cfg["website"]

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

class PointsDbTwitchEventSubDelegate(TwitchEventSubDelegate):
    _points_db: PointsDb

    def __init__(self, points_db: PointsDb) -> None:
        self._points_db = points_db

    def on_eventsub_notification(self,
                                 subscription_type: str,
                                 subscription_version: str,
                                 event_data: typing.Dict[str, typing.Any]) -> None:
        if subscription_type == "channel.channel_points_custom_reward_redemption.add":
            assert subscription_version == "1"
            # TODO(strager): reward_id<->level mapping should be configured
            # per-streamer.
            level = 1
            points = 5
            self._points_db.insert_new_redemption(
                broadcaster_id=event_data["broadcaster_user_id"],
                redemption_id=event_data["id"],
                user_id=event_data["user_id"],
                # FIXME(strager): This should come from event_data["redeemed_at"] instead.
                redeemed_at=datetime.datetime.now(),
                points=points,
                level=level,
            )
        elif subscription_type == "channel.channel_points_custom_reward_redemption.update":
            # TODO(#13): Handle rejected redemptions.
            pass
        else:
            # Ignore.
            pass

def create_app_for_testing(
    account_db: FirstAccountDb = FirstAccountDb(":memory:"),
    authdb: TwitchAuthDb = TwitchAuthDb(":memory:"),
    points_db: PointsDb = PointsDb(":memory:"),
    eventsub_websocket_manager: typing.Optional[TwitchEventSubWebSocketManager] = None,
    # Used only if eventsub_websocket_manager is None.
    eventsub_delegate: TwitchEventSubDelegate = stub_twitch_eventsub_delegate,
) -> flask.Flask:
    if eventsub_websocket_manager is None:
        eventsub_websocket_manager = TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, eventsub_delegate)
    return create_app_from_dependencies(account_db=account_db, authdb=authdb, points_db=points_db, eventsub_websocket_manager=eventsub_websocket_manager)

def create_app() -> flask.Flask:
    """Create the Flask app for production. Named 'create_app' because that's
    the name that Flask looks for.
    """
    points_db = PointsDb()
    eventsub_delegate = PointsDbTwitchEventSubDelegate(points_db=points_db)
    eventsub_websocket_manager = TwitchEventSubWebSocketManager(TwitchEventSubWebSocketThread, eventsub_delegate)
    return create_app_from_dependencies(
        account_db=FirstAccountDb(),
        authdb=TwitchAuthDb(),
        points_db=points_db,
        eventsub_websocket_manager=eventsub_websocket_manager
    )

def create_app_from_dependencies(
    account_db: FirstAccountDb,
    authdb: TwitchAuthDb,
    points_db: PointsDb,
    eventsub_websocket_manager: TwitchEventSubWebSocketManager,
) -> flask.Flask:
    app = flask.Flask(__name__)
    app.secret_key = website_config["session_secret_key"]

    @app.context_processor
    def inject_template_globals():
        return {
            "account_db": account_db,
        }

    @app.route("/")
    def home():
        return flask.render_template('index.html')

    @app.get("/login")
    def log_in_view():
        return flask.render_template('login.html')

    @app.get("/stream/<broadcaster_id>")
    def stream_leaderboard(broadcaster_id: TwitchUserId):
        return flask.render_template(
            'stream-leaderboard.html',
            stream_name="TODO", # TODO(strager)
            lifetime_points=points_db.get_lifetime_channel_points(broadcaster_id=broadcaster_id),
            monthly_points=points_db.get_monthly_channel_points(broadcaster_id=broadcaster_id),
        )

    @app.get("/admin")
    @requires_admin_auth
    def admin_view():
        return flask.render_template('admin/index.html')

    @app.get("/admin/eventsub")
    @requires_admin_auth
    def admin_eventsub():
        return flask.render_template('admin/eventsub.html', eventsub_connections=eventsub_websocket_manager.get_all_threads_for_testing())

    @app.get("/admin/accounts")
    @requires_admin_auth
    def admin_accounts():
        return flask.render_template('admin/accounts.html', accounts=account_db.get_all_accounts_for_testing())

    @app.post("/admin/impersonate")
    @requires_admin_auth
    def admin_impersonate():
        account_id_string: typing.Optional[str] = flask.request.form.get('account_id', None)
        account_id: typing.Optional[FirstAccountId] = None if account_id_string is None else int(account_id_string)
        flask.session['account_id'] = account_id

        # TODO(strager): Redirect to the same place as if the user logged in.
        return flask.redirect("/")

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

        account_id = account_db.create_or_get_account(twitch_user_id=user_id)
        flask.session['account_id'] = account_id

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

    @app.post("/logout")
    def log_out():
        flask.session['account_id'] = None

        uri = flask.request.args.get('uri', None)
        if uri is None:
            uri = flask.url_for(home.__name__)
        return flask.redirect(uri, code=303)

    @app.errorhandler(UnexpectedTwitchOAuthError)
    def unexpected_twitch_oauth_error(error):
        # TODO(security): HTML-escape.
        logger.error(error)
        return error.description, 500

    def start_eventsub_for_user(user_id: TwitchUserId) -> None:
        twitch = AuthenticatedTwitch(TwitchAuthDbUserTokenProvider(authdb, user_id))
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

    @app.route("/api/whoami")
    def api_whoami():
        return {
            "account_id": flask.session.get('account_id', None),
        }

    def get_twitch_oauth_redirect_uri() -> str:
        return flask.url_for(oauth_twitch.__name__, _external=True)

    def set_up() -> None:
        for user_id in authdb.get_all_user_ids_slow():
            start_eventsub_for_user(user_id)

    set_up()
    return app

def requires_admin_auth(endpoint_func):
    def is_authenticated(authorization_header: str) -> bool:
        if authorization_header is None:
            return False
        if not authorization_header.startswith("Basic "):
            return False
        credentials = authorization_header[len("Basic "):]
        try:
            user_pass = base64.b64decode(credentials.encode()).decode()
        except (binascii.Error, UnicodeDecodeError):
            return False
        if ":" not in user_pass:
            return False
        [_username, password] = user_pass.split(":", 2)
        return secrets.compare_digest(password, website_config["admin_password"])
    @functools.wraps(endpoint_func)
    def wrapper(*args, **kwargs):
        if not is_authenticated(flask.request.headers.get("Authorization", "")):
            return flask.Response(response="login required", status=401, headers={
                "WWW-Authenticate": 'Basic realm="First! admin"',
            })
        logging.info("admin-authenticated request from IP address %s", flask.request.remote_addr)
        return endpoint_func(*args, **kwargs)
    return wrapper

if __name__ == "__main__":
    create_app()
