# StatLine

StatLine answers NBA stats questions using game logs as evidence. FastAPI uses
NBA regular-season game logs for named-player questions, including players
outside the recommended list, and the NBA scoring leaderboard for season PPG
questions. OpenAI turns those sources into cited answers. The existing Voyage
AI + Supabase pgvector path remains available for semantic retrieval. The
Next.js experience lets fans inspect citations, search NBA players, browse
recommended scorers, open player profiles, and compare recent performances.

## Current scope

The home page recommends the top 16 players on the latest available NBA
regular-season points-per-game leaderboard. This is a discovery list, not a
restriction on questions: named players with NBA regular-season game logs can
be looked up on demand, including former players. Recent profiles and answers
use each player's latest five games from their latest available season. The
app does not have live scores, injuries, defensive-scheme data, or every
possible split. The original August 1, 2026 target in `ROADMAP.md` is
historical.

## Set up

1. Create the Python environment and install dependencies:

   ```bash
   python3 -m venv venv
   venv/bin/python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set `VOYAGE_API_KEY`, `SUPABASE_DB_URL`,
   and `OPENAI_API_KEY`. Use Supabase's **Session pooler** URL on IPv4-only
   networks. Keep `.env` local and do not place these keys in the frontend.

3. Install the frontend dependencies:

   ```bash
   cd frontend
   npm ci
   ```

4. Start the API from the repository root:

   ```bash
   venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. In another terminal, start the page:

   ```bash
   cd frontend
   npm run dev
   ```

Open [http://localhost:3000](http://localhost:3000). The API health check is at
`http://127.0.0.1:8000/health`. The page calls the API at `http://localhost:8000`
by default; set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if needed.
The read-only `GET /players` endpoint serves recommended top scorers with
season PPG and recent form. `GET /player-search?q=...` searches the NBA player
directory and `GET /players/{id}` retrieves one player's game log. No database
migration is needed.

## Refresh data

To refresh the semantic index with the latest season PPG leaders, run this
from the repository root:

```bash
venv/bin/python -m backend.ingest
```

The command selects the current NBA season, falls back to the prior season if
there are no games yet, and imports the top 16 players by season PPG. Each
summary states its season and game dates. It updates existing rows by ID and
reports failures. To preview without embeddings or database writes, add
`--dry-run`. To refresh a single player, use `--player "Jayson Tatum"`.
To override the recommendations for a manual import, use
`--watchlist data/watchlist.json`; to select a season, use `--season 2025-26`.

`nba_rag_starter.ipynb` remains a three-player learning notebook. The one-time table SQL is in the
notebook, and the `public.nba_chunks` table already exists in the connected
Supabase project.

## Evaluate answer quality

Start the API, then run `venv/bin/python -m evals.run --expected-season 2025-26`
(replace the season as play advances). The runner checks
player retrieval, citation IDs, direct averages, season leaders, and honest
responses to unsupported questions. It writes a local JSON report under
`evals/runs/`. Review every numeric claim against its cited source and use the
human-review rubric in `evals/README.md`; automated checks alone cannot prove
that an explanation is correct.

## Verify

```bash
venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run typecheck && npm run build
```
