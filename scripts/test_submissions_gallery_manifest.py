import unittest
from datetime import UTC, datetime, timedelta

from submissions_gallery_manifest import _prune_entries, entries_last_24h


class SubmissionsGalleryManifestTests(unittest.TestCase):
    def test_prune_entries_drops_old(self):
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        recent = datetime.now(UTC).isoformat()
        entries = [
            {"messageId": "1", "submittedAt": old, "imageUrl": "https://x/1.png"},
            {"messageId": "2", "submittedAt": recent, "imageUrl": "https://x/2.png"},
        ]
        pruned = _prune_entries(entries)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["messageId"], "2")

    def test_entries_last_24h(self):
        now = datetime.now(UTC)
        manifest = {
            "entries": [
                {
                    "messageId": "old",
                    "submittedAt": (now - timedelta(hours=30)).isoformat(),
                    "imageUrl": "https://x/old.png",
                },
                {
                    "messageId": "new",
                    "submittedAt": (now - timedelta(hours=2)).isoformat(),
                    "imageUrl": "https://x/new.png",
                },
            ]
        }
        recent = entries_last_24h(manifest)
        self.assertEqual([e["messageId"] for e in recent], ["new"])


if __name__ == "__main__":
    unittest.main()
