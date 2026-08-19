import unittest

from image_response_filename import (
    content_type_for_ext,
    extension_from_image_bytes,
    filename_from_image_response,
    mime_type_from_image_bytes,
    with_image_extension,
)

GIF = b"GIF89a" + b"\x00" * 24
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


class ImageResponseFilenameTests(unittest.TestCase):
    def test_sniff_gif_over_png_url(self):
        name = filename_from_image_response(
            content_disposition=None,
            url="https://storage.googleapis.com/hellscube-images/CoolCard.png",
            content_type="image/png",
            fallback_name="CoolCard",
            body=GIF,
        )
        self.assertEqual(name, "CoolCard.gif")

    def test_content_type_gif_over_png_url(self):
        name = filename_from_image_response(
            content_disposition=None,
            url="https://storage.googleapis.com/hellscube-images/CoolCard.png",
            content_type="image/gif",
            fallback_name="CoolCard",
        )
        self.assertEqual(name, "CoolCard.gif")

    def test_drive_png_name_with_gif_bytes(self):
        name = filename_from_image_response(
            content_disposition='inline;filename="Foo.png"',
            url="https://drive.google.com/uc?id=abc",
            content_type="image/png",
            body=GIF,
        )
        self.assertEqual(name, "Foo.gif")

    def test_png_bytes_keep_png(self):
        name = filename_from_image_response(
            content_disposition=None,
            url="https://storage.googleapis.com/hellscube-images/CoolCard.png",
            content_type="image/png",
            fallback_name="CoolCard",
            body=PNG,
        )
        self.assertEqual(name, "CoolCard.png")

    def test_fallback_without_type_defaults_png(self):
        name = filename_from_image_response(
            content_disposition=None,
            url="https://example.com/noext",
            fallback_name="Card",
        )
        self.assertEqual(name, "Card.png")

    def test_fallback_gif_name_is_not_given_png(self):
        name = filename_from_image_response(
            content_disposition=None,
            url="https://example.com/noext",
            fallback_name="Card.gif",
        )
        self.assertEqual(name, "Card.gif")

    def test_with_image_extension_replaces_instead_of_appending(self):
        self.assertEqual(with_image_extension("Foo.gif", ".png"), "Foo.png")
        self.assertEqual(with_image_extension("Foo.gif", ".gif"), "Foo.gif")
        self.assertEqual(with_image_extension("Foo", ".gif"), "Foo.gif")

    def test_extension_from_image_bytes(self):
        self.assertEqual(extension_from_image_bytes(GIF), ".gif")
        self.assertEqual(extension_from_image_bytes(PNG), ".png")
        self.assertIsNone(extension_from_image_bytes(b"not-an-image"))

    def test_mime_type_from_image_bytes(self):
        self.assertEqual(mime_type_from_image_bytes(GIF), "image/gif")
        self.assertEqual(mime_type_from_image_bytes(PNG), "image/png")
        self.assertEqual(content_type_for_ext(".gif"), "image/gif")
        self.assertIsNone(mime_type_from_image_bytes(b"not-an-image"))


if __name__ == "__main__":
    unittest.main()
