import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from deferred_reddit import (
    _parse_manifest_line,
    format_deferred_manifest_entry,
    process_deferred_reddit_posts,
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
        self.assertEqual(post.image_url, "")

    def test_parses_json_format_with_image_url(self):
        line = format_deferred_manifest_entry(
            "card.png",
            "**Name** by **Author**",
            "HC9.1",
            False,
            image_url="https://storage.googleapis.com/bucket/card.png",
        )
        post = _parse_manifest_line(line)
        assert post is not None
        self.assertEqual(post.filename, "card.png")
        self.assertEqual(post.image_url, "https://storage.googleapis.com/bucket/card.png")

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


class ProcessDeferredCatchupTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _seed_batch(tmp: str, *, image_url: str | None) -> str:
        batch = os.path.join(tmp, "batch")
        os.makedirs(batch)
        image_path = os.path.join(batch, "card.png")
        Path(image_path).write_bytes(b"png")
        Path(os.path.join(batch, "manifest.txt")).write_text(
            format_deferred_manifest_entry(
                "card.png",
                "**Cool Card** by **Author**",
                "HC9.1",
                False,
                image_url=image_url,
            )
            + "\n",
            encoding="utf-8",
        )
        return image_path

    async def test_flag_posts_via_devvit_post_card_when_image_url_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = self._seed_batch(
                tmp, image_url="https://storage.googleapis.com/bucket/card.png"
            )

            mock_devvit = AsyncMock(return_value={"ok": True, "postId": "t3_x"})
            with (
                patch("deferred_reddit.DEFERRED_REDDIT_ROOT", tmp),
                patch.dict(os.environ, {"REDDIT_DEFERRED_VIA_DEVVIT": "1"}, clear=False),
                patch("deferred_reddit.post_accept_via_devvit", mock_devvit),
                patch("deferred_reddit.post_to_reddit", AsyncMock()) as mock_praw,
            ):
                posted, errors = await process_deferred_reddit_posts(1)

            self.assertEqual(posted, 1)
            self.assertEqual(errors, [])
            mock_devvit.assert_awaited_once()
            mock_praw.assert_not_awaited()
            self.assertFalse(os.path.exists(image_path))

    async def test_flag_falls_back_to_asyncpraw_without_image_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = self._seed_batch(tmp, image_url=None)

            mock_praw = AsyncMock()
            with (
                patch("deferred_reddit.DEFERRED_REDDIT_ROOT", tmp),
                patch.dict(os.environ, {"REDDIT_DEFERRED_VIA_DEVVIT": "1"}, clear=False),
                patch("deferred_reddit.post_accept_via_devvit", AsyncMock()) as mock_devvit,
                patch("deferred_reddit.post_to_reddit", mock_praw),
            ):
                posted, errors = await process_deferred_reddit_posts(1)

            self.assertEqual(posted, 1)
            self.assertEqual(errors, [])
            mock_devvit.assert_not_awaited()
            mock_praw.assert_awaited_once()
            self.assertFalse(os.path.exists(image_path))


if __name__ == "__main__":
    unittest.main()
