from datetime import datetime, timezone
import time
import unittest
from first.authdb import AuthDb

TIMESTAMP_RESOLUTION = 1

class TestAuth(unittest.TestCase):

    def test_add_new_tokens(self):
        self.authdb = AuthDb()
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        self.assertEqual("funnytokenhere", self.authdb.get_access_token(user_id=5))

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


if __name__ == '__main__':
    unittest.main()
