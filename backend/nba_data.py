"""NBA player discovery and on-demand game-log snapshots.

The leaderboard is for recommendations; it never limits who can be asked about.
Responses use the NBA's regular-season game logs as their cited source. The
season batch is cached to avoid one NBA HTTP request per player or visitor.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from nba_api.stats.endpoints import leagueleaders, playercareerstats, playergamelog, playergamelogs
from nba_api.stats.static import players as nba_players
from pydantic import BaseModel

from backend.ingest import chunk_for, previous_season, season_for_day
from backend.player_data import PlayerSummary, parse_player_summary


CACHE_SECONDS = 6 * 60 * 60
RECOMMENDATION_COUNT = 16
_cache_lock = threading.Lock()
_season_cache: tuple[float, "SeasonData"] | None = None
_historical_cache: dict[int, tuple[float, tuple[PlayerSummary, str] | None]] = {}


class PlayerOption(BaseModel):
    id: int
    name: str
    active: bool


@dataclass
class SeasonData:
    season: str
    leaders: pd.DataFrame
    games: pd.DataFrame
    loaded_at: str


def normalized(value: str) -> str:
    """Treat accented NBA names and their ASCII spellings as equivalent."""
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char))


def player_catalog() -> list[dict]:
    return nba_players.get_players()


def player_by_id(player_id: int) -> dict | None:
    return next((player for player in player_catalog() if player["id"] == player_id), None)


def search_players(query: str, limit: int = 8) -> list[PlayerOption]:
    query = normalized(query.strip())
    if len(query) < 2:
        return []
    matches = [player for player in player_catalog() if query in normalized(player["full_name"])]
    matches.sort(key=lambda player: (
        not player["is_active"],
        not normalized(player["full_name"]).startswith(query),
        len(player["full_name"]),
        player["full_name"],
    ))
    return [PlayerOption(id=player["id"], name=player["full_name"], active=player["is_active"]) for player in matches[:limit]]


def mentioned_players(question: str, limit: int = 4) -> list[dict]:
    """Find explicit NBA names; avoid guessing common or ambiguous surnames."""
    text = normalized(question)
    found: list[dict] = []
    spans: list[tuple[int, int]] = []
    for player in sorted(player_catalog(), key=lambda item: len(item["full_name"]), reverse=True):
        name = normalized(player["full_name"])
        match = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text)
        if match and not any(match.start() < end and match.end() > start for start, end in spans):
            found.append(player)
            spans.append(match.span())
            if len(found) >= limit:
                break
    if found:
        return sorted(found, key=lambda player: text.find(normalized(player["full_name"])))

    active = nba_players.get_active_players()
    by_surname: dict[str, list[dict]] = {}
    for player in active:
        by_surname.setdefault(normalized(player["last_name"]), []).append(player)
    common_words = {"brown", "green", "white", "young", "williams", "smith", "johnson", "jones", "allen", "martin", "walker", "love", "ball"}
    for surname, candidates in by_surname.items():
        if len(candidates) == 1 and len(surname) >= 5 and surname not in common_words:
            match = re.search(rf"(?<!\w){re.escape(surname)}(?!\w)", text)
            if match:
                found.append(candidates[0])
    aliases = {"lebron": "LeBron James", "steph": "Stephen Curry", "sga": "Shai Gilgeous-Alexander", "ant": "Anthony Edwards"}
    for alias, name in aliases.items():
        if re.search(rf"(?<!\w){alias}(?!\w)", text):
            player = next((item for item in active if item["full_name"] == name), None)
            if player:
                found.append(player)
    unique = {player["id"]: player for player in found}
    return sorted(unique.values(), key=lambda player: (
        text.find(normalized(player["last_name"])) if normalized(player["last_name"]) in text
        else text.find(normalized(player["first_name"])) if normalized(player["first_name"]) in text
        else len(text)
    ))[:limit]


def _fetch_season(season: str) -> SeasonData | None:
    leaders = leagueleaders.LeagueLeaders(
        per_mode48="PerGame", scope="S", season=season,
        season_type_all_star="Regular Season", stat_category_abbreviation="PTS", timeout=25,
    ).get_data_frames()[0]
    if leaders.empty:
        return None
    games = playergamelogs.PlayerGameLogs(
        season_nullable=season, season_type_nullable="Regular Season", timeout=30,
    ).get_data_frames()[0]
    if games.empty:
        return None
    return SeasonData(season, leaders.sort_values("PTS", ascending=False), games,
                      datetime.now(timezone.utc).isoformat())


def season_data() -> SeasonData:
    global _season_cache
    now = time.monotonic()
    if _season_cache and _season_cache[0] > now:
        return _season_cache[1]
    with _cache_lock:
        if _season_cache and _season_cache[0] > time.monotonic():
            return _season_cache[1]
        season = season_for_day(datetime.now(timezone.utc).date())
        for candidate in (season, previous_season(season)):
            for attempt in range(2):
                try:
                    data = _fetch_season(candidate)
                    break
                except Exception as error:
                    if attempt == 0:
                        time.sleep(1)
                        continue
                    if _season_cache and _season_cache[1].season == candidate:  # Preserve known data through a temporary NBA outage.
                        return _season_cache[1]
                    raise RuntimeError("NBA season data is unavailable") from error
            if data:
                _season_cache = (time.monotonic() + CACHE_SECONDS, data)
                return data
        if _season_cache:
            return _season_cache[1]
        raise RuntimeError("No NBA regular-season games are available yet")


def recommended_players(data: SeasonData | None = None) -> list[dict]:
    data = data or season_data()
    return [
        {"id": int(row.PLAYER_ID), "rank": int(row.RANK), "name": str(row.PLAYER),
         "season_ppg": float(row.PTS), "season_games": int(row.GP), "season": data.season}
        for row in data.leaders.head(RECOMMENDATION_COUNT).itertuples()
    ]


def _summary_from_games(player_id: int, name: str, season: str, games: pd.DataFrame) -> tuple[PlayerSummary, str] | None:
    if games.empty:
        return None
    recent = games.copy()
    recent["GAME_DATE"] = pd.to_datetime(recent["GAME_DATE"]).dt.strftime("%b %d, %Y")
    chunk = chunk_for(name, season, recent)
    summary = parse_player_summary(chunk["id"], name, chunk["text"])
    return (summary, chunk["text"]) if summary else None


def player_snapshot(player_id: int, data: SeasonData | None = None) -> tuple[PlayerSummary, str] | None:
    player = player_by_id(player_id)
    if not player:
        return None
    data = data or season_data()
    games = data.games.loc[data.games["PLAYER_ID"] == player_id]
    if not games.empty:
        return _summary_from_games(player_id, player["full_name"], data.season, games)

    cached = _historical_cache.get(player_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    career = playercareerstats.PlayerCareerStats(player_id=player_id, timeout=25).season_totals_regular_season.get_data_frame()
    if career.empty:
        _historical_cache[player_id] = (time.monotonic() + CACHE_SECONDS, None)
        return None
    latest = sorted(career["SEASON_ID"].tolist())[-1]
    games = playergamelog.PlayerGameLog(player_id=player_id, season=latest, timeout=25).get_data_frames()[0]
    snapshot = _summary_from_games(player_id, player["full_name"], latest, games)
    _historical_cache[player_id] = (time.monotonic() + CACHE_SECONDS, snapshot)
    return snapshot


def recommended_summaries(data: SeasonData | None = None) -> list[PlayerSummary]:
    data = data or season_data()
    summaries = []
    for recommendation in recommended_players(data):
        snapshot = player_snapshot(recommendation["id"], data)
        if snapshot:
            summary, _ = snapshot
            summaries.append(summary.model_copy(update={
                "rank": recommendation["rank"], "season_ppg": recommendation["season_ppg"],
                "season_games": recommendation["season_games"],
            }))
    return summaries


def recent_leaders(metric: str, count: int = 5, data: SeasonData | None = None) -> list[tuple[PlayerSummary, str]]:
    """Rank each player's own latest five games, not the league's last five dates."""
    data = data or season_data()
    if metric not in {"PTS", "REB", "AST"}:
        raise ValueError("Unsupported recent ranking metric")
    recent = data.games.sort_values("GAME_DATE", ascending=False).groupby("PLAYER_ID").head(5)
    ranked = recent.groupby("PLAYER_ID").agg(games=(metric, "size"), average=(metric, "mean"))
    ranked = ranked.loc[ranked["games"] == 5].sort_values("average", ascending=False).head(count)
    return [snapshot for player_id in ranked.index
            if (snapshot := player_snapshot(int(player_id), data)) is not None]
