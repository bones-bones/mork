import base64
import unittest

from hellfall_postcard import build_postcard_payload

GIF = b"GIF89a" + b"\x00" * 24
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


class PostcardPayloadTests(unittest.TestCase):
    def test_gif_bytes_send_image_gif_mime(self):
        payload = build_postcard_payload(
            name="Cool Card",
            creators="Author",
            set_id="SOH",
            kind="card",
            image_base64=base64.b64encode(GIF).decode("ascii"),
            hcid="123",
        )
        self.assertEqual(payload["imageMimeType"], "image/gif")
        self.assertIn("imageBase64", payload)
        self.assertEqual(payload["hcid"], "123")

    def test_explicit_mime_wins_over_sniff(self):
        payload = build_postcard_payload(
            name="Cool Card",
            creators="Author",
            set_id="SOH",
            kind="card",
            image_base64=base64.b64encode(PNG).decode("ascii"),
            image_mime_type="image/gif",
        )
        self.assertEqual(payload["imageMimeType"], "image/gif")

    def test_png_sniff(self):
        payload = build_postcard_payload(
            name="Cool Card",
            creators="Author",
            set_id="HCT",
            kind="token",
            image_base64=base64.b64encode(PNG).decode("ascii"),
        )
        self.assertEqual(payload["imageMimeType"], "image/png")

    def test_image_url_path_omits_mime(self):
        payload = build_postcard_payload(
            name="Cool Card",
            creators="Author",
            set_id="SOH",
            kind="card",
            image="https://storage.googleapis.com/bucket/card.png",
        )
        self.assertNotIn("imageMimeType", payload)
        self.assertEqual(
            payload["image"],
            "https://storage.googleapis.com/bucket/card.png",
        )


if __name__ == "__main__":
    unittest.main()
