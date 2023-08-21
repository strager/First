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
from first.users_cache import TwitchUserNameCache
from first.pointsdb import PointsDb
import datetime
import functools
import base64
from first.accountdb import FirstAccountDb, FirstAccountId
import multiprocessing.dummy

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

    def get_description(self) -> str: # type: ignore[override]
        return f"Error from Twitch: {self.error_description} (code: {self.error})"

class PointsDbTwitchEventSubDelegate(TwitchEventSubDelegate):
    _points_db: PointsDb
    _account_db: FirstAccountDb
    _authdb: TwitchAuthDb

    def __init__(self, points_db: PointsDb, account_db: FirstAccountDb, authdb: TwitchAuthDb) -> None:
        self._points_db = points_db
        self._account_db = account_db
        self._authdb = authdb

    def on_eventsub_notification(self,
                                 subscription_type: str,
                                 subscription_version: str,
                                 event_data: typing.Dict[str, typing.Any]) -> None:
        if subscription_type == "channel.channel_points_custom_reward_redemption.add":
            assert subscription_version == "1"
            # TODO(strager): reward_id<->level mapping should be configured
            # per-streamer.
            class LevelMap(typing.NamedTuple):
                level: int
                next_max_redemptions: int
                points: int
                next_title: str
            level_map = {
                "first": LevelMap(level=1, next_max_redemptions=2, points=5, next_title="second"),
                "second": LevelMap(level=2, next_max_redemptions=3, points=3, next_title="third"),
                "third": LevelMap(level=3, next_max_redemptions=1, points=1, next_title="first"),
            }
            broadcaster_id = event_data["broadcaster_user_id"]
            account_id = self._account_db.get_account_id_by_twitch_user_id(broadcaster_id)

            reward_id = self._account_db.get_account_reward_id(account_id)
            if reward_id == event_data["reward"]["id"]:
                reward_title = event_data["reward"]["title"]
                level = level_map[reward_title].level
                points = level_map[reward_title].points
                next_title = level_map[reward_title].next_title
                self._points_db.insert_new_redemption(
                    broadcaster_id=broadcaster_id,
                    redemption_id=event_data["id"],
                    user_id=event_data["user_id"],
                    # FIXME(strager): This should come from event_data["redeemed_at"] instead.
                    redeemed_at=datetime.datetime.now(),
                    points=points,
                    level=level,
                )
                twitch = AuthenticatedTwitch(TwitchAuthDbUserTokenProvider(self._authdb, broadcaster_id))
                twitch.update_channel_reward(broadcaster_id, reward_id, next_title, max_redemptions=level_map[reward_title].next_max_redemptions)

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
    twitch_users_cache: TwitchUserNameCache = TwitchUserNameCache(":memory:"),
) -> flask.Flask:
    if eventsub_websocket_manager is None:
        eventsub_websocket_manager = TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, eventsub_delegate)
    return create_app_from_dependencies(account_db=account_db, authdb=authdb, points_db=points_db, eventsub_websocket_manager=eventsub_websocket_manager, twitch_users_cache=twitch_users_cache)

def create_app() -> flask.Flask:
    """Create the Flask app for production. Named 'create_app' because that's
    the name that Flask looks for.
    """
    points_db = PointsDb()
    account_db = FirstAccountDb()
    authdb = TwitchAuthDb()
    eventsub_delegate = PointsDbTwitchEventSubDelegate(points_db=points_db, account_db=account_db, authdb=authdb)
    eventsub_websocket_manager = TwitchEventSubWebSocketManager(TwitchEventSubWebSocketThread, eventsub_delegate)
    return create_app_from_dependencies(
        account_db=account_db,
        authdb=authdb,
        points_db=points_db,
        eventsub_websocket_manager=eventsub_websocket_manager,
        twitch_users_cache=TwitchUserNameCache(),
    )

