import time

import traceback
import websocket
import requests
import _thread
import rel
import json
import config

twitch_config = config.cfg["twitch"]


def request_subscription(data):
    client_id = twitch_config["client_id"]
    headers = {
        "Authorization": f"Bearer {twitch_config['token']}",
        "Client-Id": client_id,
        "Content-Type": "application/json",
    }
    result = requests.post("https://api.twitch.tv/helix/eventsub/subscriptions", data=json.dumps(data), headers=headers)
    return result

def on_message(ws, message):
    msg = json.loads(message)
    print(msg)
    channel_id = twitch_config["channel_id"]
    client_id = twitch_config["client_id"]
    client_secret = twitch_config["client_secret"]
    if msg["metadata"]["message_type"] == "session_welcome":
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
        result = request_subscription(data)
        if result.status_code == 401:
            refresh_data = {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": twitch_config["refresh_token"],
            }
            refresh_result = requests.post("https://id.twitch.tv/oauth2/token", data=refresh_data)
            print(refresh_result.status_code)
            refresh_result = refresh_result.json()
            twitch_config["token"] = refresh_result["access_token"]
            twitch_config["refresh_token"] = refresh_result["refresh_token"]
            result = request_subscription(data)
        print(result, result.text)

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
