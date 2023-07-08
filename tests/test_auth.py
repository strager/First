import unittest
from first.authdb import AuthDb

class TestAuth(unittest.TestCase):

    def test_add_new_tokens(self):
        self.authdb = AuthDb()
        self.authdb.add_new_user(
                user_id=5,
                access_token="funnytokenhere",
                refresh_token="funnyrefreshtokenhere"
        )
        self.assertEqual("funnytokenhere", self.authdb.get_access_token(user_id=5))

if __name__ == '__main__':
    unittest.main()
