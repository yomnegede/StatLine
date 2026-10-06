"""Deterministic, source-traceable regular-season back-to-back questions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from backend.history_import import season_list
from backend.ingest import previous_season, season_for_day
from backend.nba_data import mentioned_players


BACK_TO_BACK = re.compile(r"\b(?:back[\s-]*to[\s-]*backs?|b2bs?)\b", re.I)
START_YEAR = re.compile(r"\b(?:since|from|starting(?:\s+in|\s+from)?|beginning(?:\s+in)?)\s+(20\d{2}|19\d{2})(?:-(\d{2}))?\b", re.I)


@dataclass
class HistoryResult:
    answer: str | None
    source_id: str | None = None
    player: str | None = None
    content: str | None = None
    notice: str | None = None


def is_back_to_back_question(question: str) -> bool:
    return bool(BACK_TO_BACK.search(question))


def _start_scope(question: str) -> tuple[str, date, str]:
    match = START_YEAR.search(question)
    year = int(match.group(1)) if match else 2014
    if year < 1946 or year > datetime.now(timezone.utc).year:
        raise ValueError("That starting year is outside NBA history.")
    if match and not match.group(2):
        prior = year - 1
        return f"{prior}-{year % 100:02d}", date(year, 1, 1), f"January 1, {year}"
    season = f"{year}-{(year + 1) % 100:02d}"
    if match and match.group(2) != season[5:]:
        raise ValueError(f"Invalid NBA season: {match.group(0)}")
    return season, date(year, 10, 1), f"the {season} season"


def back_to_back_stats(question: str, connection) -> HistoryResult | None:
    if not is_back_to_back_question(question):
        return None
    if re.search(r"\b(first|opening)\s+(?:night|game|leg)\b", question, re.I):
        return HistoryResult(None, notice="First-night back-to-back splits are not available yet; this query covers second-night games.")
    if re.search(r"\b(playoffs?|postseason|preseason)\b", question, re.I):
        return HistoryResult(None, notice="Back-to-back splits currently cover NBA regular-season games only.")
    if re.search(r"\b(?:to|through|until|before)\s+(?:19|20)\d{2}\b", question, re.I):
        return HistoryResult(None, notice="Back-to-back splits with an ending year are not available yet.")
    if re.search(r"\b(?:between|during|in)\s+(?:19|20)\d{2}\b", question, re.I) and not START_YEAR.search(question):
        return HistoryResult(None, notice="Use “since 2014” for a calendar start or “since 2014-15” for a season start.")
    if re.search(r"\bcareer\b", question, re.I) and not START_YEAR.search(question):
        return HistoryResult(None, notice="Complete career back-to-back coverage is not loaded; name a starting year from 2014 onward.")
    named = mentioned_players(question)
    if len(named) != 1:
        return HistoryResult(None, notice="Name one NBA player for a back-to-back split.")
    player = named[0]
    try:
        start, start_date, start_label = _start_scope(question)
        current_season = season_for_day(datetime.now(timezone.utc).date())
        seasons = season_list(start, current_season)
    except ValueError as error:
        return HistoryResult(None, notice=str(error))
    with connection.cursor() as cursor:
        cursor.execute("""
            select season, state, fetched_at from statline.history_coverage
            where season >= %s and season <= %s order by season
        """, (start, current_season))
        coverage = {season: (state, fetched_at) for season, state, fetched_at in cursor.fetchall()}
        missing = [season for season in seasons if season not in coverage]
        omitted_current = missing == [current_season] and len(seasons) > 1
        if omitted_current:
            end = previous_season(current_season)
            seasons = seasons[:-1]
        else:
            end = current_season
        if missing:
            if not omitted_current:
                return HistoryResult(None, notice=(
                    f"Historical game data is not loaded for {', '.join(missing)}. "
                    "A back-to-back average would be incomplete."
                ))
        cursor.execute("""
            with team_sequence as (
                select season, team_id, game_id, game_date, matchup,
                       lag(game_date) over (
                           partition by season, team_id order by game_date, game_id
                       ) as previous_game_date
                from statline.team_games
                where season >= %s and season <= %s
            )
            select t.season, t.game_id, t.game_date, t.matchup,
                   p.points, p.rebounds, p.assists,
                   p.field_goals_made, p.field_goals_attempted
            from team_sequence t
            join statline.player_game_stats p
              on p.team_id = t.team_id and p.game_id = t.game_id
            where p.player_id = %s and t.game_date >= %s
              and t.game_date = t.previous_game_date + 1
            order by t.game_date, t.game_id
        """, (start, end, player["id"], start_date))
        rows = cursor.fetchall()
    if not rows:
        return HistoryResult(None, notice=f"No qualifying second-night regular-season games found for {player['full_name']} from {start_label} onward.")

    games = len(rows)
    points = sum(row[4] for row in rows)
    rebounds = sum(row[5] for row in rows)
    assists = sum(row[6] for row in rows)
    fgm = sum(row[7] for row in rows)
    fga = sum(row[8] for row in rows)
    fg_pct = (100 * fgm / fga) if fga else None
    partial = [season for season in seasons if coverage[season][0] != "complete"]
    latest_fetch = max(value[1] for value in coverage.values())
    coverage_note = (f" {', '.join(partial)} is still in progress; results are through the latest imported game."
                     if partial else "")
    if omitted_current:
        coverage_note += f" {current_season} is not loaded, so this average excludes that season."
    fg_text = f"{fg_pct:.1f}% FG ({fgm}/{fga})" if fg_pct is not None else "no field-goal attempts"
    source_id = f"nba_b2b_{player['id']}_{start_date.isoformat().replace('-', '_')}_{end.replace('-', '_')}"
    answer = (
        f"{player['full_name']} averaged {points/games:.1f} points, {rebounds/games:.1f} rebounds, "
        f"and {assists/games:.1f} assists in {games} second-night back-to-back regular-season games "
        f"from {start_label} through {end}, shooting {fg_text}. "
        "A back-to-back means the team played on consecutive NBA game dates; only games the player appeared in "
        f"are counted.{coverage_note} [Source: {source_id}]"
    )
    details = "\n".join(
        f"{row[2].isoformat()} {row[3]} (game {row[1]}): {row[4]} PTS, {row[5]} REB, {row[6]} AST, {row[7]}/{row[8]} FG"
        for row in rows
    )
    content = (
        f"NBA Stats TeamGameLogs and PlayerGameLogs, Regular Season, {start_label}–{end}; "
        f"imported through {latest_fetch.date().isoformat()}. {games} qualifying games; "
        f"totals: {points} PTS, {rebounds} REB, {assists} AST, {fgm}/{fga} FG. "
        f"{'Current season excluded: ' + current_season + ' is not loaded. ' if omitted_current else ''}"
        f"Selected games:\n{details}"
    )
    return HistoryResult(answer, source_id, player["full_name"], content)
