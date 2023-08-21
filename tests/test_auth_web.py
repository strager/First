import json
import time
import pytest
import responses
import first.web_server
import urllib.parse
import first.config
from first.accountdb import FirstAccountDb
from first.authdb import TwitchAuthDb, UserNotFoundError
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate
from .mock_config import set_admin_password
from .http_basic_auth import http_basic_auth_headers, base64_encode_str

twitch_config = first.config.cfg["twitch"]

@pytest.fixture
def web_app(account_db, authdb, websocket_manager):
    app = first.web_server.create_app_for_testing(account_db=account_db, authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True
    app = app.test_client()
    return app

@pytest.fixture
def authdb():
    authdb = TwitchAuthDb(":memory:")
    return authdb

@pytest.fixture
def account_db():
    return FirstAccountDb(":memory:")

@pytest.fixture
def websocket_manager():
    return TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate)

def test_log_in_post_redirects_to_twitch(web_app):
    res = web_app.post("/login")
    assert res.status_code == 303, "should redirect with a GET request"
    url = urllib.parse.urlparse(res.headers["location"])
    assert url._replace(fragment="", query="").geturl() == "https://id.twitch.tv/oauth2/authorize"
    parameters = urllib.parse.parse_qs(url.query)
    assert parameters["response_type"] == ["code"]
    assert parameters["client_id"] == [twitch_config["client_id"]]
    assert parameters["redirect_uri"] == ["http://localhost:5000/oauth/twitch"]
    scopes = parameters["scope"][-1].split(" ")
    assert "channel:read:redemptions" in scopes
    assert "channel:manage:redemptions" in scopes

def test_oauth_twitch_failure_redirect_mismatch(web_app):
    res = web_app.get("/oauth/twitch?error=redirect_mismatch&error_description=Parameter+redirect_uri+does+not+match+registered+URI")
    assert res.status_code == 500
    # TODO(strager): Instead, assert that a message was logged to the
    # logger.
    assert "Parameter redirect_uri does not match registered URI" in res.text
    assert "redirect_mismatch" in res.text


@responses.activate
def test_oauth_twitch_success(web_app, authdb):
    responses.post(
        "https://id.twitch.tv/oauth2/token",
        json={
            "access_token": "my_access_token",
            "refresh_token": "my_refresh_token",
            # TODO(strager): Do we need these?
            "expires_in": 1234,
            "scope": [],
            "token_type": "bearer",
        },
        match=[
            responses.matchers.urlencoded_params_matcher({
                "code": "myauthcode",
                "grant_type": "authorization_code",
                "client_id": twitch_config["client_id"],
                "client_secret": twitch_config["client_secret"],
                "redirect_uri": "http://localhost:5000/oauth/twitch",
            }),
        ],
    )

    responses.get(
        "https://api.twitch.tv/helix/users",
        json={
            "data": [
                {
                    "id": "12345",
                    "login": "twitchdev",
                    "display_name": "TwitchDev",
                    "email": "not-real@email.com",
                    "created_at": "2016-12-14T20:32:28Z",
                }
            ]
        },
    )
    res = web_app.get("/oauth/twitch?code=myauthcode&scope=channel%3Aread%3Aredemptions+channel%3Amanage%3Aredemptions")

    assert authdb.get_access_token(user_id="12345") == "my_access_token"
    assert authdb.get_refresh_token(user_id="12345") == "my_refresh_token"

    assert res.status_code in (302, 303), "should redirect"

@responses.activate
def test_oauth_twitch_success_does_not_start_eventsub_connection(web_app, authdb, websocket_manager):
    responses.post(
        "https://id.twitch.tv/oauth2/token",
        json={
            "access_token": "my_access_token",
            "refresh_token": "my_refresh_token",
            # TODO(strager): Do we need these?
            "expires_in": 1234,
            "scope": [],
            "token_type": "bearer",
        },
    )
    responses.get(
        "https://api.twitch.tv/helix/users",
        json={
            "data": [
                {
                    "id": "12345",
                    "login": "twitchdev",
                    "display_name": "TwitchDev",
                }
            ]
        },
    )

    web_app.get("/oauth/twitch?code=myauthcode&scope=channel%3Aread%3Aredemptions+channel%3Amanage%3Aredemptions")

    websocket_threads = websocket_manager.get_all_threads_for_testing()
    assert len(websocket_threads) == 0, "should not have started a thread after authenticating"

