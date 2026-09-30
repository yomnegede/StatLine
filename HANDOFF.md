# StatLine project handoff

## Current state

- Local FastAPI `/ask` and `/health` endpoints are working with the Next.js page.
- `backend/ingest.py` refreshes the latest season's top 16 PPG leaders by default. The manual `data/watchlist.json` file is now an optional import override.
- The data is stored in `public.nba_chunks` on Supabase Postgres with pgvector. Row level security is enabled and there is no public Data API policy.
- The API uses Voyage AI for query embeddings and OpenAI for cited answers. Keys stay in the ignored local `.env` file.
- Named-player questions use NBA regular-season game logs on demand, including players outside the recommendations. The recommendation list comes from the latest available season PPG leaderboard.
- `evals/` contains repeatable answer-quality cases and a human-review rubric.
- The app remains local. Deployment and automated refresh scheduling remain open.

## Run and refresh

Follow `README.md` for setup, local server commands, testing, and data refresh.
The notebook remains a three-player learning example. Use `venv/bin/python -m backend.ingest` to refresh the semantic index of recommended scorers.
