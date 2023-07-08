from datetime import datetime, timezone
import time
import pytest
from first.authdb import AuthDb, UserNotFoundError
import urllib.parse
import first.config

twitch_config = first.config.cfg["twitch"]

TIMESTAMP_RESOLUTION = 1


def test_add_new_tokens():
    authdb = AuthDb()
    authdb.add_new_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    assert "funnytokenhere" == authdb.get_access_token(user_id=5)
    assert "funnyrefreshtokenhere" == authdb.get_refresh_token(user_id=5)

def test_update_tokens():
    authdb = AuthDb()
    authdb.add_new_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    authdb.update_tokens(user_id=5, new_access_token="newgarbage", new_refresh_token="newrefreshgarbage")
    assert "newgarbage" == authdb.get_access_token(user_id=5)
    assert "newrefreshgarbage" == authdb.get_refresh_token(user_id=5)

def test_created_at_time_slow():
    authdb = AuthDb()
    before_add_user_time = datetime.now(timezone.utc)
    time.sleep(TIMESTAMP_RESOLUTION)
    authdb.add_new_user(
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

def test_updated_at_on_user_add_slow():
    authdb = AuthDb()
    before_add_user_time = datetime.now(timezone.utc)
    time.sleep(TIMESTAMP_RESOLUTION)
    authdb.add_new_user(
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

def test_updated_at_slow():
    authdb = AuthDb()
    authdb.add_new_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    updated_before_update_user_time = authdb.get_updated_at_time(user_id=5)
    time.sleep(TIMESTAMP_RESOLUTION)
    authdb.update_tokens(user_id=5, new_access_token="newthing", new_refresh_token="newrefreshthing")
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

def test_update_tokens_user_doesnt_exist():
    authdb = AuthDb()
    with pytest.raises(UserNotFoundError):
        authdb.update_tokens(user_id=42, new_access_token="doesntmatter", new_refresh_token="noneofyourbussiness")

def test_add_already_exisisting_user():
    authdb = AuthDb()
    authdb.add_new_user(
            user_id=5,
            access_token="funnytokenhere",
            refresh_token="funnyrefreshtokenhere"
    )
    authdb.add_new_user(
            user_id=5,
            access_token="thisshouldnbechanged",
            refresh_token="thisshouldnbechangedeither"
    )
