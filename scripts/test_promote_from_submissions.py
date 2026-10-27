import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from accept_card import PostcardWrite, promote_card_to_database, promote_from_submissions
from hellfall_postcard import PostcardSyncError


class PromoteCardToDatabaseTests(unittest.IsolatedAsyncioTestCase):
    @patch("accept_card.cardSheetUnapproved")
    @patch("accept_card._sync_postcard_from_bytes", new_callable=AsyncMock)
    async def test_create_appends_sheet_row(self, mock_sync, mock_sheet):
        mock_sheet.get_all_values.return_value = [["header"]]
        mock_sheet.find.return_value = None
        mock_sync.return_value = (
            "https://example.com/card.png",
            PostcardWrite(
                doc_id="doc1",
                was_create=True,
                previous=None,
                hcid="9001",
                image_url="https://example.com/card.png",
                hellfall_id="550e8400-e29b-41d4-a716-446655440000",
            ),
        )

        result = await promote_card_to_database(
            file_data=b"\x89PNG",
            cardName="Test Card",
            authorName="author",
        )

        self.assertEqual(result.hcid, "9001")
        mock_sync.assert_awaited_once()
        self.assertIsNone(mock_sync.await_args.kwargs.get("hcid"))
        mock_sheet.update_cells.assert_called_once()

    @patch("accept_card.cardSheetUnapproved")
    @patch("accept_card._sync_postcard_from_bytes", new_callable=AsyncMock)
    async def test_existing_hcid_updates_row(self, mock_sync, mock_sheet):
        mock_row = MagicMock()
        mock_row.row = 42
        mock_sheet.find.return_value = mock_row
        mock_sync.return_value = (
            "https://example.com/new.png",
            PostcardWrite(
                doc_id="doc1",
                was_create=False,
                previous={"hcid": "123"},
                hcid="123",
                image_url="https://example.com/new.png",
                hellfall_id="550e8400-e29b-41d4-a716-446655440001",
            ),
        )

        result = await promote_card_to_database(
            file_data=b"\x89PNG",
            cardName="Renamed",
            authorName="author",
            existing_hcid="123",
        )

        self.assertEqual(result.sheet_row, 42)
        mock_sync.assert_awaited_once_with(
            file_data=b"\x89PNG",
            card_name="Renamed",
            author_name="author",
            set_id=mock_sync.await_args.kwargs["set_id"],
            hcid="123",
        )
        mock_sheet.update_cells.assert_called_once()


class PromoteFromSubmissionsTests(unittest.IsolatedAsyncioTestCase):
    @patch("accept_card.intake_veto_poll_message", new_callable=AsyncMock)
    @patch("accept_card.getVetoChannel")
    async def test_posts_veto_then_intake(self, mock_get_veto, mock_intake):
        mock_intake.return_value = MagicMock(
            hcid="555",
            image_url="https://x",
            sheet_row=2,
            hellfall_id="550e8400-e29b-41d4-a716-446655440000",
        )
        veto_ch = MagicMock()
        veto_ch.send = AsyncMock(return_value=MagicMock())
        mock_get_veto.return_value = veto_ch
        bot = MagicMock()
        file = discord.File(fp=io.BytesIO(b"img"), filename="c.png")

        hcid = (
            await promote_from_submissions(
                bot=bot,
                veto_content="Card by author",
                file=file,
                cardName="Card",
                authorName="author",
            )
        ).hcid

        self.assertEqual(hcid, "555")
        mock_intake.assert_awaited_once()

    @patch("accept_card.intake_veto_poll_message", new_callable=AsyncMock)
    @patch("accept_card.getVetoChannel")
    async def test_propagates_intake_failure(self, mock_get_veto, mock_intake):
        mock_intake.side_effect = PostcardSyncError("nope")
        veto_ch = MagicMock()
        veto_ch.send = AsyncMock(return_value=MagicMock())
        mock_get_veto.return_value = veto_ch
        bot = MagicMock()
        file = discord.File(fp=io.BytesIO(b"img"), filename="c.png")

        with self.assertRaises(PostcardSyncError):
            await promote_from_submissions(
                bot=bot,
                veto_content="x",
                file=file,
                cardName="x",
                authorName="y",
            )


if __name__ == "__main__":
    unittest.main()
