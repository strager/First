from first.authdb import AuthDb, AuthDbUserTokenProvider
from first.twitch import AuthenticatedTwitch
from first.twitch_eventsub import TwitchEventSubWebSocketThread
import first.config
import time
import logging

logging.basicConfig(level=logging.INFO)

twitch_config = first.config.cfg["twitch"]

authdb = AuthDb()
authdb.update_or_create_user(
    # TODO(strager): Make these user-controlled in a nicer way than the config
    # file.
    user_id=twitch_config["channel_id"],
    access_token=twitch_config["token"],
    refresh_token=twitch_config["refresh_token"],
)

if __name__ == "__main__":
    token_provider = AuthDbUserTokenProvider(authdb, user_id=twitch_config["channel_id"])
    twitch = AuthenticatedTwitch(token_provider)
    websocket = TwitchEventSubWebSocketThread(twitch)
    try:
        websocket.add_subscription(
            type="channel.channel_points_custom_reward_redemption.add",
            version="1",
            condition={
                "broadcaster_user_id": twitch_config["channel_id"],
            },
        )
        websocket.start_thread()
        while True:
            time.sleep(1)
    finally:
        websocket.stop_thread()
