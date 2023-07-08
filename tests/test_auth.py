from datetime import datetime, timezone
import time
import unittest
from first.authdb import AuthDb, UserNotFoundError
import first.web_server
import urllib.parse
import first.config

twitch_config = first.config.cfg["twitch"]

TIMESTAMP_RESOLUTION = 1

class TestAuthDb(unittest.TestCase):

    def test_add_new_tokens(self):
        self.authdb = AuthDb()
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        self.assertEqual("funnytokenhere", self.authdb.get_access_token(user_id=5))
        self.assertEqual("funnyrefreshtokenhere", self.authdb.get_refresh_token(user_id=5))

    def test_update_tokens(self):
        self.authdb = AuthDb()
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        self.authdb.update_tokens(user_id=5, new_access_token="newgarbage", new_refresh_token="newrefreshgarbage")
        self.assertEqual("newgarbage", self.authdb.get_access_token(user_id=5))
        self.assertEqual("newrefreshgarbage", self.authdb.get_refresh_token(user_id=5))

    def test_created_at_time_slow(self):
        self.authdb = AuthDb()
        before_add_user_time = datetime.now(timezone.utc)
        time.sleep(TIMESTAMP_RESOLUTION)
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        created_user_time = self.authdb.get_created_at_time(user_id=5)
        time.sleep(TIMESTAMP_RESOLUTION)
        after_created_user_time = datetime.now(timezone.utc)
        print(before_add_user_time)
        print(created_user_time)
        print(after_created_user_time)
        self.assertGreater(created_user_time, before_add_user_time)
        self.assertGreater(after_created_user_time, created_user_time)

    def test_updated_at_on_user_add_slow(self):
        self.authdb = AuthDb()
        before_add_user_time = datetime.now(timezone.utc)
        time.sleep(TIMESTAMP_RESOLUTION)
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        updated_user_time = self.authdb.get_updated_at_time(user_id=5)
        time.sleep(TIMESTAMP_RESOLUTION)
        after_updated_user_time = datetime.now(timezone.utc)
        print(before_add_user_time)
        print(updated_user_time)
        print(after_updated_user_time)
        self.assertGreater(updated_user_time, before_add_user_time)
        self.assertGreater(after_updated_user_time, updated_user_time)

    def test_updated_at_slow(self):
        self.authdb = AuthDb()
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        updated_before_update_user_time = self.authdb.get_updated_at_time(user_id=5)
        time.sleep(TIMESTAMP_RESOLUTION)
        self.authdb.update_tokens(user_id=5, new_access_token="newthing", new_refresh_token="newrefreshthing")
        time.sleep(TIMESTAMP_RESOLUTION)
        updated_user_time = self.authdb.get_updated_at_time(user_id=5)
        print(updated_before_update_user_time)
        print(updated_user_time)
        self.assertGreater(updated_user_time, updated_before_update_user_time)

    def test_get_access_token_user_doesnt_exist(self):
        self.authdb = AuthDb()
        with self.assertRaises(UserNotFoundError):
            self.authdb.get_access_token(user_id=42)

    def test_get_refresh_token_user_doesnt_exist(self):
        self.authdb = AuthDb()
        with self.assertRaises(UserNotFoundError):
            self.authdb.get_refresh_token(user_id=42)

    def test_update_tokens_user_doesnt_exist(self):
        self.authdb = AuthDb()
        with self.assertRaises(UserNotFoundError):
            self.authdb.update_tokens(user_id=42, new_access_token="doesntmatter", new_refresh_token="noneofyourbussiness")

    def test_add_already_exisisting_user(self):
        self.authdb = AuthDb()
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        self.authdb.add_new_user(
                user_id=5,
                access_token="thisshouldnbechanged",
                refresh_token="thisshouldnbechangedeither"
        )

class TestTwitchWebAuth(unittest.TestCase):
    def setUp(self):
        app = first.web_server.create_app()
        app.debug = True
        self.app = app.test_client()

    def test_log_in_post_redirects_to_twitch(self):
        res = self.app.post("/login")
        self.assertEqual(res.status_code, 303, "should redirect with a GET request")
        url = urllib.parse.urlparse(res.headers["location"])
        self.assertEqual(url._replace(fragment="", query="").geturl(), "https://id.twitch.tv/oauth2/authorize")
        parameters = urllib.parse.parse_qs(url.query)
        self.assertEqual(parameters["response_type"], ["code"])
        self.assertEqual(parameters["client_id"], [twitch_config["client_id"]])
        self.assertEqual(parameters["redirect_uri"], [twitch_config["redirect_uri"]])
        scopes = parameters["scope"][-1].split(" ")
        self.assertIn("channel:read:redemptions", scopes)
        self.assertIn("channel:manage:redemptions", scopes)

if __name__ == '__main__':
    unittest.main()
