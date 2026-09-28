"""Local HTTP API for StatLine's notebook retrieval pipeline."""

import os
import re
from contextlib import closing
from pathlib import Path
from typing import Literal

import psycopg2
import voyageai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pgvector import Vector
from pgvector.psycopg2 import register_vector
from pydantic import BaseModel, Field

from utils.llm_client import generate_answer
from utils.retrieval import select_named_sources
from backend.player_data import PlayerSummary
from backend.history import back_to_back_stats, is_back_to_back_question
from backend.answer_quality import sourced_fallback, uncited_stat_paragraphs
from backend.nba_data import PlayerOption, mentioned_players, player_snapshot, recommended_players, recommended_summaries, recent_leaders, search_players, season_data


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="StatLine API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Source(BaseModel):
    id: str
    player: str
    content: str
    distance: float


class AskResponse(BaseModel):
    answer: str | None
    sources: list[Source]
    status: Literal["answered", "answer_unavailable", "no_data"]
    notice: str | None = None


def get_connection():
    database_url = os.getenv("SUPABASE_DB_URL")
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL is not configured")
    connection = psycopg2.connect(database_url, connect_timeout=10, sslmode="require")
    register_vector(connection)
    return connection


def retrieve_sources(question: str, limit: int = 25) -> list[Source]:
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if not voyage_key:
        raise RuntimeError("VOYAGE_API_KEY is not configured")

    embedding = voyageai.Client(api_key=voyage_key).embed(
        [question], model="voyage-3", input_type="query"
    ).embeddings[0]

    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, player, content, embedding <=> %s as distance
                from public.nba_chunks
                order by embedding <=> %s
                limit %s
                """,
                (Vector(embedding), Vector(embedding), limit),
            )
            rows = cursor.fetchall()

    return [
        Source(id=row[0], player=row[1], content=row[2], distance=row[3])
        for row in rows
    ]


@app.get("/health")
def health():
    try:
        with closing(get_connection()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select count(*) from public.nba_chunks")
                count = cursor.fetchone()[0]
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database is unavailable") from error
    return {"status": "ok", "chunks": count}


@app.get("/players", response_model=list[PlayerSummary])
def players():
    """Recommend the current regular-season scoring leaders by season PPG."""
    try:
        return recommended_summaries()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Player data is unavailable") from error


@app.get("/recommendations")
def recommendations():
    try:
        return recommended_players()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Scoring leaders are unavailable") from error


@app.get("/player-search", response_model=list[PlayerOption])
def player_search(q: str = Query(min_length=2, max_length=80)):
    return search_players(q)


@app.get("/players/{player_id}", response_model=PlayerSummary)
def player_detail(player_id: int):
    try:
        snapshot = player_snapshot(player_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Player game logs are unavailable") from error
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No NBA regular-season game logs found for this player")
    return snapshot[0]


def source_for_snapshot(snapshot: tuple[PlayerSummary, str]) -> Source:
    summary, content = snapshot
    return Source(id=summary.source_id, player=summary.name, content=content, distance=0.0)


def direct_sources(question: str) -> tuple[list[Source] | None, str | None]:
    """Use exact NBA data for named players and deterministic league rankings."""
    unsupported = {
        r"\b(zone defense|defensive scheme)\b": "Defensive scheme data is not available in StatLine's game logs.",
        r"\b(injur(?:y|ies|ed)|medical status)\b": "Injury status is not available in StatLine's game logs.",
        r"\b(live score|tonight|right now|in progress)\b": "Live game data is not available in StatLine.",
    }
    for pattern, notice in unsupported.items():
        if re.search(pattern, question, re.IGNORECASE):
            return [], notice
    named = mentioned_players(question)
    if named:
        data = season_data()
        snapshots = [player_snapshot(player["id"], data) for player in named]
        missing = [player["full_name"] for player, snapshot in zip(named, snapshots) if snapshot is None]
        if missing:
            return [], f"No regular-season game logs are available for {', '.join(missing)}."
        return [source_for_snapshot(snapshot) for snapshot in snapshots if snapshot], None

    lower = question.lower()
    ranking = bool(re.search(r"\b(who|which|top|most|highest|leader|leading)\b", lower))
    recent = bool(re.search(r"\b(last|past|recent)\b", lower))
    metric = ("PTS" if re.search(r"\b(points?|scor(?:e|es|ing|ers?)|ppg)\b", lower)
              else "REB" if re.search(r"\b(rebounds?|rebounding)\b", lower)
              else "AST" if re.search(r"\b(assists?|assisting)\b", lower) else None)
    if ranking and recent and metric:
        return [source_for_snapshot(snapshot) for snapshot in recent_leaders(metric)], None
    if ranking and metric == "PTS" and re.search(r"\b(season|ppg|points per game|scoring leaders?)\b", lower):
        data = season_data()
        leaders = recommended_players(data)[:10]
        content = (
            f"NBA {data.season} regular-season points-per-game leaders (NBA LeagueLeaders, "
            f"{data.loaded_at[:10]}): " + "; ".join(
                f"#{row['rank']} {row['name']}: {row['season_ppg']:.1f} PPG in {row['season_games']} games"
                for row in leaders
            )
        )
        return [Source(id=f"nba_ppg_leaders_{data.season.replace('-', '_')}",
                       player="NBA scoring leaders", content=content, distance=0.0)], None
    return None, None


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    question = request.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=422, detail="Enter a question of at least 3 characters")

    if is_back_to_back_question(question):
        try:
            with closing(get_connection()) as connection:
                result = back_to_back_stats(question, connection)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Historical stats are unavailable") from error
        if result is None or result.answer is None:
            return AskResponse(answer=None, sources=[], status="no_data",
                               notice=result.notice if result else "Historical stats are unavailable")
        return AskResponse(
            answer=result.answer,
            sources=[Source(id=result.source_id, player=result.player,
                            content=result.content, distance=0.0)],
            status="answered",
        )

    try:
        sources, notice = direct_sources(question)
        if sources is None:
            sources = select_named_sources(question, retrieve_sources(question))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Stats retrieval is unavailable") from error

    if not sources:
        return AskResponse(answer=None, sources=[], status="no_data", notice=notice or "No stats have been loaded yet.")

    if not os.getenv("OPENAI_API_KEY"):
        return AskResponse(
            answer=None,
            sources=sources,
            status="answer_unavailable",
            notice="OpenAI is not configured. Retrieved stats are shown below.",
        )

    context = "\n\n".join(f"[Source: {row.id}] {row.content}" for row in sources)
    try:
        answer = generate_answer(question, context)
    except RuntimeError as error:
        if "OpenAI API credits are exhausted" not in str(error):
            raise HTTPException(status_code=503, detail="Answer generation is unavailable") from error
        return AskResponse(
            answer=None,
            sources=sources,
            status="answer_unavailable",
            notice="OpenAI API credits are exhausted. Retrieved stats are shown below.",
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail="Answer generation is unavailable") from error

    cited_ids = re.findall(r"\[Source: ([^\]]+)\]", answer)
    if (uncited_stat_paragraphs(answer) or not cited_ids
            or any(cited_id not in {source.id for source in sources} for cited_id in cited_ids)):
        answer = sourced_fallback(sources) or answer

    return AskResponse(answer=answer, sources=sources, status="answered")
