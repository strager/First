import pytest
import threading
from first.usersdb import TwitchUsersDb
from first.config import cfg
from first.errors import UniqueUserAlreadyExists

users_config = cfg["usersdb"]


def test_insert_new_user():
    usersdb = TwitchUsersDb(":memory:")
    usersdb.insert_new_user(
            user_id="5",
            user_login="potato",
            user_name="Potato"
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")

def test_insert_existing_user():
    usersdb = TwitchUsersDb(":memory:")
    usersdb.insert_new_user(
            user_id="5",
            user_login="potato",
            user_name="Potato"
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")
    with pytest.raises(UniqueUserAlreadyExists):
        usersdb.insert_new_user(
                user_id="5",
                user_login="potato",
                user_name="Potato"
        )

def test_insert_existing_user_different_name():
    usersdb = TwitchUsersDb(":memory:")
    usersdb.insert_new_user(
            user_id="5",
            user_login="potato",
            user_name="Potato"
    )
    assert "potato" == usersdb.get_user_login_from_id(user_id="5")
    assert "Potato" == usersdb.get_user_name_from_id(user_id="5")
    with pytest.raises(UniqueUserAlreadyExists):
        usersdb.insert_new_user(
                user_id="5",
                user_login="tomato",
                user_name="Tomato"
        )
