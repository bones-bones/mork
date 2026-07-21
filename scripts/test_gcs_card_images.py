import unittest

from gcs_card_images import (
    parse_gcs_public_url,
    public_gcs_url,
    slug_object_name,
)


class GcsCardImagesTests(unittest.TestCase):
    def test_slug_matches_hellfall_style(self):
        self.assertEqual(slug_object_name("3682"), "3682")
        # Hellfall replaces "/" with "|" then non-[\\w\\-.] with "_", so "|" becomes "_"
        self.assertEqual(slug_object_name("Foo/Bar"), "Foo_Bar")
        self.assertEqual(slug_object_name("a b!c"), "a_b_c")

    def test_public_url_encodes_segments(self):
        self.assertEqual(
            public_gcs_url("hellscube-images", "3682.png"),
            "https://storage.googleapis.com/hellscube-images/3682.png",
        )
        self.assertEqual(
            public_gcs_url("hellscube-images", "Foo|Bar.png"),
            "https://storage.googleapis.com/hellscube-images/Foo%7CBar.png",
        )

    def test_parse_gcs_url(self):
        parsed = parse_gcs_public_url(
            "https://storage.googleapis.com/hellscube-images/3682.png",
            expected_bucket="hellscube-images",
        )
        self.assertEqual(parsed, ("hellscube-images", "3682.png"))
        self.assertIsNone(
            parse_gcs_public_url(
                "https://lh3.googleusercontent.com/d/abc",
                expected_bucket="hellscube-images",
            )
        )


if __name__ == "__main__":
    unittest.main()
