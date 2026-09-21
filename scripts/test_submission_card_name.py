import unittest

from get_card_message import get_card_message, parseCardNameAndAuthor, submission_card_name


class SubmissionCardNameTests(unittest.TestCase):
    def test_empty_content(self):
        self.assertEqual(submission_card_name(""), "")

    def test_whitespace_only(self):
        self.assertEqual(submission_card_name("   \n"), "")

    def test_uses_first_line_only(self):
        self.assertEqual(submission_card_name("Bolt\nby @user"), "Bolt")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(submission_card_name("  Lightning Bolt  "), "Lightning Bolt")


class ParseCardNameAndAuthorTests(unittest.TestCase):
    def test_name_and_author(self):
        self.assertEqual(parseCardNameAndAuthor("Bolt by Alice"), ("Bolt", "Alice"))

    def test_name_only_is_no_author(self):
        self.assertEqual(parseCardNameAndAuthor("It's everyone's top"), ("It's everyone's top", ""))
        self.assertEqual(
            get_card_message("It's everyone's top"),
            "**It's everyone's top** by **no author**",
        )

    def test_substring_by_is_not_an_author_separator(self):
        self.assertEqual(
            parseCardNameAndAuthor("Standby Protocol"),
            ("Standby Protocol", ""),
        )
        self.assertEqual(
            get_card_message("Standby Protocol"),
            "**Standby Protocol** by **no author**",
        )

    def test_author_only(self):
        self.assertEqual(parseCardNameAndAuthor("by Alice"), ("", "Alice"))

    def test_empty(self):
        self.assertEqual(parseCardNameAndAuthor(""), ("", ""))
        self.assertEqual(get_card_message(""), "**Crazy card with no name** by **no author**")

    def test_uses_last_by_separator(self):
        self.assertEqual(
            parseCardNameAndAuthor("Attack by Surprise by Bob"),
            ("Attack by Surprise", "Bob"),
        )


if __name__ == "__main__":
    unittest.main()
