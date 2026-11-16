import unittest

from handle_veto_post import (
    VETO_POLL_UUID_PREFIX,
    parse_hcid_from_veto_poll_messages,
    parse_hellfall_uuid_from_veto_poll_messages,
    parse_hellpit_thread_id_from_veto_poll_messages,
)


class VetoPollPromotionRefTests(unittest.TestCase):
    def test_parses_uuid_after_hellpit(self):
        self.assertEqual(
            parse_hellfall_uuid_from_veto_poll_messages(
                [
                    "https://discord.com/channels/1/2/3",
                    f"{VETO_POLL_UUID_PREFIX}550e8400-e29b-41d4-a716-446655440000",
                ]
            ),
            "550e8400-e29b-41d4-a716-446655440000",
        )

    def test_parses_uuid_regardless_of_index(self):
        self.assertEqual(
            parse_hellfall_uuid_from_veto_poll_messages(
                [
                    "system noise",
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

    def test_missing_uuid_or_hcid(self):
        self.assertIsNone(parse_hellfall_uuid_from_veto_poll_messages(["only hellpit link"]))
        self.assertIsNone(parse_hcid_from_veto_poll_messages(["only hellpit link"]))

    def test_uuid_line_not_parsed_as_legacy_hcid(self):
        self.assertIsNone(
            parse_hcid_from_veto_poll_messages(
                ["https://x", f"{VETO_POLL_UUID_PREFIX}550e8400-e29b-41d4-a716-446655440000"]
            )
        )

    def test_parses_hellpit_thread_id_with_uuid_present(self):
        self.assertEqual(
            parse_hellpit_thread_id_from_veto_poll_messages(
                [
                    "https://discord.com/channels/111/222/333444",
                    f"{VETO_POLL_UUID_PREFIX}550e8400-e29b-41d4-a716-446655440000",
                ]
            ),
            333444,
        )

    def test_parses_hellpit_thread_id_when_not_first(self):
        self.assertEqual(
            parse_hellpit_thread_id_from_veto_poll_messages(
                [
                    "noise",
                    "https://discord.com/channels/111/222/999888",
                    f"{VETO_POLL_UUID_PREFIX}abc",
                ]
            ),
            999888,
        )

    def test_hellpit_missing(self):
        self.assertIsNone(
            parse_hellpit_thread_id_from_veto_poll_messages(
                [f"{VETO_POLL_UUID_PREFIX}abc", "42069"]
            )
        )


if __name__ == "__main__":
    unittest.main()
