import base64
import pytest
import first.config
import first.web_server
from first.authdb import TwitchAuthDb, UserNotFoundError
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate

website_config = first.config.cfg["website"]

@pytest.fixture
def authdb():
    authdb = TwitchAuthDb(":memory:")
    return authdb

@pytest.fixture
def websocket_manager():
    return TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread, stub_twitch_eventsub_delegate)

@pytest.fixture
def web_app(authdb, websocket_manager):
    app = first.web_server.create_app_for_testing(authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True
    return app.test_client()

def test_new_eventsub_connection_for_logged_in_users_on_start(authdb, websocket_manager):
    authdb.update_or_create_user(user_id="1", access_token="a1", refresh_token="r1")
    authdb.update_or_create_user(user_id="2", access_token="a2", refresh_token="r2")

    app = first.web_server.create_app_for_testing(authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True

    threads = websocket_manager.get_all_threads_for_testing()
    assert len(threads) == 2
    assert all(thread.running for thread in threads)

admin_endpoints = ["/admin", "/admin/eventsub"]

def test_admin_pages_require_authentication(web_app):
    for endpoint in admin_endpoints:
        response = web_app.get(endpoint)
        assert response.status_code == 401, "should be unauthorized"
        challenge = response.headers.get("www-authenticate", "")
        assert challenge.startswith("Basic ") or challenge == "Basic", f"challenge: {challenge!r}"
        assert 'realm="First! admin"' in challenge

@pytest.fixture
def set_admin_password():
    def set(new_password: str) -> None:
        website_config["admin_password"] = new_password
    old_password = website_config["admin_password"]
    yield set
    website_config["admin_password"] = old_password

def test_admin_pages_work_with_correct_password(web_app, set_admin_password):
    password = "hunter12"
    set_admin_password(password)
    for endpoint in admin_endpoints:
        # Username shouldn't matter to the server.
        for username in ["admin", "root", "", "asdf"]:
            response = web_app.get(endpoint, headers={
                "Authorization": f"Basic {base64_encode_str(f'{username}:{password}')}",
            })
            assert response.status_code == 200, "should be authorized"

def test_admin_pages_fail_with_incorrect_password(web_app, set_admin_password):
    correct_password = "hunter12"
    wrong_password = "HUNTER69"
    set_admin_password(correct_password)
    for endpoint in admin_endpoints:
        # Username shouldn't matter to the server.
        for username in ["admin", "root", "", "asdf"]:
            response = web_app.get(endpoint, headers={
                "Authorization": f"Basic {base64_encode_str(f'{username}:{wrong_password}')}",
            })
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

def base64_encode_str(plaintext: str) -> str:
    return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
