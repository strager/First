import base64
import urllib.parse
import responses
import time
import pytest
import first.web_server
from first.accountdb import FirstAccountDb
from first.authdb import TwitchAuthDb, UserNotFoundError
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate
import first.config
from .mock_config import set_admin_password
from .http_basic_auth import http_basic_auth_headers, base64_encode_str

twitch_config = first.config.cfg["twitch"]

@pytest.fixture
def authdb():
    authdb = TwitchAuthDb(":memory:")
    return authdb

@pytest.fixture
def account_db():
    account_db = FirstAccountDb(":memory:")
    return account_db

@pytest.fixture
def websocket_manager():
    return TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate)

@pytest.fixture
def web_app(authdb, websocket_manager, account_db):
    app = first.web_server.create_app_for_testing(account_db=account_db, authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True
    return app.test_client()

def test_new_eventsub_connection_for_logged_in_users_with_reward_id_on_start(authdb, websocket_manager, account_db):
    authdb.update_or_create_user(user_id="1", access_token="a1", refresh_token="r1")
    account_1_id = account_db.create_or_get_account(twitch_user_id="1")
    account_db.set_account_reward_id(account_1_id, "111")

    authdb.update_or_create_user(user_id="2", access_token="a2", refresh_token="r2")
    account_2_id = account_db.create_or_get_account(twitch_user_id="2")
    account_db.set_account_reward_id(account_2_id, "222")

    # No reward ID for account_3_id.
    authdb.update_or_create_user(user_id="3", access_token="a3", refresh_token="r3")
    account_3_id = account_db.create_or_get_account(twitch_user_id="3")

    assert set(account_db.get_all_twitch_user_ids_with_any_reward_id()) == {"1", "2"}

    app = first.web_server.create_app_for_testing(account_db=account_db, authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True

    threads = websocket_manager.get_all_threads_for_testing()
    assert len(threads) == 2, "should have a thread for accounts 1 and 2 but not account 3"
    assert all(thread.running for thread in threads)

admin_endpoints = ["/admin", "/admin/eventsub"]

def test_admin_pages_require_authentication(web_app):
    for endpoint in admin_endpoints:
        response = web_app.get(endpoint)
        assert response.status_code == 401, "should be unauthorized"
        challenge = response.headers.get("www-authenticate", "")
        assert challenge.startswith("Basic ") or challenge == "Basic", f"challenge: {challenge!r}"
        assert 'realm="First! admin"' in challenge

def test_admin_pages_work_with_correct_password(web_app, set_admin_password):
    password = "hunter12"
    set_admin_password(password)
    for endpoint in admin_endpoints:
        # Username shouldn't matter to the server.
        for username in ["admin", "root", "", "asdf"]:
            response = web_app.get(endpoint, headers=http_basic_auth_headers(username, password))
            assert response.status_code == 200, "should be authorized"

def test_admin_pages_fail_with_incorrect_password(web_app, set_admin_password):
    correct_password = "hunter12"
    wrong_password = "HUNTER69"
    set_admin_password(correct_password)
    for endpoint in admin_endpoints:
        # Username shouldn't matter to the server.
        for username in ["admin", "root", "", "asdf"]:
            response = web_app.get(endpoint, headers=http_basic_auth_headers(username, wrong_password))
            assert response.status_code == 401, "should be unauthorized"

def test_admin_pages_fail_with_malformed_password_header(web_app, set_admin_password):
    invalid_utf8 = b'\xff invalid utf8 \xff'
    for www_authenticate_header in [
        "Basic not_base_64",
        "Complex",
        f"Basic {base64_encode_str('nopassword')}",
        f"Basic {base64.b64encode(invalid_utf8).decode()}",
    ]:
        response = web_app.get("/admin", headers={
            "Authorization": www_authenticate_header,
        })
        assert response.status_code == 401, "should be unauthorized"

@pytest.mark.slow
def test_setting_reward_id_starts_eventsub_connection(web_app, account_db, authdb, websocket_manager, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="123")
    account_db.set_account_reward_id(account_id, "reward-id")
    authdb.update_or_create_user(user_id="123", access_token="a", refresh_token="r")
    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400

    response = web_app.post("/manage.html", data={
        "reward": "1234"
    })
    assert 200 <= response.status_code < 400
    # HACK[EventSub-async-start]: EventSub management is asynchronous. Wait for
    # it to finish.
    time.sleep(1)

    websocket_threads = websocket_manager.get_all_threads_for_testing()
    assert len(websocket_threads) == 1, "should have started a thread"
    assert websocket_threads[0].running

@responses.activate
def test_creating_first_reward_sets_reward_id(web_app, account_db, authdb, websocket_manager, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="123")
    authdb.update_or_create_user(user_id="123", access_token="a", refresh_token="r")
    set_admin_password("hunter12")
    impersonate_response = web_app.post("/admin/impersonate", data={
        "account_id": str(account_id),
    }, headers=http_basic_auth_headers("admin", "hunter12"))
    assert 200 <= impersonate_response.status_code < 400

    responses.post(
        "https://api.twitch.tv/helix/channel_points/custom_rewards",
        json={
            "data": [
                {
                    "id": "new-reward-id",
                },
            ]
        },
        match=[
            responses.matchers.query_param_matcher({
                "broadcaster_id": "123",
            }),
            responses.matchers.json_params_matcher({
                "title": "first",
                "cost": 10,
                "is_enabled": True,
                "is_user_input_required": False,
                "is_max_per_stream_enabled": True,
                "max_per_stream": 1,
                "is_max_per_user_per_stream_enabled": True,
                "max_per_user_per_stream": 1,
                "should_redemptions_skip_request_queue": True,
            }),
        ],
    )

    response = web_app.post("/create-first-reward", data={
        "cost": 10,
    })

    assert response.status_code == 303, "should redirect with a GET request"
    url = urllib.parse.urlparse(response.headers["location"])
    assert url.path == "/manage.html", "should direct to the manage page"

    assert account_db.get_account_reward_id(account_id) == "new-reward-id"

@pytest.mark.slow
def test_unsetting_reward_id_stops_eventsub_connection(web_app, account_db, authdb, websocket_manager, set_admin_password):
    account_id = account_db.create_or_get_account(twitch_user_id="123")
    account_db.set_account_reward_id(account_id, "reward-id")
    authdb.update_or_create_user(user_id="123", access_token="a", refresh_token="r")
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

    # HACK[EventSub-async-start]: EventSub management is asynchronous. Wait for
    # it to finish.
    time.sleep(1)

    account_db.set_account_reward_id(account_id, None)

    # Stop the EventSub connection.
    response = web_app.post("/manage.html", data={
        "reward": ""
    })
    assert 200 <= response.status_code < 400

    # HACK[EventSub-async-start]: EventSub management is asynchronous. Wait for
    # it to finish.
    time.sleep(1)

    websocket_threads = websocket_manager.get_all_threads_for_testing()
    assert len(websocket_threads) == 0, "should have stopped the thread"
