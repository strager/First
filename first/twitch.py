import requests
from first.authdb import Token, UserId
import first.config

twitch_config = first.config.cfg["twitch"]

class Twitch:
    """Unauthenticated Twitch API access."""

    def get_authenticated_user_id(self, access_token: Token) -> UserId:
        # TODO(strager): Error handling.
        response = requests.get("https://api.twitch.tv/helix/users", headers={
            "Authorization": f"Bearer {access_token}",
            "Client-Id": twitch_config["client_id"],
        }).json()
        return response["data"][0]["id"]
