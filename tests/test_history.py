import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

import pandas as pd

from backend.history import back_to_back_stats, is_back_to_back_question
from backend.history_import import season_has_no_games_yet, season_list, validate_season


class FakeCursor:
    def __init__(self, coverage, rows):
        self.results = [coverage, rows]
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchall(self):
        return self.results.pop(0)


class FakeConnection:
    def __init__(self, coverage, rows):
        self.fake_cursor = FakeCursor(coverage, rows)

    def cursor(self):
        return self.fake_cursor


class HistoryTests(unittest.TestCase):
    def test_season_range(self):
        self.assertEqual(season_list("2014-15", "2016-17"), ["2014-15", "2015-16", "2016-17"])
        with self.assertRaises(ValueError):
            season_list("2014-16", "2016-17")

    def test_empty_current_season_is_skipped_but_historical_gap_is_not(self):
        today = date(2026, 10, 6)
        empty = pd.DataFrame()
        self.assertTrue(season_has_no_games_yet("2026-27", empty, empty, today))
        self.assertFalse(season_has_no_games_yet("2025-26", empty, empty, today))
        self.assertFalse(season_has_no_games_yet("2026-27", pd.DataFrame([{"GAME_ID": "g1"}]), empty, today))

    def test_import_rejects_missing_team_box_score(self):
        teams = pd.DataFrame([
            {"SEASON_YEAR": "2014-15", "TEAM_ID": 1, "GAME_ID": "g1", "GAME_DATE": "2014-10-28", "MATCHUP": "A vs. B"},
            {"SEASON_YEAR": "2014-15", "TEAM_ID": 2, "GAME_ID": "g1", "GAME_DATE": "2014-10-28", "MATCHUP": "B @ A"},
        ])
        players = pd.DataFrame([
            {"SEASON_YEAR": "2014-15", "TEAM_ID": 1, "PLAYER_ID": 1, "GAME_ID": "g1",
             "PTS": 20, "REB": 4, "AST": 5, "FGM": 8, "FGA": 17},
        ])
        with self.assertRaisesRegex(ValueError, "coverage differs"):
            validate_season("2014-15", teams, players)

    @patch("backend.history.season_for_day", return_value="2015-16")
    def test_answer_uses_played_second_nights_and_weighted_field_goals(self, _):
        fetched = datetime(2026, 9, 28, tzinfo=timezone.utc)
        connection = FakeConnection(
            [("2014-15", "complete", fetched), ("2015-16", "complete", fetched)],
            [("2014-15", "g2", date(2014, 10, 29), "HOU @ UTA", 30, 6, 8, 10, 20),
             ("2015-16", "g3", date(2015, 11, 2), "HOU vs. OKC", 20, 4, 6, 5, 20)],
        )
        result = back_to_back_stats("James Harden stats on back to backs starting from 2014-15", connection)
        self.assertIsNotNone(result)
        self.assertIn("25.0 points, 5.0 rebounds, and 7.0 assists", result.answer)
        self.assertIn("37.5% FG (15/40)", result.answer)
        self.assertIn("game g2", result.content)
        self.assertIn("game g3", result.content)
        self.assertIn("t.game_date = t.previous_game_date + 1", connection.fake_cursor.queries[1][0])

    @patch("backend.history.season_for_day", return_value="2015-16")
    def test_bare_year_starts_on_january_first(self, _):
        fetched = datetime(2026, 9, 28, tzinfo=timezone.utc)
        connection = FakeConnection(
            [(season, "complete", fetched) for season in ("2013-14", "2014-15", "2015-16")],
            [("2013-14", "g1", date(2014, 1, 2), "HOU vs. NYK", 20, 4, 6, 7, 15)],
        )
        result = back_to_back_stats("James Harden back-to-backs since 2014", connection)
        self.assertIn("January 1, 2014", result.answer)
        self.assertEqual(connection.fake_cursor.queries[1][1][0], "2013-14")
        self.assertEqual(connection.fake_cursor.queries[1][1][3], date(2014, 1, 1))

    @patch("backend.history.season_for_day", return_value="2016-17")
    def test_missing_season_does_not_return_partial_average(self, _):
        fetched = datetime(2026, 9, 28, tzinfo=timezone.utc)
        connection = FakeConnection([("2014-15", "complete", fetched)], [])
        result = back_to_back_stats("James Harden on back-to-backs since 2014", connection)
        self.assertIsNone(result.answer)
        self.assertIn("2015-16", result.notice)
        self.assertEqual(len(connection.fake_cursor.queries), 1)

    @patch("backend.history.season_for_day", return_value="2026-27")
    def test_october_rollover_uses_latest_contiguous_coverage(self, _):
        fetched = datetime(2026, 9, 28, tzinfo=timezone.utc)
        coverage = [(season, "complete", fetched) for season in season_list("2013-14", "2025-26")]
        connection = FakeConnection(
            coverage,
            [("2025-26", "g1", date(2026, 4, 10), "LAC vs. GSW", 24, 5, 8, 9, 18)],
        )
        result = back_to_back_stats("James Harden back-to-backs since 2014", connection)
        self.assertIn("through 2025-26", result.answer)
        self.assertIn("2026-27 is not loaded", result.answer)
        self.assertIn("2026-27 is not loaded", result.content)
        self.assertTrue(result.source_id.endswith("2025_26"))
        self.assertEqual(connection.fake_cursor.queries[1][1][1], "2025-26")

    @patch("backend.history.season_for_day", return_value="2026-27")
    def test_only_missing_current_season_has_no_average(self, _):
        connection = FakeConnection([], [])
        result = back_to_back_stats("James Harden back-to-backs since 2026-27", connection)
        self.assertIsNone(result.answer)
        self.assertIn("2026-27", result.notice)
        self.assertEqual(len(connection.fake_cursor.queries), 1)

    def test_first_night_is_declined(self):
        self.assertTrue(is_back_to_back_question("Harden B2Bs"))
        result = back_to_back_stats("James Harden first night of back-to-backs", None)
        self.assertIn("First-night", result.notice)

    def test_end_year_and_career_are_not_silently_ignored(self):
        self.assertIn("ending year", back_to_back_stats(
            "James Harden back-to-backs from 2014 through 2020", None).notice)
        self.assertIn("career", back_to_back_stats(
            "James Harden career back-to-back averages", None).notice)


if __name__ == "__main__":
    unittest.main()
