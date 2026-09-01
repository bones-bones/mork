import os
import unittest

from hellfall_shared import get_auth_headers


class AuthHeaderTests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("HELLFALL_POSTCARD_API_KEY")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("HELLFALL_POSTCARD_API_KEY", None)
        else:
            os.environ["HELLFALL_POSTCARD_API_KEY"] = self._prev

    def test_explicit_key_is_used(self):
        os.environ["HELLFALL_POSTCARD_API_KEY"] = "from-env"
        headers = get_auth_headers("explicit")
        self.assertEqual(headers["Authorization"], "Bearer explicit")

    def test_no_arg_falls_back_to_env(self):
        os.environ["HELLFALL_POSTCARD_API_KEY"] = "from-env"
        headers = get_auth_headers()
        self.assertEqual(headers["Authorization"], "Bearer from-env")

    def test_missing_key_omits_authorization(self):
        os.environ.pop("HELLFALL_POSTCARD_API_KEY", None)
        headers = get_auth_headers()
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
