# StatLine

An NBA RAG (retrieval-augmented generation) app — ask natural-language questions about NBA players and get answers grounded in real stats, not hallucinated.

**Example queries:**
- "Who should I start this week between Ant Edwards and Devin Booker?"
- "What does Tatum do against zone defense?"
- "Who's been the most efficient scorer in the last 30 days?"

## Stack

- Frontend: Next.js
- Backend: Python, FastAPI
- Vector DB: Supabase (pgvector)
- RAG framework: LangChain
- LLM: Anthropic Claude API
- Embeddings: Voyage AI
- NBA data: nba_api / BallDontLie
- Deployment: Vercel (frontend) + Railway/Render (backend)

## Status

In development. Target launch: August 1, 2026.

See `ROADMAP.md` for the build plan and `nba_rag_starter.ipynb` for the RAG pipeline prototype.

## Setup

Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY`
- `SUPABASE_DB_URL`
