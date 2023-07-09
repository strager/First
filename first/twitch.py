import requests
from urllib.parse import quote_plus
import first.config
import typing

if typing.TYPE_CHECKING:
    from first.authdb import Token, UserId, TokenProvider

twitch_config = first.config.cfg["twitch"]

class Twitch:
    """Unauthenticated Twitch API access."""

    def get_authenticated_user_id(self, access_token: "Token") -> "UserId":
        # TODO(strager): Error handling.
        response = requests.get("https://api.twitch.tv/helix/users", headers={
            "Authorization": f"Bearer {access_token}",
            "Client-Id": twitch_config["client_id"],
        }).json()
        return response["data"][0]["id"]

    class RefreshAuthTokenResult(typing.NamedTuple):
        new_access_token: "Token"
        new_refresh_token: "Token"

    def refresh_auth_token(self, refresh_token: "Token") -> RefreshAuthTokenResult:
        refresh_data = {
            "grant_type": "refresh_token",
            "client_id": twitch_config["client_id"],
            "client_secret": twitch_config["client_secret"],
            "refresh_token": refresh_token,
        }
        refresh_result = requests.post("https://id.twitch.tv/oauth2/token", data=refresh_data)
        # TODO(strager): Handle errors.
        refresh_result = refresh_result.json()
        return self.RefreshAuthTokenResult(
            new_access_token=refresh_result["access_token"],
            new_refresh_token=refresh_result["refresh_token"],
        )

class AuthenticatedTwitch:
    """Authenticated Twitch API access.

    Automatically refreshes access tokens if necessary.
    """

    _auth_token_provider: "TokenProvider"

    def __init__(self, auth_token_provider: "TokenProvider") -> None:
        self._auth_token_provider = auth_token_provider

    def get_user_display_name_by_user_id(self, user_id: "UserId") -> str:
        def issue_request() -> None:
            return requests.get(f"https://api.twitch.tv/helix/users?id={quote_plus(user_id)}", headers={
                "Authorization": f"Bearer {self._auth_token_provider.get_access_token()}",
                "Client-Id": twitch_config["client_id"],
            })
        response = issue_request()
        if response.status_code == 401:
            self._auth_token_provider.refresh_access_token()
            response = issue_request()
        # TODO(strager): Robust error handling.
        return response.json()["data"][0]["display_name"]
