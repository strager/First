from first.authdb import Token, TokenProvider
from first.pointsdb import PointsDb
from first.twitch import AuthenticatedTwitch
from first.twitch_eventsub import TwitchEventSubWebSocketThread, TwitchEventSubDelegate
from first.web_server import PointsDbTwitchEventSubDelegate
from first.accountdb import FirstAccountDb
from first.authdb import TwitchAuthDb
import contextlib
import copy
import json
import pytest
import threading
import typing
import websockets.sync.server

@pytest.fixture
def exit_stack():
    with contextlib.ExitStack() as exit_stack:
        yield exit_stack

@pytest.mark.slow  # FIXME(strager): Teardown is slow for some reason.
def test_eventsub_thread_calls_delegate_on_receiving_channel_point_redemption(exit_stack):
    # Create a server which sends an EventSub notification to the client.
    def handle_server_connection(connection: websockets.sync.server.ServerConnection) -> None:
        # Message received from production Twitch:
        # TODO(strager): Pick a better message. In this one, the streamer
        # redeemed points in his own stream, which is confusing.
        connection.send(json.dumps({
          "metadata": {
            "message_id": "VVGVVUcY-T03itpOG3qhIlUTbd8hpVPLqlnet5OYaxo=",
            "message_type": "notification",
            "message_timestamp": "2023-07-13T11:49:36.545175204Z",
            "subscription_type": "channel.channel_points_custom_reward_redemption.add",
            "subscription_version": "1"
          },
          "payload": {
            "subscription": {
              "id": "3084e6d6-7bb0-47e3-a289-4a6c58d7c30c",
              "status": "enabled",
              "type": "channel.channel_points_custom_reward_redemption.add",
              "version": "1",
              "condition": {
                "broadcaster_user_id": "21065580",
                "reward_id": ""
              },
              "transport": {
                "method": "websocket",
                "session_id": "AgoQZAzmSi9VSoK9aYhEqjGdFBIGY2VsbC1h"
              },
              "created_at": "2023-07-13T11:49:34.794259056Z",
              "cost": 0
            },
            "event": {
              "broadcaster_user_id": "21065580",
              "broadcaster_user_login": "strager",
              "broadcaster_user_name": "strager",
              "id": "addae886-719e-4427-8f19-8152a260a806",
              "user_id": "21065580",
              "user_login": "strager",
              "user_name": "strager",
              "user_input": "",
              "status": "fulfilled",
              "redeemed_at": "2023-07-13T11:49:36.525368238Z",
              "reward": {
                "id": "b34cd9ba-40de-4953-80f8-57362376f8e0",
                "title": "tres comas",
                "prompt": ", , ,",
                "cost": 1000000000
              }
            }
          }
        }))
        # Ignore messages sent by the client.

    server = exit_stack.enter_context(websockets.sync.server.serve(handle_server_connection, host="localhost", port=0))
    server_thread = threading.Thread(target=server.serve_forever)
    exit_stack.callback(lambda: server_thread.join())
    exit_stack.callback(lambda: server.shutdown())
    server_thread.start()
    (server_host, server_port) = server.socket.getsockname()

    # Create a client which remembers its first received EventSub notification.
    received_notification_cond = threading.Condition()
    received_subscription_type: typing.Optional[str] = None
    received_event_data: typing.Optional[typing.Dict[str, typing.Any]] = None
    class TestClientDelegate(TwitchEventSubDelegate):
        def on_eventsub_notification(self,
                                     subscription_type: str,
                                     subscription_version: str,
                                     event_data: typing.Dict[str, typing.Any]) -> None:
            with received_notification_cond:
                nonlocal received_subscription_type
                received_subscription_type = subscription_type
                nonlocal received_event_data
                received_event_data = copy.deepcopy(event_data)
                received_notification_cond.notify_all()
    client_delegate = TestClientDelegate()
    twitch = AuthenticatedTwitch(FailingTokenProvider())
    client_thread = TwitchEventSubWebSocketThread(twitch, client_delegate, websocket_uri=f"ws://{server_host}:{server_port}/")
    client_thread.add_subscription(
        type="channel.channel_points_custom_reward_redemption.add",
        version="1",
        condition={
            "broadcaster_user_id": "21065580",
        },
    )
    exit_stack.callback(lambda: client_thread.stop_thread())
    client_thread.start_thread()

    # Wait for the server to send a notification to the client.
    with received_notification_cond:
        ok = received_notification_cond.wait_for(lambda: received_subscription_type is not None and received_event_data is not None, timeout=3)
        assert ok, "timed out waiting for client to receive message from server"

        assert received_subscription_type == "channel.channel_points_custom_reward_redemption.add"
        assert received_event_data.get("broadcaster_user_id") == "21065580"
        assert received_event_data.get("broadcaster_user_login") == "strager"
        assert received_event_data.get("broadcaster_user_name") == "strager"
        assert received_event_data.get("user_id") == "21065580"
        assert received_event_data.get("user_login") == "strager"
        assert received_event_data.get("user_name") == "strager"
        assert received_event_data.get("status") == "fulfilled"
        assert received_event_data.get("reward", {}).get("id") == "b34cd9ba-40de-4953-80f8-57362376f8e0"
        assert received_event_data.get("redeemed_at") == "2023-07-13T11:49:36.525368238Z"

@pytest.mark.skip(reason="time")
def test_eventsub_delegate_stores_data_in_pointsdb():
    points_db = PointsDb(":memory:")
    account_db = FirstAccountDb(":memory:")
    authdb = TwitchAuthDb(":memory:")
    account_db.create_or_get_account(twitch_user_id="123")
    account_db.set_account_reward_id("1", "b34cd9ba-40de-4953-80f8-57362376f8e0")
    delegate = PointsDbTwitchEventSubDelegate(points_db, account_db, authdb)
    delegate.on_eventsub_notification(
        subscription_type="channel.channel_points_custom_reward_redemption.add",
        subscription_version="1",
        event_data={
            "broadcaster_user_id": "123",
            "broadcaster_user_login": "strimmer",
            "broadcaster_user_name": "strimmer",
            "id": "addae886-719e-4427-8f19-8152a260a806",
            "user_id": "456",
            "user_login": "chatter",
            "user_name": "chatter",
            "user_input": "",
            "status": "fulfilled",
            "redeemed_at": "2023-07-13T11:49:36.525368238Z",
            "reward": {
                "id": "b34cd9ba-40de-4953-80f8-57362376f8e0",
                "title": "first",
                "prompt": "Be first in chat!",
                "cost": 1,
            },
        },
    )
    leaderboard = points_db.get_lifetime_channel_points(broadcaster_id="123")
    assert leaderboard == [("456", 5)]

class FailingTokenProvider(TokenProvider):
    def get_access_token(self) -> Token:
        raise AssertionError("should not be called")

    def refresh_access_token(self) -> Token:
        raise AssertionError("should not be called")
