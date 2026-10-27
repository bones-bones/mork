import unittest

from accept_card import parse_errata_id_from_veto_content, _veto_poll_title_line


class VetoPollIntakeParseTests(unittest.TestCase):
    def test_errata_second_line(self):
        self.assertEqual(
            parse_errata_id_from_veto_content("Name by Author\nErrata: 12345"),
            "12345",
        )

    def test_masterpiece_prefix_stripped(self):
        self.assertEqual(
            _veto_poll_title_line("HC9: Cool Card by someone"),
            "Cool Card by someone",
        )


if __name__ == "__main__":
    unittest.main()
