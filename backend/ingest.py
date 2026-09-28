"""Refresh the player summaries used by StatLine's retrieval API.

Run from the repository root: venv/bin/python -m backend.ingest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg2
import voyageai
from dotenv import load_dotenv
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players
from pgvector import Vector
from pgvector.psycopg2 import register_vector


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WATCHLIST = ROOT / "data" / "watchlist.json"


def season_for_day(day: date) -> str:
    """Return the season that started most recently, before fallback checks."""
    start = day.year if day.month >= 10 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def previous_season(season: str) -> str:
    start = int(season[:4]) - 1
    return f"{start}-{(start + 1) % 100:02d}"


def load_watchlist(path: Path) -> list[str]:
    names = json.loads(path.read_text())
    if not isinstance(names, list) or not names or any(
        not isinstance(name, str) or not name.strip() for name in names
    ):
        raise ValueError("Watchlist must be a nonempty JSON array of player names")
    if len(set(names)) != len(names):
        raise ValueError("Watchlist contains duplicate names")
    return names


def player_id_for(name: str) -> int:
    matches = players.find_players_by_full_name(name)
    if len(matches) != 1:
        raise ValueError(f"Expected one NBA player match for {name!r}, found {len(matches)}")
    return matches[0]["id"]


def fetch_gamelog(player_id: int, season: str, retries: int = 3) -> pd.DataFrame:
    for attempt in range(retries):
        try:
            return playergamelog.PlayerGameLog(
                player_id=player_id, season=season, timeout=20
            ).get_data_frames()[0]
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("Retry loop ended unexpectedly")


def chunk_for(name: str, season: str, games: pd.DataFrame, count: int = 5) -> dict:
    if games.empty:
        raise ValueError(f"No games for {name} in {season}")

    recent = games.assign(_date=pd.to_datetime(games["GAME_DATE"]))
    recent = recent.sort_values("_date", ascending=False).head(count)
    averages = {stat: recent[stat].mean() for stat in ("PTS", "REB", "AST")}
    field_goals_attempted = recent["FGA"].sum()
    field_goal_pct = (
        recent["FGM"].sum() / field_goals_attempted if field_goals_attempted else 0.0
    )
    latest = recent["_date"].iloc[0].date().isoformat()
    earliest = recent["_date"].iloc[-1].date().isoformat()
    game_details = "; ".join(
        f"{row.GAME_DATE} {row.MATCHUP}: {row.PTS} pts/{row.REB} reb/{row.AST} ast"
        for row in recent.itertuples()
    )
    text = (
        f"{name} — {season} regular season, last {len(recent)} games "
        f"({earliest} to {latest}, NBA PlayerGameLog): "
        f"averaging {averages['PTS']:.1f} pts, {averages['REB']:.1f} reb, "
        f"{averages['AST']:.1f} ast on {field_goal_pct * 100:.1f}% field-goal shooting. "
        f"Game-by-game: {game_details}"
    )
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return {"id": f"{slug}_last5", "player": name, "text": text, "latest_game": latest}


def prepare_chunks(names: list[str], season: str, allow_fallback: bool) -> tuple[list[dict], list[str]]:
    chunks = []
    failures = []
    for name in names:
        try:
            player_id = player_id_for(name)
            seasons = [season, previous_season(season)] if allow_fallback else [season]
            for candidate in seasons:
                games = fetch_gamelog(player_id, candidate)
                if not games.empty:
                    chunk = chunk_for(name, candidate, games)
                    chunks.append(chunk)
                    print(f"Fetched {name}: {candidate}, latest game {chunk['latest_game']}")
                    break
            else:
                raise ValueError(f"No games found in {', '.join(seasons)}")
        except Exception as error:
            failures.append(f"{name}: {type(error).__name__}: {error}")
            print(f"Skipped {name}: {type(error).__name__}")
        time.sleep(0.6)  # stats.nba.com is an unofficial data source; avoid bursts.
    return chunks, failures


def store_chunks(chunks: list[dict]) -> None:
    voyage_key = os.getenv("VOYAGE_API_KEY")
    database_url = os.getenv("SUPABASE_DB_URL")
    if not voyage_key or not database_url:
        raise RuntimeError("Set VOYAGE_API_KEY and SUPABASE_DB_URL in .env")

    embeddings = voyageai.Client(api_key=voyage_key).embed(
        [chunk["text"] for chunk in chunks], model="voyage-3", input_type="document"
    ).embeddings
    if len(embeddings) != len(chunks) or any(len(embedding) != 1024 for embedding in embeddings):
        raise RuntimeError("Voyage returned an unexpected embedding count or dimension")

    with closing(psycopg2.connect(database_url, connect_timeout=10, sslmode="require")) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            for chunk, embedding in zip(chunks, embeddings):
                cursor.execute(
                    """
                    insert into public.nba_chunks (id, player, content, embedding)
                    values (%s, %s, %s, %s)
                    on conflict (id) do update
                    set player = excluded.player,
                        content = excluded.content,
                        embedding = excluded.embedding
                    """,
                    (chunk["id"], chunk["player"], chunk["text"], Vector(embedding)),
                )
        connection.commit()
    print(f"Stored {len(chunks)} player summaries.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh StatLine player summaries")
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--season", help="NBA season such as 2025-26; defaults to current season with fallback")
    parser.add_argument("--player", action="append", help="Refresh one named player; repeat for more")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and summarize without embedding or storing")
    args = parser.parse_args()

    names = args.player or load_watchlist(args.watchlist)
    season = args.season or season_for_day(datetime.now(timezone.utc).date())
    if not re.fullmatch(r"20\d{2}-\d{2}", season):
        parser.error("--season must look like 2025-26")
    chunks, failures = prepare_chunks(names, season, allow_fallback=args.season is None)
    if chunks and not args.dry_run:
        load_dotenv(ROOT / ".env")
        store_chunks(chunks)
    if args.dry_run:
        print(f"Dry run: prepared {len(chunks)} player summaries; no embeddings or database writes.")
    for failure in failures:
        print(f"Warning: {failure}")
    return 1 if failures or not chunks else 0


if __name__ == "__main__":
    raise SystemExit(main())
