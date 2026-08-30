import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from reddit_devvit import (
    devvit_external_url,
    post_accept_via_devvit,
    post_gallery_via_devvit,
    post_reply_via_devvit,
    reddit_accept_via_devvit_enabled,
    reddit_cotd_via_devvit_enabled,
    reddit_gallery_via_devvit_enabled,
    reddit_mirror_via_devvit_enabled,
    reddit_reply_via_devvit_enabled,
    reddit_title_for_acceptance,
    validate_devvit_post_card_secret,
    validate_devvit_post_card_url,
)

EXTERNAL_URL = (
    "https://hellscube-bridge-21otlg-external.devvit.net/external/post-card"
)
MANAGED_TOKEN = "devvit_at_test_token_for_unit_tests"


class RedditDevvitTests(unittest.TestCase):
    def test_feature_flag(self):
        with patch.dict(os.environ, {"REDDIT_ACCEPT_VIA_DEVVIT": "1"}, clear=False):
            self.assertTrue(reddit_accept_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_ACCEPT_VIA_DEVVIT": "0"}, clear=False):
            self.assertFalse(reddit_accept_via_devvit_enabled())

    def test_cotd_feature_flag(self):
        with patch.dict(os.environ, {"REDDIT_COTD_VIA_DEVVIT": "1"}, clear=False):
            self.assertTrue(reddit_cotd_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_COTD_VIA_DEVVIT": "0"}, clear=False):
            self.assertFalse(reddit_cotd_via_devvit_enabled())

    def test_mirror_feature_flag(self):
        with patch.dict(os.environ, {"REDDIT_MIRROR_VIA_DEVVIT": "1"}, clear=False):
            self.assertTrue(reddit_mirror_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_MIRROR_VIA_DEVVIT": "0"}, clear=False):
            self.assertFalse(reddit_mirror_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_MIRROR_VIA_DEVVIT": ""}, clear=False):
            self.assertFalse(reddit_mirror_via_devvit_enabled())

    def test_reply_feature_flag(self):
        with patch.dict(os.environ, {"REDDIT_REPLY_VIA_DEVVIT": "1"}, clear=False):
            self.assertTrue(reddit_reply_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_REPLY_VIA_DEVVIT": "0"}, clear=False):
            self.assertFalse(reddit_reply_via_devvit_enabled())

    def test_gallery_feature_flag(self):
        with patch.dict(os.environ, {"REDDIT_GALLERY_VIA_DEVVIT": "1"}, clear=False):
            self.assertTrue(reddit_gallery_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_GALLERY_VIA_DEVVIT": "0"}, clear=False):
            self.assertFalse(reddit_gallery_via_devvit_enabled())

    def test_devvit_external_url_rewrite(self):
        with patch.dict(os.environ, {"DEVVIT_POST_CARD_URL": EXTERNAL_URL}, clear=False):
            self.assertEqual(
                devvit_external_url("reply-to-post"),
                "https://hellscube-bridge-21otlg-external.devvit.net/external/reply-to-post",
            )
            self.assertEqual(
                devvit_external_url("post-gallery"),
                "https://hellscube-bridge-21otlg-external.devvit.net/external/post-gallery",
            )

    def test_title_uses_set_id(self):
        title = reddit_title_for_acceptance(
            "**Cool Card** by **Author**",
            "SCL.X",
        )
        self.assertEqual(title, "Cool Card by Author was accepted into SCL.X")

    def test_veto_title(self):
        title = reddit_title_for_acceptance(
            "**Bad Card** by **Author**",
            "HCV",
            was_vetoed=True,
        )
        self.assertEqual(title, "Bad Card by Author was vetoed from HCV")

    def test_rejects_api_url(self):
        with self.assertRaisesRegex(RuntimeError, "/external/post-card"):
            validate_devvit_post_card_url("https://example.test/api/post-card")

    def test_rejects_t5_prefix_in_hostname(self):
        with self.assertRaisesRegex(RuntimeError, "t5_"):
            validate_devvit_post_card_url(
                "https://hellscube-bridge-t5_21otlg-external.devvit.net/external/post-card"
            )

    def test_accepts_external_url(self):
        validate_devvit_post_card_url(EXTERNAL_URL)

    def test_rejects_post_card_secret(self):
        with self.assertRaisesRegex(RuntimeError, "devvit_at_"):
            validate_devvit_post_card_secret("postCardSecret-value")

    def test_accepts_managed_token(self):
        validate_devvit_post_card_secret(MANAGED_TOKEN)


class PostAcceptViaDevvitTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_json_payload(self):
        env = {
            "DEVVIT_POST_CARD_URL": EXTERNAL_URL,
            "DEVVIT_POST_CARD_SECRET": MANAGED_TOKEN,
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"ok": True, "postId": "t3_abc"})

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__.return_value = mock_resp
        mock_post_cm.__aexit__.return_value = False

        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_cm

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = False

        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "reddit_devvit.aiohttp.ClientSession",
                return_value=mock_session_cm,
            ),
        ):
            result = await post_accept_via_devvit(
                title="Card was accepted into SOH",
                image_url="https://storage.googleapis.com/bucket/card.png",
                flair_id="flair-id",
            )

        self.assertEqual(result["postId"], "t3_abc")
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["imageUrl"],
                         "https://storage.googleapis.com/bucket/card.png")
        self.assertEqual(
            call_kwargs["headers"]["Authorization"],
            f"Bearer {MANAGED_TOKEN}",
        )
        self.assertEqual(call_kwargs["headers"]["Accept"], "application/json")


class PostReplyViaDevvitTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_reply_payload(self):
        env = {
            "DEVVIT_POST_CARD_URL": EXTERNAL_URL,
            "DEVVIT_POST_CARD_SECRET": MANAGED_TOKEN,
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"ok": True, "commentId": "t1_abc", "permalink": "/r/x/"}
        )

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__.return_value = mock_resp
        mock_post_cm.__aexit__.return_value = False

        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_cm

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = False

        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "reddit_devvit.aiohttp.ClientSession",
                return_value=mock_session_cm,
            ),
        ):
            result = await post_reply_via_devvit(
                post_id="abc123",
                text="hello from discord",
            )

        self.assertEqual(result["commentId"], "t1_abc")
        call_kwargs = mock_session.post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["postId"], "abc123")
        self.assertEqual(
            mock_session.post.call_args.args[0],
            "https://hellscube-bridge-21otlg-external.devvit.net/external/reply-to-post",
        )


class PostGalleryViaDevvitTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_gallery_payload(self):
        env = {
            "DEVVIT_POST_CARD_URL": EXTERNAL_URL,
            "DEVVIT_POST_CARD_SECRET": MANAGED_TOKEN,
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"ok": True, "postId": "t3_gal", "permalink": "/r/HellsCube/"}
        )

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__.return_value = mock_resp
        mock_post_cm.__aexit__.return_value = False

        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_cm

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = False

        urls = [
            "https://storage.googleapis.com/bucket/a.png",
            "https://storage.googleapis.com/bucket/b.png",
        ]

        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "reddit_devvit.aiohttp.ClientSession",
                return_value=mock_session_cm,
            ),
        ):
            result = await post_gallery_via_devvit(
                title="Some of Today's Submissions",
                image_urls=urls,
                flair_id="flair-id",
            )

        self.assertEqual(result["postId"], "t3_gal")
        call_kwargs = mock_session.post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["imageUrls"], urls)
        self.assertEqual(
            mock_session.post.call_args.args[0],
            "https://hellscube-bridge-21otlg-external.devvit.net/external/post-gallery",
        )


if __name__ == "__main__":
    unittest.main()
