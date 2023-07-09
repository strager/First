import time

import traceback
import websocket
import requests
import _thread
import rel
import json
import first.config
from first.twitch import AuthenticatedTwitch
from first.authdb import AuthDb, AuthDbUserTokenProvider

twitch_config = first.config.cfg["twitch"]

authdb = AuthDb()
authdb.update_or_create_user(
    # TODO(strager): Make these user-controlled in a nicer way than the config
    # file.
    user_id=twitch_config["channel_id"],
    access_token=twitch_config["token"],
    refresh_token=twitch_config["refresh_token"],
)

def on_message(ws, message):
    msg = json.loads(message)
    print(msg)
    channel_id = twitch_config["channel_id"]
    if msg["metadata"]["message_type"] == "session_welcome":
        token_provider = AuthDbUserTokenProvider(authdb, user_id=twitch_config["channel_id"])
        twitch = AuthenticatedTwitch(token_provider)
        session_id = msg['payload']['session']['id']
        data = {
            "type": "channel.channel_points_custom_reward_redemption.add",
            "version": "1",
            "condition": {
                "broadcaster_user_id": channel_id,
            },
            "transport": {
                "method": "websocket",
                "session_id": session_id
            }
        }
        twitch.request_eventsub_subscription(data)

def on_error(ws, error):
    traceback.print_exception(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("Opened connection")

if __name__ == "__main__":
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp("wss://eventsub.wss.twitch.tv/ws",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=rel, reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
