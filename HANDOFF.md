# StatLine project handoff

## Current state

- Local FastAPI `/ask` and `/health` endpoints are working with the Next.js page.
- `backend/ingest.py` refreshes the 16 players in `data/watchlist.json` and upserts their latest five regular-season games.
- The data is stored in `public.nba_chunks` on Supabase Postgres with pgvector. Row level security is enabled and there is no public Data API policy.
- The API uses Voyage AI for query embeddings and OpenAI for cited answers. Keys stay in the ignored local `.env` file.
- A live comparison across the watchlist returned the player with the highest five-game scoring average and a matching source citation.
- The app is a local watchlist prototype. Deployment, larger coverage, and automated refresh scheduling remain open.

## Run and refresh

Follow `README.md` for setup, local server commands, testing, and data refresh.
The notebook remains a three-player learning example. Use `venv/bin/python -m backend.ingest` for the app's full watchlist.
