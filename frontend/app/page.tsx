"use client";

import { FormEvent, useEffect, useState } from "react";

type Source = {
  id: string;
  player: string;
  content: string;
  distance: number;
};

type AskResponse = {
  answer: string | null;
  sources: Source[];
  status: "answered" | "answer_unavailable" | "no_data";
  notice: string | null;
};

type Health = { status: string; chunks: number };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const EXAMPLES = [
  "How have Tatum and Booker played in their last five games?",
  "What were Anthony Edwards' recent scoring numbers?",
  "Who averaged the most points in this watchlist?",
];

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data: Health | null) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (question.trim().length < 3) return;

    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "The API could not answer right now.");
      }
      setResult((await response.json()) as AskResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the API.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="brand"><span className="brand-mark">S</span><span>StatLine</span></div>
        <div className="header-meta">
          <span className="season-tag">Loaded game logs</span>
          <span className={`health-tag ${health ? "online" : "offline"}`}>
            <span className="health-dot" />
            {health ? `${health.chunks} player sources live` : "API not connected"}
          </span>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow"><span className="eyebrow-line" /> NBA STATS, WITH RECEIPTS</div>
          <h1>Ask the game.<br /><em>See the numbers.</em></h1>
          <p>Natural language answers grounded in the latest available game logs. Ask about the players in the current watchlist.</p>
        </section>

        <section className="query-panel" aria-label="Ask a stats question">
          <form onSubmit={ask}>
            <label htmlFor="question">YOUR QUESTION</label>
            <textarea
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="How have Tatum and Booker played lately?"
              maxLength={500}
              rows={3}
            />
            <div className="query-actions">
              <span>Grounded in the latest loaded player summaries</span>
              <button type="submit" disabled={loading || question.trim().length < 3}>
                {loading ? "Checking the tape…" : "Get the answer"}<span aria-hidden="true">↗</span>
              </button>
            </div>
          </form>
        </section>

        <section className="examples" aria-label="Example questions">
          <span>TRY A QUESTION</span>
          <div className="example-list">
            {EXAMPLES.map((example) => (
              <button key={example} type="button" onClick={() => setQuestion(example)}>{example}<span aria-hidden="true">↗</span></button>
            ))}
          </div>
        </section>

        {error && <div className="error-box" role="alert">{error}</div>}

        {result && (
          <section className="result-section" aria-live="polite">
            <div className="section-heading"><span>01 / ANSWER</span><span>{result.status === "answered" ? "GROUNDED RESPONSE" : "SOURCE DATA"}</span></div>
            <div className="answer-card">
              {result.answer ? <div className="answer-text">{result.answer}</div> : <p className="notice">{result.notice}</p>}
            </div>
            <div className="section-heading sources-heading"><span>02 / SOURCES</span><span>{result.sources.length} RETRIEVED</span></div>
            <div className="sources-grid">
              {result.sources.map((source, index) => (
                <article className="source-card" key={source.id}>
                  <div className="source-top"><span>SOURCE {String(index + 1).padStart(2, "0")}</span><span>{source.player}</span></div>
                  <p>{source.content}</p>
                  <code>[Source: {source.id}]</code>
                </article>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer><span>STATLINE / BUILT ON REAL GAME LOGS</span><span>Early prototype · latest loaded games</span></footer>
    </div>
  );
}
