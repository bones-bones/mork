import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from accept_card import hcid_from_unapproved_hellfall_id
from sheet_dual_write import sheet_dual_write_enabled
from username_mappings import load_username_mappings_from_file, resolve_username


class SheetDualWriteEnabledTests(unittest.TestCase):
    def test_defaults_on(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SHEET_DUAL_WRITE", None)
            self.assertTrue(sheet_dual_write_enabled())

    def test_zero_is_off(self):
        with patch.dict(os.environ, {"SHEET_DUAL_WRITE": "0"}):
            self.assertFalse(sheet_dual_write_enabled())

    def test_yes_is_on(self):
        with patch.dict(os.environ, {"SHEET_DUAL_WRITE": "yes"}):
            self.assertTrue(sheet_dual_write_enabled())


class HcidFromHellfallIdTests(unittest.TestCase):
    @patch("accept_card.cardSheetUnapproved")
    @patch("accept_card.get_card_by_id")
    def test_catalog_first(self, mock_get_card, mock_sheet):
        card = MagicMock()
        card.hcid = "4242"
        mock_get_card.return_value = card

        self.assertEqual(
            hcid_from_unapproved_hellfall_id("550e8400-e29b-41d4-a716-446655440000"),
            "4242",
        )
        mock_sheet.find.assert_not_called()

    @patch("accept_card.sheet_dual_write_enabled", return_value=True)
    @patch("accept_card.cardSheetUnapproved")
    @patch("accept_card.get_card_by_id", return_value=None)
    def test_sheet_fallback_when_dual_write(self, _mock_get, mock_sheet, _dual):
        cell = MagicMock()
        cell.row = 7
        mock_sheet.find.return_value = cell
        mock_sheet.cell.return_value = MagicMock(value="9999")

        self.assertEqual(hcid_from_unapproved_hellfall_id("uuid-here"), "9999")
        mock_sheet.find.assert_called_once()


class UsernameMappingsFileTests(unittest.TestCase):
    def test_dict_format(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write('{"Alice": ["a1", "a2"], "Bob": "b1"}')
            path = tmp.name
        try:
            self.assertTrue(load_username_mappings_from_file(path))
            self.assertEqual(resolve_username("a1"), "Alice")
            self.assertEqual(resolve_username("b1"), "Bob")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
