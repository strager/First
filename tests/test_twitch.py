import pytest
import responses
from first.twitch import Twitch, AuthenticatedTwitch
import urllib.parse
import first.config
from first.authdb import AuthDb, Token

twitch_config = first.config.cfg["twitch"]

@responses.activate
def test_authenticated_request_uses_existing_token():
    responses.get(
        "https://api.twitch.tv/helix/users",
        json={ "data": [ { "display_name": "TwitchDev" } ] },
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer access_token"}),
        ],
    )

    class TestTokenProvider:
        def get_access_token(self) -> Token:
            return "access_token"

        def refresh_access_token(self) -> Token:
            raise AssertionError("token should not be refreshed")

    twitch = AuthenticatedTwitch(TestTokenProvider())
    display_name = twitch.get_user_display_name_by_user_id("12345")
    assert display_name == "TwitchDev", "API should have been called with Authorization header"

@responses.activate
def test_authenticated_request_refreshes_token_on_auth_failure():
    responses.get(
        "https://api.twitch.tv/helix/users",
        status=401,
        json={"error":"Unauthorized","status":401,"message":"Invalid OAuth token"},
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer initial_access_token"}),
        ],
    )
    responses.get(
        "https://api.twitch.tv/helix/users",
        json={ "data": [ { "display_name": "TwitchDev" } ] },
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer updated_access_token"}),
        ],
    )

    class TestTokenProvider:
        _access_token: Token = "initial_access_token"

        def get_access_token(self) -> Token:
            return self._access_token

        def refresh_access_token(self) -> Token:
            self._access_token = "updated_access_token"
            return self._access_token

    token_provider = TestTokenProvider()
    twitch = AuthenticatedTwitch(token_provider)
    display_name = twitch.get_user_display_name_by_user_id("12345")
    assert token_provider.get_access_token() == "updated_access_token", "token should have refreshed"
    assert display_name == "TwitchDev", "API should have been called with refreshed token"
