# NBA RAG App — Roadmap to Aug 1, 2026

26 days from today (Jul 6) to launch. Plan is built around the existing build order — don't skip ahead. Each week ends with a working artifact, not just progress.

## Week 1: Jul 6 – Jul 12 — RAG pipeline in a notebook

Goal: end-to-end RAG working in Jupyter, ugly is fine. By Sunday you should be able to ask "who should I start, Tatum or Booker?" and get a grounded answer with a citation.

- [ ] Pull game logs / season averages for a handful of players (nba_api or BallDontLie)
- [ ] Chunk by player + time window (e.g. "Tatum, last 14 days")
- [ ] Embed chunks with Voyage AI
- [ ] Store + retrieve from Supabase pgvector (start with pure semantic search — add keyword hybrid later if retrieval quality is weak)
- [ ] Send retrieved chunks to Claude, generate a cited answer
- [ ] Manually test 5-10 example questions, note where retrieval or answers go wrong

Don't touch FastAPI or Next.js this week even if the notebook code is messy.

## Week 2: Jul 13 – Jul 19 — FastAPI + Next.js, connected

Goal: the notebook logic is wrapped in an API and has a UI in front of it, running locally.

- [ ] Move ingestion/chunking/embedding into a FastAPI ingestion script (can be a one-off script, doesn't need to be an endpoint)
- [ ] Build a `/query` FastAPI endpoint that does retrieval + generation
- [ ] Basic Next.js chat page that calls `/query` and renders the answer + citations
- [ ] This is also the point to introduce LangChain if it's simplifying things — don't force it in if raw code is clearer

## Week 3: Jul 20 – Jul 26 — Deploy + real users

Goal: live URL, at least 5 real people have used it and given feedback.

- [ ] Deploy FastAPI backend (Railway or Render)
- [ ] Deploy Next.js frontend (Vercel)
- [ ] Smoke test in production with real questions
- [ ] Get 5 real users (start with people who'd actually use it — r/fantasybasketball, friends in leagues)
- [ ] Collect feedback, fix the most obvious breakage

Resist scope creep here — trade analyzer, waiver wire, multi-sport are backlogged for a reason.

## Jul 27 – Aug 1 — Buffer, polish, resume-ready

Goal: nothing new, just make what exists solid and presentable.

- [ ] Fix bugs surfaced by real users
- [ ] Minimal `/admin` route: password gate + a simple view of usage/cost so far (skip the full dashboard — timeline, decision log, Reddit digest stay backlogged)
- [ ] Write the resume/LinkedIn blurb and a short writeup of the technical decisions (chunking strategy, hybrid retrieval, eval approach) — this is the interview-talking-point payoff
- [ ] If there's slack time: light RAGAS eval on your test question set, only if core product is solid first

## Decision log

(Add entries here as you make calls — useful for interviews later.)

| Date | Decision | Why |
|------|----------|-----|
| 2026-07-06 | Voyage AI over OpenAI for embeddings | Anthropic's recommended partner, ~10% better retrieval benchmarks, Claude has no native embeddings endpoint |
| 2026-07-06 | Hybrid search (semantic + keyword) planned for stats queries | Pure semantic search under-performs on stat-heavy queries with specific player names/terms |

## Notes

- Pace: ~3-4 hrs weeknights + free weekends. This plan assumes that, not a death march.
- If Week 1 slips past Sunday, cut scope in Week 3 (fewer users, simpler admin) before cutting Week 1 — a working pipeline is the foundation everything else depends on.
