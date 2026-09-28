import unittest
from datetime import date

import pandas as pd

from backend.ingest import chunk_for, previous_season, season_for_day
from utils.retrieval import select_named_sources


class IngestTests(unittest.TestCase):
    def test_season_boundary(self):
        self.assertEqual(season_for_day(date(2026, 9, 28)), "2025-26")
        self.assertEqual(season_for_day(date(2026, 10, 1)), "2026-27")
        self.assertEqual(previous_season("2026-27"), "2025-26")

    def test_chunk_uses_latest_games_and_weighted_field_goal_pct(self):
        games = pd.DataFrame(
            [
                {"GAME_DATE": "Apr 01, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 10, "REB": 2, "AST": 3, "FGM": 1, "FGA": 2},
                {"GAME_DATE": "Apr 03, 2026", "MATCHUP": "AAA @ CCC", "PTS": 20, "REB": 4, "AST": 5, "FGM": 3, "FGA": 10},
            ]
        )
        chunk = chunk_for("Test Player", "2025-26", games)
        self.assertEqual(chunk["id"], "test_player_last5")
        self.assertEqual(chunk["latest_game"], "2026-04-03")
        self.assertIn("15.0 pts", chunk["text"])
        self.assertIn("33.3% field-goal shooting", chunk["text"])
        self.assertLess(chunk["text"].index("Apr 03"), chunk["text"].index("Apr 01"))

    def test_named_players_survive_retrieval_order(self):
        sources = [
            {"player": "Nikola Jokic"},
            {"player": "Devin Booker"},
            {"player": "Jayson Tatum"},
        ]
        selected = select_named_sources("Compare Tatum and Booker", sources)
        self.assertEqual([row["player"] for row in selected], ["Devin Booker", "Jayson Tatum"])


if __name__ == "__main__":
    unittest.main()
