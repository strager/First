import pytest
import responses
import first.web_server
import urllib.parse
import first.config
from first.authdb import AuthDb, UserNotFoundError
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate

twitch_config = first.config.cfg["twitch"]

@pytest.fixture
def web_app(authdb, websocket_manager):
    app = first.web_server.create_app_for_testing(authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True
    app = app.test_client()
    return app

@pytest.fixture
def authdb():
    authdb = AuthDb(":memory:")
    return authdb

@pytest.fixture
def websocket_manager():
    return TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate)

def test_log_in_post_redirects_to_twitch(web_app):
    res = web_app.post("/login")
    assert res.status_code, 303 == "should redirect with a GET request"
    url = urllib.parse.urlparse(res.headers["location"])
    assert url._replace(fragment="", query="").geturl() == "https://id.twitch.tv/oauth2/authorize"
    parameters = urllib.parse.parse_qs(url.query)
    assert parameters["response_type"] == ["code"]
    assert parameters["client_id"] == [twitch_config["client_id"]]
    assert parameters["redirect_uri"] == ["http://localhost/oauth/twitch"]
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
                "redirect_uri": "http://localhost/oauth/twitch",
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
def test_oauth_twitch_success_starts_eventsub_connection(web_app, authdb, websocket_manager):
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
    assert len(websocket_threads) == 1, "should have started one thread after authenticating"
    assert websocket_threads[0].running

@responses.activate
def test_oauth_twitch_for_already_started_user_closes_old_and_starts_new_eventsub_connection(web_app, authdb, websocket_manager):
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

    threads_before_second_login = websocket_manager.get_all_threads_for_testing()

    # Log in a second time.
    web_app.get("/oauth/twitch?code=myauthcode&scope=channel%3Aread%3Aredemptions+channel%3Amanage%3Aredemptions")

    threads_after_second_login = websocket_manager.get_all_threads_for_testing()
    assert len(threads_before_second_login) == 1
    assert len(threads_after_second_login) == 1
    assert not threads_before_second_login[0].running, "old thread should have stopped"
    assert threads_after_second_login[0].running, "new thread should be running"
