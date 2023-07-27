import requests
import json
from urllib.parse import quote_plus
import first.config
import typing

if typing.TYPE_CHECKING:
    from first.authdb import Token, TokenProvider

TwitchUserId = str
RewardId = str

twitch_config = first.config.cfg["twitch"]

class Twitch:
    """Unauthenticated Twitch API access.

    This object is thread-safe.
    """

    def get_authenticated_user_id(self, access_token: "Token") -> "TwitchUserId":
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
        refresh_response = requests.post("https://id.twitch.tv/oauth2/token", data=refresh_data)
        # TODO(strager): Handle errors.
        refresh_result = refresh_response.json()
        return self.RefreshAuthTokenResult(
            new_access_token=refresh_result["access_token"],
            new_refresh_token=refresh_result["refresh_token"],
        )

    def get_authenticated_app_access_token(self) -> "Token":
        data = {
            "grant_type": "client_credentials",
            "client_id": twitch_config["client_id"],
            "client_secret": twitch_config["client_secret"],
        }
        response = requests.post("https://id.twitch.tv/oauth2/token", data=data).json()
        return response["access_token"]

class AuthenticatedTwitch:
    """Authenticated Twitch API access.

    Automatically refreshes access tokens if necessary.

    This object is as thread-safe as the given TokenProvider.
    """

    _auth_token_provider: "TokenProvider"

    def __init__(self, auth_token_provider: "TokenProvider") -> None:
        self._auth_token_provider = auth_token_provider

    def get_self_user_id_fast(self) -> "TwitchUserId":
        return self._auth_token_provider.user_id

    def get_user_display_name_by_user_id(self, user_id: "TwitchUserId") -> str:
        data = self._get_json(f"https://api.twitch.tv/helix/users?id={quote_plus(user_id)}")
        # TODO(strager): Robust error handling.
        return data["data"][0]["display_name"]

    def create_custom_channel_points_reward(
        self,
        broadcaster_id: TwitchUserId,
        title: str,
        cost: int,
        is_enabled: typing.Optional[bool] = None,
        is_user_input_required: typing.Optional[bool] = None,
        is_max_per_stream_enabled: typing.Optional[bool] = None,
        max_per_stream: typing.Optional[int] = None,
        is_max_per_user_per_stream_enabled: typing.Optional[bool] = None,
        max_per_user_per_stream: typing.Optional[int] = None,
        should_redemptions_skip_request_queue: typing.Optional[bool] = None,
    ) -> RewardId:
        request_body = {
            "title": title,
            "cost": cost,
        }
        if is_enabled is not None: request_body["is_enabled"] = is_enabled
        if is_user_input_required is not None: request_body["is_user_input_required"] = is_user_input_required
        if is_max_per_stream_enabled is not None: request_body["is_max_per_stream_enabled"] = is_max_per_stream_enabled
        if max_per_stream is not None: request_body["max_per_stream"] = max_per_stream
        if is_max_per_user_per_stream_enabled is not None: request_body["is_max_per_user_per_stream_enabled"] = is_max_per_user_per_stream_enabled
        if max_per_user_per_stream is not None: request_body["max_per_user_per_stream"] = max_per_user_per_stream
        if should_redemptions_skip_request_queue is not None: request_body["should_redemptions_skip_request_queue"] = should_redemptions_skip_request_queue
        data = self._post_json(f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={quote_plus(broadcaster_id)}", request_body)
        # TODO(strager): Robust error handling.
        return data["data"][0]["id"]

    def get_all_channel_reward_ids(self, broadcaster_id: "TwitchUserId") -> typing.List[typing.Tuple[RewardId, str]]:
        data = self._get_json(f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={quote_plus(broadcaster_id)}")
        print(data)
        if "error" in data:
            raise Exception(data["message"])
        result = [ (x["id"], x["title"]) for x in data["data"] ]
        return result

    def update_channel_reward(self, broadcaster_id: "TwitchUserId", reward_id: RewardId, new_title: str, max_redemptions: int):
        settings = {
            "title": new_title,
            "is_max_per_stream_enabled": True,
            "max_per_stream": max_redemptions,
            "is_max_per_user_per_stream_enabled": True,
            "max_per_user_per_stream": 1,
        }
        data = self._patch_json(f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={quote_plus(broadcaster_id)}&id={quote_plus(reward_id)}", body=settings)
        if "error" in data:
            raise Exception(data["message"])
        return

    def request_eventsub_subscription(self, request_body) -> None:
        response = self._post_json("https://api.twitch.tv/helix/eventsub/subscriptions", body=request_body)
        # TODO(strager): Robust error handling.
        print(response)

    def _get_json(self, uri: str):
        """Issue an HTTP GET request and return parsed JSON.

        See _request_json for details about authentication and refreshing.
        """
        return self._request_json("GET", uri)

    def _post_json(self, uri: str, body):
        """Issue an HTTP POST request and return parsed JSON.

        body must be convertible to JSON.

        See _request_json for details about authentication and refreshing.
        """
        return self._request_json("POST", uri, data=json.dumps(body), headers={
            'Content-Type': 'application/json',
        })

    def _patch_json(self, uri: str, body):
        """Issue an HTTP PATCH request and return parsed JSON.

        body must be convertible to JSON.

        See _request_json for details about authentication and refreshing.
        """
        return self._request_json("PATCH", uri, data=json.dumps(body), headers={
            'Content-Type': 'application/json',
        })

    def _request_json(self, *requests_args, **requests_kwargs):
        """Issue an HTTP request and return parsed JSON.

        The request includes authentication headers.

        This function refreshes the token and retries if an initial request
        fails with an authentication error.
        """
        extra_headers = requests_kwargs.pop("headers", {})
        def issue_request() -> requests.Response:
            headers = {
                "Authorization": f"Bearer {self._auth_token_provider.get_access_token()}",
                "Client-Id": twitch_config["client_id"],
            }
            headers.update(extra_headers)
            return requests.request(*requests_args, **requests_kwargs, headers=headers)
        response = issue_request()
        if response.status_code == 401:
            self._auth_token_provider.refresh_access_token()
            response = issue_request()
        # TODO(strager): Check status code.
        return response.json()
