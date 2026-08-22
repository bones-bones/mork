import unittest

from deferred_reddit import (
    _parse_manifest_line,
    format_deferred_manifest_entry,
    safe_card_filename,
)
from reddit_functions import reddit_title_for_acceptance


class RedditTitleTests(unittest.TestCase):
    def test_acceptance_uses_set_id(self):
        title = reddit_title_for_acceptance(
            "**Cool Card** by **Author**",
            "SOH",
        )
        self.assertEqual(title, "Cool Card by Author was accepted into SOH")

    def test_scube_lair_set_id(self):
        title = reddit_title_for_acceptance(
            "**Secret Lair Card** by **Author**",
            "SCL.X",
        )
        self.assertEqual(title, "Secret Lair Card by Author was accepted into SCL.X")

    def test_vetoed_uses_set_id(self):
        title = reddit_title_for_acceptance(
            "**Bad Card** by **Author**",
            "HCV",
            was_vetoed=True,
        )
        self.assertEqual(title, "Bad Card by Author was vetoed from HCV")

    def test_unicode_card_name_in_title(self):
        title = reddit_title_for_acceptance(
            "**Æther Channel™ — {W}{U}** by **José**",
            "SCL.X",
        )
        self.assertEqual(
            title,
            "Æther Channel™ — {W}{U} by José was accepted into SCL.X",
        )


class DeferredManifestTests(unittest.TestCase):
    def test_parses_json_format_with_unicode_and_tabs(self):
        line = format_deferred_manifest_entry(
            'Bob\'s "Cool" Card™.png',
            '**Bob\'s "Cool" Card™ — Æther {W}{U}** by **Author**\twith\ttabs',
            "SCL.X",
            False,
        )
        post = _parse_manifest_line(line)
        assert post is not None
        self.assertEqual(post.filename, 'Bob\'s "Cool" Card™.png')
        self.assertIn("Æther", post.card_message)
        self.assertIn("\twith\ttabs", post.card_message)
        self.assertEqual(post.set_id, "SCL.X")

    def test_parses_new_tab_format_with_set_id(self):
        post = _parse_manifest_line("card.png\t**Name** by **Author**\tSCL.X\t0")
        assert post is not None
        self.assertEqual(post.filename, "card.png")
        self.assertEqual(post.card_message, "**Name** by **Author**")
        self.assertEqual(post.set_id, "SCL.X")
        self.assertFalse(post.was_vetoed)

    def test_parses_legacy_title_format(self):
        post = _parse_manifest_line("card.png\tName by Author was accepted into HC9")
        assert post is not None
        self.assertEqual(post.title, "Name by Author was accepted into HC9")


class SafeFilenameTests(unittest.TestCase):
    def test_replaces_path_unsafe_chars(self):
        self.assertEqual(
            safe_card_filename('Bob/Cool:Card*"<>|', ".png"),
            "Bob|Cool|Card|||||.png",
        )

    def test_preserves_unicode(self):
        self.assertEqual(
            safe_card_filename("Æther™ — {W}{U}", ".png"),
            "Æther™ — {W}{U}.png",
        )
        self.assertEqual(safe_card_filename("Polluted Δ", ".png"), "Polluted Δ.png")


if __name__ == "__main__":
    unittest.main()