@responses.activate
def test_oauth_twitch_success_logs_in_with_first_account(web_app, authdb, account_db):
    responses.post(
        "https://id.twitch.tv/oauth2/token",
        json={
            "access_token": "my_access_token",
            "refresh_token": "my_refresh_token",
            # TODO(strager): Do we need these?
            "expires_in": 1234,
            "scope": [],
            "token_type": "bearer",
        },
    )
    responses.get(
        "https://api.twitch.tv/helix/users",
        json={
            "data": [
                {
                    "id": "12345",
                    "login": "twitchdev",
                    "display_name": "TwitchDev",
                }
            ]
        },
    )

    web_app.get("/oauth/twitch?code=myauthcode&scope=channel%3Aread%3Aredemptions+channel%3Amanage%3Aredemptions")

    # Ensure the account was created. get_account_id_by_twitch_user_id shouldn't
    # raise FirstAccountNotFoundError.
    account_id = account_db.get_account_id_by_twitch_user_id(
        twitch_user_id="12345",
    )
    assert account_id is not None
    # Ensure the user is now logged into the account via a cookie.
    whoami_response = web_app.get("/api/whoami")
    whoami_data = json.loads(whoami_response.text)
    assert whoami_data.get('account_id') == account_id

def test_admin_impersonate_changes_account_id(web_app, account_db, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="1234")
    assert account_id is not None

    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400

    whoami_response = web_app.get("/api/whoami")
    whoami_data = json.loads(whoami_response.text)
    assert whoami_data.get('account_id') == account_id

def test_log_out_should_disassociate_account_with_session(web_app, account_db, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="1234")
    assert account_id is not None
    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400

    _log_out_response = web_app.post("/logout")

    whoami_response = web_app.get("/api/whoami")
    whoami_data = json.loads(whoami_response.text)
    assert whoami_data.get('account_id') == None

def test_log_out_without_uri_should_redirect_to_home_page(web_app, account_db, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="1234")
    assert account_id is not None
    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400

    log_out_response = web_app.post("/logout")
    assert log_out_response.status_code == 303, "should redirect with a GET request"
    url = urllib.parse.urlparse(log_out_response.headers["location"])
    assert url.path == "/", "should direct to the home page"

def test_log_out_with_uri_should_redirect_to_specified_uri(web_app, account_db, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="1234")
    assert account_id is not None
    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400

    log_out_response = web_app.post("/logout?uri=/banana/icecream")
    assert log_out_response.status_code == 303, "should redirect with a GET request"
    url = urllib.parse.urlparse(log_out_response.headers["location"])
    assert url.path == "/banana/icecream", "should direct to the requested uri"

@responses.activate
@pytest.mark.slow
def test_oauth_twitch_for_already_started_user_closes_old_and_starts_new_eventsub_connection(web_app, authdb, websocket_manager, account_db, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="12345")
    account_db.set_account_reward_id(account_id, "reward-id")
    authdb.update_or_create_user(user_id="12345", access_token="old_access_token", refresh_token="old_refresh_token")
    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400
    # Start an EventSub connection.
    response = web_app.post("/manage.html", data={
        "reward": "1234"
    })
    assert 200 <= response.status_code < 400

    print("done impersonating; EventSub threads should be starting or started")

    responses.post(
        "https://id.twitch.tv/oauth2/token",
        json={
            "access_token": "old_access_token",
            "refresh_token": "old_refresh_token",
            # TODO(strager): Do we need these?
            "expires_in": 1234,
            "scope": [],
            "token_type": "bearer",
        },
    )
    responses.get(
        "https://api.twitch.tv/helix/users",
        json={
            "data": [
                {
                    "id": "12345",
                    "login": "twitchdev",
                    "display_name": "TwitchDev",
                }
            ]
        },
    )

    web_app.get("/oauth/twitch?code=myauthcode&scope=channel%3Aread%3Aredemptions+channel%3Amanage%3Aredemptions")

    responses.post(
        "https://id.twitch.tv/oauth2/token",
        json={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            # TODO(strager): Do we need these?
            "expires_in": 1234,
            "scope": [],
            "token_type": "bearer",
        },
    )

    # HACK[EventSub-async-start]: EventSub management is asynchronous. Wait for
    # it to finish.
    time.sleep(1)
    threads_before_login = websocket_manager.get_all_threads_for_testing()

    # Log in, forcing new OAuth tokens.
    web_app.get("/oauth/twitch?code=myauthcode&scope=channel%3Aread%3Aredemptions+channel%3Amanage%3Aredemptions")
    # HACK[EventSub-async-start]: EventSub management is asynchronous. Wait for
    # it to finish.
    time.sleep(1)

    threads_after_login = websocket_manager.get_all_threads_for_testing()
    assert len(threads_before_login) == 1
    assert len(threads_after_login) == 1
    assert not threads_before_login[0].running, "old thread should have stopped"
    assert threads_after_login[0].running, "new thread should be running"
