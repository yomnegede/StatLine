# StatLine

> Ask questions about NBA players in plain English and get answers grounded in real game data.

StatLine is an NBA analytics assistant built around a simple idea: natural-language answers should be backed by inspectable statistics, not plausible-sounding guesses.

The app combines a Next.js interface with a FastAPI data service. It can resolve NBA players, retrieve recent game-log summaries and scoring-leader data, answer supported questions with cited sources, and clearly explain when a question is outside the data it currently has.

## Why StatLine?

NBA data is available everywhere, but most fans still need to know exactly which player, split, stat, or page to search for. StatLine is the conversation layer on top of that data.

Example questions:

- `How has Jayson Tatum played in his last five games?`
- `Compare the recent form of Anthony Edwards and Devin Booker.`
- `Who are the current NBA scoring leaders?`
- `Who has been scoring the most recently?`

The goal is not just to produce an answer. It is to show the evidence behind the answer and avoid pretending to know things the current data does not support.

## Current capabilities

- Natural-language NBA questions through `POST /ask`
- Exact, on-demand retrieval for named players with available NBA regular-season game logs
- Recent five-game player summaries with points, rebounds, assists, field-goal percentage, dates, and game-by-game results
- Historical second-night back-to-back averages for any player in imported regular-season game logs, with the qualifying game IDs
- Current-season scoring-leader recommendations
- Player search and player profile views
- Semantic retrieval over player summaries using Voyage AI embeddings and Supabase Postgres with pgvector
- Cited answer generation using OpenAI
- Source-aware fallback responses when the model cannot produce a properly cited answer
- Explicit refusal for unsupported live-score, injury, and defensive-scheme questions
- Repeatable local answer-quality evaluation cases
- A learning notebook that demonstrates the original three-player RAG pipeline

## Current limitations

StatLine is an actively evolving project. The current release does **not** provide:

- Live scores or in-progress game data
- Injury or medical-status information
- Defensive-scheme or zone-defense analysis
- A complete historical game-level warehouse
- Every possible statistical split
- Automated hosted deployment or scheduled data refreshes

The home-page recommendations are a discovery list based on the latest available regular-season points-per-game leaderboard. They do not limit which named players can be queried: players outside the recommendations can still be searched and loaded when NBA game logs are available.

Recent player answers use the player's latest five games from the latest available season. Always check the dates and citations shown with an answer.

Back-to-back answers use imported game facts from 2013-14 onward and explicitly state their season cutoff.

## Architecture

```mermaid
flowchart LR
    U[User question] --> UI[Next.js frontend]
    UI --> API[FastAPI API]
    API --> R[Question routing]
    R -->|Named player or supported ranking| NBA[NBA game logs and leaderboards]
    R -->|Second-night back-to-back| H[(Private game facts and coverage)]
    R -->|General retrieval question| E[Voyage AI query embedding]
    E --> V[(Supabase Postgres + pgvector)]
    NBA --> S[Structured source summaries]
    H --> UI
    V --> S
    S --> L[OpenAI answer generation]
    L --> C[Citation and answer-quality checks]
    C --> UI
```

### Request flow

1. The frontend sends a question to the FastAPI `/ask` endpoint.
2. The backend checks whether the question matches a supported direct-data path, such as a named-player lookup or scoring-leader query.
3. Named-player and ranking routes fetch NBA data and build source records. The back-to-back route selects imported games and calculates the answer deterministically.
4. Otherwise, the backend embeds the question with Voyage AI and retrieves the closest summaries from `public.nba_chunks` in Supabase.
5. Retrieved sources are passed to OpenAI with instructions to cite them using source IDs.
6. StatLine validates the generated answer. If citations are missing or unsupported statistical prose is detected, it falls back to a source-based response instead of returning an ungrounded answer.
7. The frontend renders the answer and the underlying sources.

### Data and provenance principles

- Numeric claims should come from retrieved NBA data, not model memory.
- The backend owns data retrieval and supported-scope checks.
- The model explains retrieved evidence; it does not write SQL or invent unavailable statistics.
- Unsupported questions should return a clear limitation rather than an unrelated answer.
- Data freshness and coverage are part of the answer context and should be treated explicitly as the project grows.

For the longer-term calendar-aware, game-level query design, see [`docs/STAT_QUERY_ARCHITECTURE.md`](docs/STAT_QUERY_ARCHITECTURE.md).

## Tech stack

### Frontend

