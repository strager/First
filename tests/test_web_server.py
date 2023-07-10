import pytest
import first.web_server
from first.authdb import AuthDb, UserNotFoundError
from first.twitch_eventsub import TwitchEventSubWebSocketManager, FakeTwitchEventSubWebSocketThread

@pytest.fixture
def authdb():
    authdb = AuthDb(":memory:")
    return authdb

@pytest.fixture
def websocket_manager():
    return TwitchEventSubWebSocketManager(FakeTwitchEventSubWebSocketThread)

def test_new_eventsub_connection_for_logged_in_users_on_start(authdb, websocket_manager):
    authdb.update_or_create_user(user_id="1", access_token="a1", refresh_token="r1")
    authdb.update_or_create_user(user_id="2", access_token="a2", refresh_token="r2")

    app = first.web_server.create_app_for_testing(authdb=authdb, eventsub_websocket_manager=websocket_manager)
    app.debug = True

    threads = websocket_manager.get_all_threads_for_testing()
    assert len(threads) == 2
    assert all(thread.running for thread in threads)
