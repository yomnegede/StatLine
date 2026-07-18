# NBA RAG App — Project Context for Claude Code

## Who I am
- Yom Negede, CS student at Georgia Tech (graduating May 2027)
- Current SWE intern at John Deere (TypeScript, React, Java Spring Boot)
- Previous intern at Sleeper (React, Firebase, Cloudflare) — external webpage, not core app
- Targeting FAANG SWE roles for summer 2027 full-time
- This project is both something I want real users on AND a strong interview talking point

## What we're building
An NBA RAG (Retrieval-Augmented Generation) application that lets users ask natural language questions about NBA players and get answers grounded in real stats — not hallucinated, actually retrieved.

**Core use case:** Fantasy basketball players and NBA fans ask questions like:
- "Who should I start this week between Ant Edwards and Devin Booker?"
- "What does Tatum do against zone defense?"
- "Who's been the most efficient scorer in the last 30 days?"

The app retrieves real NBA data and uses Claude to reason over it and return a grounded, cited answer.

## Hard deadline
**August 1, 2025** — needs to be live with real users. FAANG applications open early August and this needs to be on the resume and talkable by then.

## Stack decisions (already made, don't second-guess these)
- **Frontend:** Next.js (Yom knows React well)
- **Backend:** Python FastAPI for the RAG pipeline
- **Vector DB:** Supabase pgvector (free tier, Yom knows PostgreSQL)
- **RAG framework:** LangChain (learning from scratch, prioritize clear patterns)
- **LLM:** Anthropic Claude API (claude-sonnet-4-6) — already on resume
- **NBA Data:** BallDontLie API or NBA API (free)
- **Auth:** Simple password protection for /admin route
- **Deployment:** Vercel (frontend) + Railway or Render (FastAPI backend)

## App structure
```
/                  → Main chat interface for users
/admin             → Password-protected dashboard (admin only)
```

## Admin dashboard (to build after core app works)
A `/admin` route visible only to Yom. Will eventually show:
- Project timeline + August 1st countdown
- API cost/spend tracker
- Reddit research (r/fantasybasketball pain points)
- Decision log
- User feedback
- To-do list

## RAG architecture plan
1. **Data ingestion** — pull player stats, recent game logs, injury reports from NBA APIs
2. **Chunking** — split by player + time window (e.g. "Ant Edwards last 14 days")
3. **Embedding** — use Anthropic or OpenAI embeddings, store in Supabase pgvector
4. **Retrieval** — hybrid search (semantic + keyword) for different query types
5. **Generation** — Claude reasons over retrieved chunks, cites sources in response

## Build order (don't skip ahead)
1. Get RAG pipeline working in a Jupyter notebook — ugly is fine
2. Wrap it in a FastAPI endpoint
3. Build the Next.js frontend and connect it
4. Polish UI and fix what's broken
5. Get 5 real users, iterate
6. Add /admin dashboard
7. Weekly Reddit email digest (backlogged)

## What makes this technically interesting for interviews
- Multi-source retrieval (structured stats + unstructured text)
- Chunking and embedding strategy decisions
- Hybrid search implementation
- Evaluation framework to show it actually works
- Real users with real usage data

## Competitive landscape
- **Databallr** — has all the data but requires you to know what to look for. We're the conversation layer on top of that data, not a competitor.
- No well-executed natural language NBA analytics product exists for normal fans.

## Yom's coding background
Strong in: React, TypeScript, JavaScript, PostgreSQL, Python
Learning on this project: RAG, LangChain, vector databases, embeddings, FastAPI
Don't over-engineer — Yom is learning RAG from scratch, prioritize clear readable patterns over clever abstractions.

## Preferences
- Keep code readable and well-commented — this is a learning project
- Explain RAG concepts when introducing new patterns
- When stuck between two approaches, recommend the simpler one given the deadline
- Don't suggest adding features unless core use case is working first

## Key context for conversations
- Yom has ~3-4 hours on weeknights and free weekends (is in Chicago for internship)
- Wants to enjoy the summer — not a death march, sustainable pace
- First RAG project — learning this stack from scratch
- Real users matter more than perfect code

## Backlog (don't build yet)
- [ ] Weekly Reddit digest email — pulls top r/fantasybasketball posts, summarizes with Claude, emails Yom every Monday
- [ ] Admin dashboard full build
- [ ] Multi-sport expansion
- [ ] Trade evaluation feature
- [ ] Waiver wire recommendations