def create_app_from_dependencies(
    account_db: FirstAccountDb,
    authdb: TwitchAuthDb,
    points_db: PointsDb,
    eventsub_websocket_manager: TwitchEventSubWebSocketManager,
    twitch_users_cache: TwitchUserNameCache,
) -> flask.Flask:
    app = flask.Flask(__name__)
    app.secret_key = website_config["session_secret_key"]

    thread_pool = multiprocessing.dummy.Pool(processes=4)

    @app.context_processor
    def inject_template_globals():
        return {
            "account_db": account_db,
            "twitch_users_cache": twitch_users_cache,
        }

    @app.route("/")
    def home():
        return flask.render_template('index.html', firsts_per_streamer=points_db.get_streamers_lifetime_leaderboard(), id_to_display_name=twitch_users_cache.get_display_name_from_id)

    @app.get("/login")
    def log_in_view():
        return flask.render_template('login.html')

    @app.get("/stream/<broadcaster_id>")
    def stream_leaderboard(broadcaster_id: TwitchUserId):
        return flask.render_template(
            'stream-leaderboard.html',
            stream_name=twitch_users_cache.get_display_name_from_id(broadcaster_id),
            lifetime_points=points_db.get_lifetime_channel_points(broadcaster_id=broadcaster_id),
            monthly_points=points_db.get_monthly_channel_points(broadcaster_id=broadcaster_id),
            id_to_display_name=twitch_users_cache.get_display_name_from_id,
        )

    @app.get("/admin")
    @requires_admin_auth
    def admin_view():
        return flask.render_template(
            'admin/index.html',
            id_to_display_name=twitch_users_cache.get_display_name_from_id,
        )

    @app.get("/admin/eventsub")
    @requires_admin_auth
    def admin_eventsub():
        return flask.render_template(
            'admin/eventsub.html',
            eventsub_connections=eventsub_websocket_manager.get_all_threads_for_testing(),
            id_to_display_name=twitch_users_cache.get_display_name_from_id,
        )

    @app.get("/admin/accounts")
    @requires_admin_auth
    def admin_accounts():
        return flask.render_template(
            'admin/accounts.html',
            accounts=account_db.get_all_accounts_for_testing(),
            id_to_display_name=twitch_users_cache.get_display_name_from_id,
        )

    @app.get("/manage.html")
    def manage():
        account_id = flask.session.get('account_id', None)
        if account_id is None:
            return "", 404
        user_id = account_db.get_account_twitch_user_id(account_id)
        twitch = AuthenticatedTwitch(TwitchAuthDbUserTokenProvider(authdb, user_id))
        return flask.render_template(
            'manage.html',
            id_to_display_name=twitch_users_cache.get_display_name_from_id,
            rewards=twitch.get_all_channel_reward_ids(user_id),
        )

    @app.post("/manage.html")
    def manage_post():
        account_id = flask.session.get('account_id', None)
        if account_id is None:
            return "", 404
        reward_id = flask.request.form.get('reward', None)
        if reward_id is None:
            return "", 400
        if reward_id == "":
            reward_id = None
        # TODO(strager): Validate that reward_id is valid.
        account_db.set_account_reward_id(account_id=account_id, reward_id=reward_id)

        start_or_stop_eventsub_for_user_as_needed_async(user_id=account_db.get_account_twitch_user_id(account_id))
        return flask.redirect(flask.url_for(manage.__name__))

    @app.post("/create-first-reward")
    def create_first_reward():
        account_id = flask.session.get('account_id', None)
        if account_id is None:
            return "", 404
        form_cost = flask.request.form.get('cost', None)
        if form_cost is None:
            return "", 400
        cost = int(form_cost) # TODO(strager): Validate safely.

        twitch_user_id = account_db.get_account_twitch_user_id(account_id)
        twitch = AuthenticatedTwitch(TwitchAuthDbUserTokenProvider(authdb, twitch_user_id))
        reward_id = twitch.create_custom_channel_points_reward(
            broadcaster_id = twitch_user_id,
            title = "first",
            cost = cost,
            is_enabled = True,
            is_user_input_required = False,
            is_max_per_stream_enabled = True,
            max_per_stream = 1,
            is_max_per_user_per_stream_enabled = True,
            max_per_user_per_stream = 1,
            should_redemptions_skip_request_queue = True,
        )
        account_db.set_account_reward_id(account_id=account_id, reward_id=reward_id)

        start_or_stop_eventsub_for_user_as_needed_async(user_id=account_db.get_account_twitch_user_id(account_id))
        return flask.redirect(flask.url_for(manage.__name__), code=303)

    @app.post("/admin/impersonate")
    @requires_admin_auth
    def admin_impersonate():
        account_id_string: typing.Optional[str] = flask.request.form.get('account_id', None)
        account_id: typing.Optional[FirstAccountId] = None if account_id_string is None else int(account_id_string)
        flask.session['account_id'] = account_id

        return redirect_after_login()

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
            "redirect_uri": twitch_config["redirect_uri"],
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

        start_or_stop_eventsub_for_user_as_needed_async(user_id=user_id)

        return redirect_after_login()

    def redirect_after_login():
        return flask.redirect(flask.url_for(manage.__name__))

    @app.post("/login")
    def log_in():
        # TODO[twitch-oauth-state]: Set a state to avoid CSRF.
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

    def start_or_stop_eventsub_for_user_as_needed_async(user_id: TwitchUserId) -> None:
        thread_pool.apply_async(lambda: start_or_stop_eventsub_for_user_as_needed_sync(user_id))

    def start_or_stop_eventsub_for_user_as_needed_sync(user_id: TwitchUserId) -> None:
        should_be_running = account_db.get_account_reward_id(account_db.get_account_id_by_twitch_user_id(user_id)) is not None

        # TODO(robustness): We should stop the old connection only after the new
        # connection is subscribed.
        eventsub_websocket_manager.stop_connections_for_user(user_id)

        if should_be_running:
            twitch = AuthenticatedTwitch(TwitchAuthDbUserTokenProvider(authdb, user_id))
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

    def set_up() -> None:
        for user_id in account_db.get_all_twitch_user_ids_with_any_reward_id():
            start_or_stop_eventsub_for_user_as_needed_sync(user_id)

        import atexit
        atexit.register(lambda: thread_pool.terminate())

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
