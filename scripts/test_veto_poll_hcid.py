import unittest

from handle_veto_post import (
    VETO_POLL_UUID_PREFIX,
    parse_hcid_from_veto_poll_messages,
    parse_hellfall_uuid_from_veto_poll_messages,
)


class VetoPollPromotionRefTests(unittest.TestCase):
    def test_parses_uuid_second_line(self):
        self.assertEqual(
            parse_hellfall_uuid_from_veto_poll_messages(
                [
                    "https://discord.com/channels/1/2/3",
                    f"{VETO_POLL_UUID_PREFIX}550e8400-e29b-41d4-a716-446655440000",
                ]
            ),
            "550e8400-e29b-41d4-a716-446655440000",
        )

    def test_parses_legacy_numeric_hcid(self):
        self.assertEqual(
            parse_hcid_from_veto_poll_messages(
                ["https://discord.com/channels/1/2/3", "42069"]
            ),
            "42069",
        )

    def test_requires_two_messages(self):
        self.assertIsNone(parse_hellfall_uuid_from_veto_poll_messages(["only hellpit link"]))
        self.assertIsNone(parse_hcid_from_veto_poll_messages(["only hellpit link"]))

    def test_uuid_line_not_parsed_as_legacy_hcid(self):
        self.assertIsNone(
            parse_hcid_from_veto_poll_messages(
                ["https://x", f"{VETO_POLL_UUID_PREFIX}550e8400-e29b-41d4-a716-446655440000"]
            )
        )


if __name__ == "__main__":
    unittest.main()