- [Next.js](https://nextjs.org/)
- [React](https://react.dev/)
- TypeScript
- CSS

### Backend

- [FastAPI](https://fastapi.tiangolo.com/)
- Python
- [nba_api](https://github.com/swar/nba_api)
- [OpenAI API](https://platform.openai.com/)
- [Voyage AI](https://www.voyageai.com/) embeddings
- [PostgreSQL](https://www.postgresql.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Supabase](https://supabase.com/) database hosting

## Run locally

### Prerequisites

- Python 3.11+ recommended
- Node.js and npm
- A Supabase Postgres database with the `public.nba_chunks` table and pgvector enabled
- API keys for OpenAI and Voyage AI

### 1. Clone the repository

```bash
git clone https://github.com/yomnegede/StatLine.git
cd StatLine
```

### 2. Create the Python environment

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
```

### 3. Configure the backend

```bash
cp .env.example .env
```

Set the following values in `.env`:

```dotenv
OPENAI_API_KEY=your_openai_api_key
VOYAGE_API_KEY=your_voyage_api_key
SUPABASE_DB_URL=postgresql://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:5432/postgres
```

Use Supabase's **Session pooler** connection string when working from an IPv4-only network. Never commit `.env` or expose these keys in the frontend.

### 4. Configure the frontend

The frontend defaults to `http://localhost:8000` for the API. To override it:

```bash
cp frontend/.env.local.example frontend/.env.local
```

Then set:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 5. Start the API

From the repository root:

```bash
venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- Health check: `http://127.0.0.1:8000/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`

### 6. Start the frontend

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API overview

### `POST /ask`

Ask a natural-language NBA question.

Request:

```json
{
  "question": "How has Jayson Tatum played in his last five games?"
}
```

Response shape:

```json
{
  "answer": "...",
  "sources": [
    {
      "id": "jayson_tatum_last5",
      "player": "Jayson Tatum",
      "content": "...",
      "distance": 0.0
    }
  ],
  "status": "answered",
  "notice": null
}
```

Possible statuses:

- `answered` — a cited answer was generated
- `answer_unavailable` — sources were retrieved, but answer generation was unavailable
- `no_data` — the question was unsupported or no relevant data was available

Second-night back-to-back questions use imported game facts and answer without an OpenAI call. A bare year such as “since 2014” begins January 1, 2014; “since 2014-15” begins with that NBA season.

### `GET /health`

Checks database connectivity and returns the number of stored semantic chunks.

### `GET /players`

Returns the recommended current scoring leaders with season and recent-form data.

### `GET /recommendations`

Returns the recommendation records used by the frontend.

### `GET /player-search?q=<name>`

Searches the NBA player directory.

### `GET /players/{player_id}`

Returns the latest available player snapshot and recent game-log summary.

## Refresh the data

The ingestion command refreshes the semantic index with the latest available regular-season scoring leaders. It automatically selects the current season and can fall back to the previous season when the current season has no games yet.

```bash
venv/bin/python -m backend.ingest
```

Useful options:

```bash
# Preview retrieval and summaries without embeddings or database writes
venv/bin/python -m backend.ingest --dry-run

# Refresh a specific player
venv/bin/python -m backend.ingest --player "Jayson Tatum"

# Refresh multiple players
venv/bin/python -m backend.ingest \
  --player "Jayson Tatum" \
  --player "Devin Booker"

# Use a specific season
venv/bin/python -m backend.ingest --season 2025-26

# Import names from a custom watchlist
venv/bin/python -m backend.ingest --watchlist data/watchlist.json
```

The ingestion process:

1. Selects players from the latest available scoring leaderboard, a supplied watchlist, or explicit `--player` arguments.
2. Fetches NBA regular-season game logs with `nba_api`.
3. Builds a readable summary from the player's most recent five games.
4. Creates document embeddings with Voyage AI.
5. Upserts summaries into `public.nba_chunks` in Supabase.

Because `nba_api` depends on NBA.com endpoints that can change or throttle requests, ingestion uses retries and a delay between players. Treat the data source as external and validate refresh results before relying on them in production.

### Historical game facts

Initialize the private `statline` schema and import regular-season team and player game logs:

```bash
venv/bin/python -m backend.history_import --init-schema --start-season 2013-14
```

The importer validates coverage and replaces each season in one transaction. Before the first completed game of a new season, it skips that empty season. Historical back-to-back answers reject gaps in older seasons. If only the current season is not yet imported, they answer through the latest contiguous loaded season and state that the current season is excluded. This route covers second nights of regular-season back-to-backs only.

## Evaluate answer quality

StatLine includes a small, repeatable evaluation suite under [`evals/`](evals/). It covers player retrieval, comparisons, scoring-leader questions, historical back-to-back splits, citations, and unsupported live or defensive questions.

Start the API, then run:

```bash
venv/bin/python -m evals.run --expected-season 2025-26
```

For a quick targeted run:

```bash
venv/bin/python -m evals.run --ids unlisted_player season_ppg_leader
```

The runner writes detailed JSON reports under `evals/runs/` and checks that:

- Expected players reach retrieval
- Citation IDs refer to returned sources
- Direct-average questions include the sourced value
- Unsupported questions decline to guess
- Season expectations do not silently fall back to stale data

Automated checks are necessary but not sufficient. Review each report manually for factuality, relevance, scope honesty, and whether every numeric claim is actually supported by the cited source. See [`evals/README.md`](evals/README.md) for the review rubric.

## Verify changes

Run the backend tests and frontend checks before opening a pull request:

```bash
venv/bin/python -m unittest discover -s tests -v
cd frontend
npm run typecheck
npm run build
```

## Repository structure

```text
StatLine/
├── backend/
│   ├── main.py              # FastAPI app and API routes
│   ├── nba_data.py          # NBA data access and player snapshots
│   ├── player_data.py       # Player response models
│   ├── ingest.py            # NBA data ingestion and pgvector upserts
│   ├── history.py           # Deterministic back-to-back query
│   ├── history_import.py    # Historical game-fact import
│   └── answer_quality.py    # Citation and fallback validation
├── frontend/
│   ├── app/                 # Next.js routes and page entry points
│   └── components/          # Reusable UI components
├── data/
│   └── watchlist.json       # Optional manual ingestion list
├── db/
│   └── statline_history.sql # Private game-fact schema
├── docs/
│   └── STAT_QUERY_ARCHITECTURE.md
├── evals/
│   ├── cases.json           # Evaluation questions and expectations
│   ├── run.py               # Local evaluation runner
│   └── README.md             # Evaluation rubric
├── tests/                   # Backend tests
├── utils/
│   ├── llm_client.py        # OpenAI answer generation
│   └── retrieval.py         # Retrieval filtering and source selection
├── nba_rag_starter.ipynb    # Original three-player RAG learning notebook
├── requirements.txt
└── .env.example
```

## Roadmap

The near-term direction is to move from short player summaries toward an exact, game-level query layer:

- Store versioned games, player box-score facts, calendar events, and coverage state in Postgres
- Use typed query plans for dates, seasons, opponents, last-N games, rankings, and NBA Cup/event filters
- Calculate numerical results deterministically in application code
- Return the exact games, denominator, formula, source, and as-of time behind each result
- Keep document retrieval for explanations and basketball terminology rather than using embeddings as the source of numerical truth
- Add broader evaluation fixtures for coverage failures, event boundaries, and source outages

Longer-term ideas such as a Reddit digest, a full admin dashboard, waiver-wire recommendations, trade evaluation, and multi-sport support are intentionally backlogged until the core question-answering experience is reliable.

## Design principles

1. **Ground answers in data.** Retrieval is only useful when the retrieved evidence supports the claim.
2. **Prefer deterministic calculations.** The model should not be responsible for arithmetic or selecting hidden rows.
3. **Be honest about coverage.** A clear “not available” is better than a confident hallucination.
4. **Show the evidence.** Users should be able to inspect the source behind an answer.
5. **Keep the system understandable.** This is a learning project, so readable code and explicit data flow matter more than clever abstractions.
6. **Ship the smallest useful product first.** Core NBA questions come before extra features.

## Contributing

This is currently a personal project, but feedback and focused contributions are welcome. Before submitting a change:

1. Keep changes scoped to a clear user or data-quality problem.
2. Add or update an evaluation case when changing retrieval or answer behavior.
3. Run the backend tests, frontend typecheck, and production build.
4. Do not commit API keys, local environment files, generated reports, or secrets.

## License

No license has been selected yet. Until a license is added, the repository should not be treated as granting permission to reuse, modify, or redistribute the code.

## Author

Built by [Yom Negede](https://github.com/yomnegede).

- Georgia Tech CS student
- Interested in reliable AI systems, full-stack products, and developer-facing infrastructure

If you find StatLine useful or have an NBA question the app should support, open an issue with the question and the evidence you would expect to see in the answer.
