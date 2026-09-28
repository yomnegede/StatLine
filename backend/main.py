"""Local HTTP API for StatLine's notebook retrieval pipeline."""

import os
from contextlib import closing
from pathlib import Path
from typing import Literal

import psycopg2
import voyageai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pgvector import Vector
from pgvector.psycopg2 import register_vector
from pydantic import BaseModel, Field

from utils.llm_client import generate_answer
from utils.retrieval import select_named_sources


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="StatLine API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    question = request.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=422, detail="Enter a question of at least 3 characters")

    try:
        sources = select_named_sources(question, retrieve_sources(question))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Stats retrieval is unavailable") from error

    if not sources:
        return AskResponse(answer=None, sources=[], status="no_data", notice="No stats have been loaded yet.")

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

    return AskResponse(answer=answer, sources=sources, status="answered")
