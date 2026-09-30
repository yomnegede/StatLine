"""Import complete regular-season team and player game facts one season at a time.

Run from the repository root: python -m backend.history_import --start-season 2014-15
The source calls happen before the database transaction; a failed season leaves
the last verified snapshot untouched.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from nba_api.stats.endpoints import playergamelogs, teamgamelogs
from psycopg2.extras import execute_values

from backend.ingest import season_for_day

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SOURCE = "NBA Stats TeamGameLogs + PlayerGameLogs, Regular Season"


def season_list(start: str, end: str) -> list[str]:
    for season in (start, end):
        if len(season) != 7 or season[4] != "-" or not season[:4].isdigit() or season[5:] != str((int(season[:4]) + 1) % 100).zfill(2):
            raise ValueError(f"Invalid NBA season: {season}")
    if start > end:
        raise ValueError("Start season must not follow end season")
    return [f"{year}-{str((year + 1) % 100).zfill(2)}" for year in range(int(start[:4]), int(end[:4]) + 1)]


def fetch_season(season: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    teams = teamgamelogs.TeamGameLogs(
        season_nullable=season, season_type_nullable="Regular Season", timeout=45
    ).get_data_frames()[0]
    players = playergamelogs.PlayerGameLogs(
        season_nullable=season, season_type_nullable="Regular Season", timeout=45
    ).get_data_frames()[0]
    return teams, players


def validate_season(season: str, teams: pd.DataFrame, players: pd.DataFrame) -> tuple[list[tuple], list[tuple]]:
    required_team = {"SEASON_YEAR", "TEAM_ID", "GAME_ID", "GAME_DATE", "MATCHUP"}
    required_player = {"SEASON_YEAR", "PLAYER_ID", "TEAM_ID", "GAME_ID", "PTS", "REB", "AST", "FGM", "FGA"}
    if not required_team.issubset(teams.columns) or not required_player.issubset(players.columns):
        raise ValueError(f"{season}: NBA response is missing required columns")
    if teams.empty or players.empty:
        raise ValueError(f"{season}: NBA returned an empty game log")
    if set(teams.SEASON_YEAR.astype(str)) != {season} or set(players.SEASON_YEAR.astype(str)) != {season}:
        raise ValueError(f"{season}: source rows have the wrong season")
    if teams.duplicated(["TEAM_ID", "GAME_ID"]).any() or players.duplicated(["PLAYER_ID", "GAME_ID"]).any():
        raise ValueError(f"{season}: duplicate team or player game IDs")
    team_keys = set(zip(teams.TEAM_ID, teams.GAME_ID))
    player_keys = set(zip(players.TEAM_ID, players.GAME_ID))
    if team_keys != player_keys:
        raise ValueError(f"{season}: team/player game coverage differs ({len(team_keys - player_keys)} missing box scores)")
    if teams.GAME_ID.nunique() * 2 != len(teams):
        raise ValueError(f"{season}: each regular-season game needs exactly two teams")
    numeric = players[["PTS", "REB", "AST", "FGM", "FGA"]].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or (numeric < 0).any().any() or (numeric.FGM > numeric.FGA).any():
        raise ValueError(f"{season}: invalid or missing player stats")
    fetched_at = datetime.now(timezone.utc)
    team_rows = [
        (season, int(row.TEAM_ID), str(row.GAME_ID), pd.Timestamp(row.GAME_DATE).date(),
         str(row.MATCHUP), fetched_at)
        for row in teams.itertuples()
    ]
    player_rows = [
        (season, str(row.GAME_ID), int(row.PLAYER_ID), int(row.TEAM_ID),
         int(row.PTS), int(row.REB), int(row.AST), int(row.FGM), int(row.FGA), fetched_at)
        for row in players.itertuples()
    ]
    return team_rows, player_rows


def import_season(connection, season: str, teams: pd.DataFrame, players: pd.DataFrame) -> tuple[int, int]:
    team_rows, player_rows = validate_season(season, teams, players)
    today = datetime.now(timezone.utc).date()
    current = season_for_day(today)
    # The season helper keeps the last season selected until October. By late
    # August its regular season has finished, including the 2020 bubble.
    finished = season < current or today >= date(int(season[:4]) + 1, 8, 31)
    state = "complete" if finished else "partial"
    # Replace a season atomically so corrections and removed rows do not linger.
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("delete from statline.player_game_stats where season = %s", (season,))
            cursor.execute("delete from statline.team_games where season = %s", (season,))
            execute_values(cursor, """
                insert into statline.team_games
                    (season, team_id, game_id, game_date, matchup, fetched_at) values %s
            """, team_rows, page_size=1000)
            execute_values(cursor, """
                insert into statline.player_game_stats
                    (season, game_id, player_id, team_id, points, rebounds, assists,
                     field_goals_made, field_goals_attempted, fetched_at) values %s
            """, player_rows, page_size=1000)
            cursor.execute("""
                insert into statline.history_coverage
                    (season, state, team_games_count, player_games_count, source, fetched_at)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (season) do update set
                    state = excluded.state,
                    team_games_count = excluded.team_games_count,
                    player_games_count = excluded.player_games_count,
                    source = excluded.source,
                    fetched_at = excluded.fetched_at
            """, (season, state, len(team_rows), len(player_rows), SOURCE, team_rows[0][-1]))
    return len(team_rows), len(player_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-season", default="2014-15")
    parser.add_argument("--end-season", default=None)
    parser.add_argument("--init-schema", action="store_true")
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()
    if args.schema_only and not args.init_schema:
        parser.error("--schema-only requires --init-schema")
    end = args.end_season or season_for_day(datetime.now(timezone.utc).date())
    seasons = season_list(args.start_season, end)
    from backend.main import get_connection
    with closing(get_connection()) as connection:
        if args.init_schema:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute((Path(__file__).resolve().parents[1] / "db" / "statline_history.sql").read_text())
        if args.schema_only:
            print("StatLine history schema initialized")
            return
        for season in seasons:
            print(f"Fetching {season} regular-season facts...", flush=True)
            teams, players = fetch_season(season)
            team_count, player_count = import_season(connection, season, teams, players)
            print(f"{season}: {team_count} team games, {player_count} player games imported", flush=True)


if __name__ == "__main__":
    main()
