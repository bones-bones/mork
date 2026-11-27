"""Tests for scripts/check_duplicate_commands.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_duplicate_commands import collect_bindings, find_collisions


YOGG_COLLISION_SOURCE = '''\
from discord.ext import commands

class SpecificCardsCog(commands.Cog):
    @commands.command(aliases=["puzzle", "yogg", "pb"])
    async def puzzlebox(self, ctx):
        pass

    @commands.command()
    async def yogg(self, ctx, cost):
        pass
'''


class CheckDuplicateCommandsTests(unittest.TestCase):
    def test_repo_has_no_collisions(self):
        bindings = collect_bindings()
        self.assertGreater(len(bindings), 0)
        self.assertEqual(find_collisions(bindings), {})

    def test_yogg_style_collision_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SpecificCards.py"
            path.write_text(YOGG_COLLISION_SOURCE, encoding="utf-8")
            bindings = collect_bindings((path,))
            collisions = find_collisions(bindings)
            self.assertIn("yogg", collisions)
            kinds = {b.kind for b in collisions["yogg"]}
            self.assertEqual(kinds, {"alias", "command"})


if __name__ == "__main__":
    unittest.main()
