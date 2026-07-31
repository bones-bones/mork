import unittest

from cogs.lifecycle.design_hell_acceptance import (
    card_name_and_author_from_design_hell_message,
    parse_set_id_from_design_hell_prompt,
)


class DesignHellAcceptanceTests(unittest.TestCase):
    def test_parses_plain_set_line(self):
        content = (
            "The current prompt is: Pride Month Celebration!\n"
            "Submissions will close on: July 4, 2026 at 11:00 AM\n"
            "Set: SCL.X"
        )
        self.assertEqual(parse_set_id_from_design_hell_prompt(content), "SCL.X")

    def test_parses_bold_set_value(self):
        content = (
            "The current prompt is: Pride Month Celebration!\n"
            "Submissions will close on: July 4, 2026 at 11:00 AM\n"
            "Set: **SCL.X**"
        )
        self.assertEqual(parse_set_id_from_design_hell_prompt(content), "SCL.X")

    def test_returns_none_without_set_line(self):
        self.assertIsNone(parse_set_id_from_design_hell_prompt("No set here"))

    def test_uses_first_line_as_card_name_and_poster_as_author(self):
        card_name, author = card_name_and_author_from_design_hell_message(
            "Pride Parade\nextra line ignored", "coolcreator"
        )
        self.assertEqual(card_name, "Pride Parade")
        self.assertEqual(author, "coolcreator")


if __name__ == "__main__":
    unittest.main()
