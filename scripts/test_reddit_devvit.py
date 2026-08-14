import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from reddit_devvit import (
    post_accept_via_devvit,
    reddit_accept_via_devvit_enabled,
    reddit_title_for_acceptance,
)


class RedditDevvitTests(unittest.TestCase):
    def test_feature_flag(self):
        with patch.dict(os.environ, {"REDDIT_ACCEPT_VIA_DEVVIT": "1"}, clear=False):
            self.assertTrue(reddit_accept_via_devvit_enabled())
        with patch.dict(os.environ, {"REDDIT_ACCEPT_VIA_DEVVIT": "0"}, clear=False):
            self.assertFalse(reddit_accept_via_devvit_enabled())

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


class PostAcceptViaDevvitTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_json_payload(self):
        env = {
            "DEVVIT_POST_CARD_URL": "https://example.test/api/post-card",
            "DEVVIT_POST_CARD_SECRET": "secret",
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

        with patch.dict(os.environ, env, clear=False):
            with patch(
                "reddit_devvit.aiohttp.ClientSession",
                return_value=mock_session_cm,
            ):
                result = await post_accept_via_devvit(
                    title="Card was accepted into SOH",
                    image_url="https://storage.googleapis.com/bucket/card.png",
                    flair_id="flair-id",
                )

        self.assertEqual(result["postId"], "t3_abc")
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args.kwargs
        self.assertEqual(
            call_kwargs["json"]["imageUrl"],
            "https://storage.googleapis.com/bucket/card.png",
        )
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer secret")


if __name__ == "__main__":
    unittest.main()
