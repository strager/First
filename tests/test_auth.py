from datetime import datetime, timezone
import responses
import threading
import time
import pytest
from first.authdb import AuthDb, UserNotFoundError, AuthDbUserTokenProvider
import urllib.parse
import first.config

twitch_config = first.config.cfg["twitch"]

TIMESTAMP_RESOLUTION = 1


def test_add_new_tokens():
    authdb = AuthDb()
    authdb.update_or_create_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    assert "funnytokenhere" == authdb.get_access_token(user_id=5)
    assert "funnyrefreshtokenhere" == authdb.get_refresh_token(user_id=5)

def test_update_tokens():
    authdb = AuthDb()
    authdb.update_or_create_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    authdb.update_or_create_user(user_id=5, access_token="newgarbage", refresh_token="newrefreshgarbage")
    assert "newgarbage" == authdb.get_access_token(user_id=5)
    assert "newrefreshgarbage" == authdb.get_refresh_token(user_id=5)

@pytest.mark.slow
def test_created_at_time_slow():
    authdb = AuthDb()
    before_add_user_time = datetime.now(timezone.utc)
    time.sleep(TIMESTAMP_RESOLUTION)
    authdb.update_or_create_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    created_user_time = authdb.get_created_at_time(user_id=5)
    time.sleep(TIMESTAMP_RESOLUTION)
    after_created_user_time = datetime.now(timezone.utc)
    print(before_add_user_time)
    print(created_user_time)
    print(after_created_user_time)
    assert created_user_time > before_add_user_time
    assert after_created_user_time > created_user_time

@pytest.mark.slow
def test_updated_at_on_user_add_slow():
    authdb = AuthDb()
    before_add_user_time = datetime.now(timezone.utc)
    time.sleep(TIMESTAMP_RESOLUTION)
    authdb.update_or_create_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    updated_user_time = authdb.get_updated_at_time(user_id=5)
    time.sleep(TIMESTAMP_RESOLUTION)
    after_updated_user_time = datetime.now(timezone.utc)
    print(before_add_user_time)
    print(updated_user_time)
    print(after_updated_user_time)
    assert updated_user_time > before_add_user_time
    assert after_updated_user_time > updated_user_time

@pytest.mark.slow
def test_updated_at_slow():
    authdb = AuthDb()
    authdb.update_or_create_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    updated_before_update_user_time = authdb.get_updated_at_time(user_id=5)
    time.sleep(TIMESTAMP_RESOLUTION)
    authdb.update_or_create_user(user_id=5, access_token="newthing", refresh_token="newrefreshthing")
    time.sleep(TIMESTAMP_RESOLUTION)
    updated_user_time = authdb.get_updated_at_time(user_id=5)
    print(updated_before_update_user_time)
    print(updated_user_time)
    assert updated_user_time > updated_before_update_user_time

def test_get_access_token_user_doesnt_exist():
    authdb = AuthDb()
    with pytest.raises(UserNotFoundError):
        authdb.get_access_token(user_id=42)

def test_get_refresh_token_user_doesnt_exist():
    authdb = AuthDb()
    with pytest.raises(UserNotFoundError):
        authdb.get_refresh_token(user_id=42)

def test_add_already_exisisting_user():
    authdb = AuthDb()
    authdb.update_or_create_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    authdb.update_or_create_user(
            user_id=5,
            access_token="thisshouldbetheupdatedtoken",
            refresh_token="thisshouldbechangedalso"
    )
    assert authdb.get_access_token(user_id=5) == "thisshouldbetheupdatedtoken"
    assert authdb.get_refresh_token(user_id=5) == "thisshouldbechangedalso"

def test_read_and_write_from_multiple_threads():
    authdb = AuthDb()

    loaded_access_token = None
    loaded_refresh_token = None

    def thread_1() -> None:
        authdb.update_or_create_user(
                user_id=5,
                access_token="thread_1_access_token",
                refresh_token="thread_1_refresh_token"
        )
    def thread_2() -> None:
        authdb.update_or_create_user(
                user_id=5,
                access_token="thread_2_access_token",
                refresh_token="thread_2_refresh_token"
        )
    def thread_3() -> None:
        nonlocal loaded_access_token
        try:
            loaded_access_token = authdb.get_access_token(user_id=5)
        except UserNotFoundError:
            loaded_access_token = "(not found)"
    def thread_4() -> None:
        nonlocal loaded_refresh_token
        try:
            loaded_refresh_token = authdb.get_refresh_token(user_id=5)
        except UserNotFoundError:
            loaded_refresh_token = "(not found)"

    threads = [threading.Thread(target=f) for f in [thread_1, thread_2, thread_3, thread_4]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert loaded_access_token in ("(not found)", "thread_1_access_token", "thread_2_access_token")
    assert loaded_refresh_token in ("(not found)", "thread_1_refresh_token", "thread_2_refresh_token")

def test_token_provider_gives_token_from_database():
    authdb = AuthDb()
    authdb.update_or_create_user(
            user_id=5,
            access_token="my_access_token",
            refresh_token="my_refresh_token"
    )
    token_provider = AuthDbUserTokenProvider(authdb, user_id=5)
    assert token_provider.get_access_token() == "my_access_token"

@responses.activate
def test_token_provider_refresh_gets_new_access_and_access_tokens_from_twitch_api():
    responses.post(
        "https://id.twitch.tv/oauth2/token",
        match=[
            responses.matchers.urlencoded_params_matcher({
                "grant_type": "refresh_token",
                "client_id": twitch_config["client_id"],
                "client_secret": twitch_config["client_secret"],
                "refresh_token": "original_refresh_token",
            }),
        ],
        json={
            'access_token': 'new_access_token',
            'expires_in': 15578,
            'refresh_token': 'new_refresh_token',
            'scope': ['channel:manage:redemptions', 'channel:read:redemptions', 'chat:edit'],
            'token_type': 'bearer',
        },
    )

    authdb = AuthDb()
    authdb.update_or_create_user(
            user_id=5,
            access_token="original_access_token",
            refresh_token="original_refresh_token"
    )
    token_provider = AuthDbUserTokenProvider(authdb, user_id=5)

    assert token_provider.refresh_access_token() == "new_access_token"
    assert token_provider.get_access_token() == "new_access_token"

    assert authdb.get_access_token(user_id=5) == "new_access_token"
    assert authdb.get_refresh_token(user_id=5) == "new_refresh_token"
