# StatLine

StatLine answers NBA stats questions using game logs as evidence. A repeatable
ingestion command fetches player game logs through `nba_api`, summarizes each
player's latest five games, embeds the summaries with Voyage AI, and stores
them in Supabase Postgres with pgvector. FastAPI retrieves relevant summaries
and asks OpenAI to answer with source IDs. A Next.js page displays the answer
and its underlying stats.

## Current scope

The local app has been tested end to end with the 16 players in
`data/watchlist.json`. These are the latest available 2025–26 regular-season
game logs as of the September 2026 refresh. The app is still a watchlist
prototype, not a complete NBA data service or a live game feed. The original
August 1, 2026 target in `ROADMAP.md` is historical.

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

## Refresh data

Edit `data/watchlist.json`, then run this from the repository root:

```bash
venv/bin/python -m backend.ingest
```

The command selects the current NBA season and falls back to the previous
season for a player with no games yet. Each summary states its season and game
dates. It updates existing player rows by ID, and reports any players it
could not refresh. To preview the summaries without embeddings or database
writes, add `--dry-run`. To refresh a single player, use
`--player "Jayson Tatum"`; to select a season, use `--season 2025-26`.

`nba_rag_starter.ipynb` remains a three-player learning notebook. Use the CLI
above to refresh the app's full watchlist. The one-time table SQL is in the
notebook, and the `public.nba_chunks` table already exists in the connected
Supabase project.

## Verify

```bash
venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run typecheck && npm run build
```
