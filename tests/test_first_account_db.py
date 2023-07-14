import pytest
from first.accountdb import FirstAccountDb, FirstAccountNotFoundError

def test_create_new_account():
    account_db = FirstAccountDb(":memory:")
    account_1_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    assert account_db.get_account_twitch_user_id(account_id=account_1_id) == "1234"
    account_2_id = account_db.create_or_get_account(
        twitch_user_id="5678",
    )
    assert account_db.get_account_twitch_user_id(account_id=account_1_id) == "1234"
    assert account_db.get_account_twitch_user_id(account_id=account_2_id) == "5678"

def test_create_account_with_existing_twitch_user_id_should_reuse_account():
    account_db = FirstAccountDb(":memory:")
    account_1_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    account_2_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    assert account_1_id == account_2_id

def test_getting_existing_account_by_twitch_user_id_succeeds():
    account_db = FirstAccountDb(":memory:")
    account_id = account_db.create_or_get_account(
        twitch_user_id="1234",
    )
    assert account_db.get_account_id_by_twitch_user_id(
        twitch_user_id="1234",
    ) == account_id

def test_getting_missing_account_by_twitch_user_id_fails():
    account_db = FirstAccountDb(":memory:")
    with pytest.raises(FirstAccountNotFoundError):
        account_db.get_account_id_by_twitch_user_id(
            twitch_user_id="1234",
        )

def test_get_twitch_user_for_non_existing_account():
    account_db = FirstAccountDb(":memory:")
    with pytest.raises(FirstAccountNotFoundError):
        account_db.get_account_twitch_user_id(account_id=420)
