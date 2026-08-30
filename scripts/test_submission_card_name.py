import unittest

from get_card_message import submission_card_name


class SubmissionCardNameTests(unittest.TestCase):
    def test_empty_content(self):
        self.assertEqual(submission_card_name(""), "")

    def test_whitespace_only(self):
        self.assertEqual(submission_card_name("   \n"), "")

    def test_uses_first_line_only(self):
        self.assertEqual(submission_card_name("Bolt\nby @user"), "Bolt")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(submission_card_name("  Lightning Bolt  "), "Lightning Bolt")


if __name__ == "__main__":
    unittest.main()
