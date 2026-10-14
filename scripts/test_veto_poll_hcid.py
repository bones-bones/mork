import unittest

from handle_veto_post import parse_hcid_from_veto_poll_messages


class VetoPollHcidTests(unittest.TestCase):
    def test_parses_second_line(self):
        self.assertEqual(
            parse_hcid_from_veto_poll_messages(
                ["https://discord.com/channels/1/2/3", "42069"]
            ),
            "42069",
        )

    def test_requires_two_messages(self):
        self.assertIsNone(parse_hcid_from_veto_poll_messages(["only hellpit link"]))

    def test_rejects_non_numeric(self):
        self.assertIsNone(
            parse_hcid_from_veto_poll_messages(["https://x", "Errata: 12"])
        )


if __name__ == "__main__":
    unittest.main()
