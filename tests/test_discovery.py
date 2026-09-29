import unittest
from unittest.mock import patch

import pandas as pd

from backend.main import direct_sources
from backend.answer_quality import sourced_fallback, uncited_stat_paragraphs
from backend.nba_data import SeasonData, mentioned_players, player_snapshot, recommended_players, search_players, season_data
from evals.run import grade


class DiscoveryTests(unittest.TestCase):
    def test_unlisted_and_accented_players_resolve(self):
        self.assertEqual(search_players("Jalen Johnson")[0].name, "Jalen Johnson")
        self.assertEqual([p["full_name"] for p in mentioned_players("Compare Jalen Johnson and Luka Doncic")],
                         ["Jalen Johnson", "Luka Dončić"])
        self.assertEqual([p["full_name"] for p in mentioned_players("Compare Tatum and Booker")],
                         ["Jayson Tatum", "Devin Booker"])

    def test_batch_game_logs_support_player_outside_recommendations(self):
        player = search_players("Jalen Johnson")[0]
        dates = ["2026-04-11", "2026-04-09", "2026-04-07", "2026-04-05", "2026-04-03"]
        games = pd.DataFrame([
            {"PLAYER_ID": player.id, "GAME_DATE": day, "MATCHUP": "ATL vs. BOS",
             "PTS": 20 + index, "REB": 8, "AST": 5, "FGM": 8, "FGA": 16}
            for index, day in enumerate(dates)
        ])
        data = SeasonData("2025-26", pd.DataFrame(), games, "2026-04-12")
        snapshot = player_snapshot(player.id, data)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot[0].points, 22.0)
        self.assertEqual(len(snapshot[0].games), 5)
        self.assertIn("Jalen Johnson", snapshot[1])

    def test_recommendations_rank_season_ppg(self):
        board = pd.DataFrame([
            {"PLAYER_ID": 1, "RANK": 2, "PLAYER": "Second", "GP": 70, "PTS": 24.0},
            {"PLAYER_ID": 2, "RANK": 1, "PLAYER": "First", "GP": 65, "PTS": 30.0},
        ])
        data = SeasonData("2025-26", board.sort_values("PTS", ascending=False), pd.DataFrame(), "2026-04-12")
        self.assertEqual([row["name"] for row in recommended_players(data)], ["First", "Second"])

    def test_season_network_error_does_not_select_previous_year(self):
        with patch("backend.nba_data._season_cache", None), \
             patch("backend.nba_data._fetch_season", side_effect=TimeoutError("NBA timeout")) as fetch, \
             patch("backend.nba_data.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                season_data()
        self.assertEqual(fetch.call_count, 2)

    def test_unsupported_question_declines_without_sources(self):
        sources, notice = direct_sources("How does Tatum play against zone defense?")
        self.assertEqual(sources, [])
        self.assertIn("not available", notice)

    def test_eval_catches_missing_citation_and_wrong_average(self):
        case = {"kind": "named_average", "expected_players": ["Jalen Johnson"]}
        result = {"status": "answered", "answer": "Jalen Johnson averaged 22.0 points. [Source: jalen]",
                  "sources": [{"id": "jalen", "player": "Jalen Johnson",
                               "content": "Jalen Johnson averaging 22.0 pts"}]}
        self.assertTrue(all(grade(case, result).values()))
        result["answer"] = "Jalen Johnson averaged 25.0 points. [Source: wrong]"
        self.assertFalse(grade(case, result)["citations_reference_retrieved_sources"])
        self.assertFalse(grade(case, result)["states_source_average"])

    def test_uncited_stat_claim_uses_grounded_fallback(self):
        from backend.main import Source
        source = Source(id="jalen_last5", player="Jalen Johnson", distance=0.0,
                        content="Jalen Johnson — 2025-26 regular season, last 5 games "
                                "(2026-04-01 to 2026-04-10, NBA PlayerGameLog): "
                                "averaging 22.0 pts, 8.0 reb, 5.0 ast on 50.0% field-goal shooting. Game-by-game: ...")
        self.assertTrue(uncited_stat_paragraphs("Jalen averaged 25.0 points."))
        fallback = sourced_fallback([source])
        self.assertIn("22.0 points", fallback)
        self.assertIn("[Source: jalen_last5]", fallback)
        self.assertFalse(uncited_stat_paragraphs(fallback))

    def test_uncited_answer_with_legacy_summary_is_unavailable(self):
        from backend.main import AskRequest, Source, ask

        source = Source(
            id="tatum_last5", player="Jayson Tatum", distance=0.0,
            content="Jayson Tatum — last 5 games (Apr 01 to Apr 10): "
                    "averaging 22.0 pts, 8.0 reb, 5.0 ast on 50.0% shooting from the field.",
        )
        with patch("backend.main.direct_sources", return_value=([source], None)), \
             patch("backend.main.os.getenv", return_value="test-key"), \
             patch("backend.main.generate_answer", return_value="Tatum averaged 25 points."):
            result = ask(AskRequest(question="How has Tatum played recently?"))

        self.assertEqual(result.status, "answer_unavailable")
        self.assertIsNone(result.answer)
        self.assertEqual(result.sources, [source])

    def test_uncited_answer_uses_parseable_fallback(self):
        from backend.main import AskRequest, Source, ask

        source = Source(
            id="tatum_last5", player="Jayson Tatum", distance=0.0,
            content="Jayson Tatum — 2025-26 regular season, last 5 games "
                    "(2026-04-01 to 2026-04-10, NBA PlayerGameLog): "
                    "averaging 22.0 pts, 8.0 reb, 5.0 ast on 50.0% field-goal shooting.",
        )
        with patch("backend.main.direct_sources", return_value=([source], None)), \
             patch("backend.main.os.getenv", return_value="test-key"), \
             patch("backend.main.generate_answer", return_value="Tatum averaged 25 points."):
            result = ask(AskRequest(question="How has Tatum played recently?"))

        self.assertEqual(result.status, "answered")
        self.assertIn("22.0 points", result.answer)
        self.assertNotIn("25 points", result.answer)


if __name__ == "__main__":
    unittest.main()
