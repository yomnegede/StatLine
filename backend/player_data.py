"""Turn the existing sourced game-log summaries into read-only UI data."""

import re
from pydantic import BaseModel


class RecentGame(BaseModel):
    date: str
    matchup: str
    points: int
    rebounds: int
    assists: int


class PlayerSummary(BaseModel):
    id: str
    name: str
    season: str
    games_count: int
    first_game: str
    last_game: str
    points: float
    rebounds: float
    assists: float
    field_goal_pct: float
    games: list[RecentGame]
    source_id: str
    rank: int | None = None
    season_ppg: float | None = None
    season_games: int | None = None


SUMMARY_PATTERN = re.compile(
    r"(?P<season>20\d{2}-\d{2}) regular season, last (?P<count>\d+) games "
    r"\((?P<first>\d{4}-\d{2}-\d{2}) to (?P<last>\d{4}-\d{2}-\d{2}), NBA PlayerGameLog\): "
    r"averaging (?P<points>\d+(?:\.\d+)?) pts, (?P<rebounds>\d+(?:\.\d+)?) reb, "
    r"(?P<assists>\d+(?:\.\d+)?) ast on (?P<fg>\d+(?:\.\d+)?)% field-goal shooting\. "
    r"Game-by-game: (?P<games>.+)$"
)
GAME_PATTERN = re.compile(
    r"(?P<date>.+?) (?P<matchup>[A-Z]{2,3} (?:@|vs\.) [A-Z]{2,3}): "
    r"(?P<points>\d+) pts/(?P<rebounds>\d+) reb/(?P<assists>\d+) ast$"
)


def parse_player_summary(source_id: str, name: str, content: str) -> PlayerSummary | None:
    """Parse the format written by ingest.chunk_for; reject incomplete records."""
    prefix = f"{name} — "
    if not content.startswith(prefix):
        return None
    match = SUMMARY_PATTERN.fullmatch(content[len(prefix):])
    if not match:
        return None
    games = []
    for item in match["games"].split("; "):
        game = GAME_PATTERN.fullmatch(item)
        if not game:
            return None
        games.append(
            RecentGame(
                date=game["date"], matchup=game["matchup"],
                points=int(game["points"]), rebounds=int(game["rebounds"]),
                assists=int(game["assists"]),
            )
        )
    if len(games) != int(match["count"]):
        return None
    return PlayerSummary(
        id=source_id, name=name, season=match["season"],
        games_count=int(match["count"]), first_game=match["first"], last_game=match["last"],
        points=float(match["points"]), rebounds=float(match["rebounds"]),
        assists=float(match["assists"]), field_goal_pct=float(match["fg"]),
        games=games, source_id=source_id,
    )
