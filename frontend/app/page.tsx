"use client";

import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AskResponse,
  ComparisonMetric,
  Icon,
  metricLabels,
  Metric,
  Player,
  PlayerOption,
  PlayerAvatar,
  SectionLabel,
  Source,
  StatBlock,
  TrendChart,
} from "../components/statline";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const examples = [
  "Who leads the NBA in points per game this season?",
  "Compare Jaylen Brown and Devin Booker recently.",
  "How has Anthony Edwards played in his last five games?",
];
const loadingSteps = [
  "Searching player data",
  "Reading recent game logs",
  "Putting the numbers together",
];
type Sort =
  | "season_ppg"
  | "points"
  | "rebounds"
  | "assists"
  | "field_goal_pct"
  | "name";

function QueryInput({
  question,
  setQuestion,
  onSubmit,
  loading,
  inputRef,
}: {
  question: string;
  setQuestion: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  loading: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }
  return (
    <form className="query-box" onSubmit={onSubmit}>
      <label htmlFor="question">
        <Icon name="spark" size={16} /> ASK STATLINE
      </label>
      <textarea
        ref={inputRef}
        id="question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={onKeyDown}
        maxLength={500}
        rows={2}
        placeholder="Ask about any NBA player or recent performance…"
      />
      <div className="query-bottom">
        <span>
          NBA regular-season data · Enter to ask · Shift + Enter for a new line
        </span>
        <button
          className="primary-button"
          type="submit"
          disabled={loading || question.trim().length < 3}
        >
          {loading ? "Analyzing…" : "Ask StatLine"}
          <Icon name="arrow" size={17} />
        </button>
      </div>
    </form>
  );
}

function CitationText({
  text,
  sources,
  onCite,
}: {
  text: string;
  sources: Source[];
  onCite: (id: string) => void;
}) {
  return (
    <>
      {text.split(/(\[Source: [^\]]+\])/g).map((part, index) => {
        const match = part.match(/^\[Source: ([^\]]+)\]$/);
        if (!match) return <span key={index}>{part}</span>;
        const sourceIndex = sources.findIndex(
          (source) => source.id === match[1],
        );
        return sourceIndex < 0 ? (
          <span key={index}>{part}</span>
        ) : (
          <button
            key={index}
            className="citation"
            type="button"
            onClick={() => onCite(match[1])}
            aria-label={`View source ${sourceIndex + 1}, ${sources[sourceIndex].player}`}
          >
            {sourceIndex + 1}
          </button>
        );
      })}
    </>
  );
}

type AnswerStat = Pick<
  Player,
  "id" | "name" | "games_count" | "points" | "rebounds" | "assists"
>;

function statsFromSource(source: Source, players: Player[]): AnswerStat | null {
  const loaded = players.find((player) => player.source_id === source.id);
  if (loaded) return loaded;
  const match = source.content.match(
    /last (\d+) games .*?averaging (\d+(?:\.\d+)?) pts, (\d+(?:\.\d+)?) reb, (\d+(?:\.\d+)?) ast/,
  );
  return match
    ? {
        id: source.id,
        name: source.player,
        games_count: Number(match[1]),
        points: Number(match[2]),
        rebounds: Number(match[3]),
        assists: Number(match[4]),
      }
    : null;
}

function AnswerPanel({
  result,
  players,
  askFollowup,
}: {
  result: AskResponse;
  players: Player[];
  askFollowup: (question: string) => void;
}) {
  const [openSource, setOpenSource] = useState<string | null>(null);
  const citedIds = [
    ...(result.answer?.matchAll(/\[Source: ([^\]]+)\]/g) ?? []),
  ].map((match) => match[1]);
  const citedSources = [...new Set(citedIds)]
    .map((id) => result.sources.find((source) => source.id === id))
    .filter((source): source is Source => Boolean(source));
  const primarySources = citedSources.length
    ? citedSources
    : result.sources.slice(0, 3);
  const otherSources = result.sources.filter(
    (source) => !primarySources.some((primary) => primary.id === source.id),
  );
  const matched = primarySources
    .map((source) => statsFromSource(source, players))
    .filter((player): player is AnswerStat => Boolean(player))
    .slice(0, 3);
  const paragraphs =
    result.answer
      ?.trim()
      .split(/\n\s*\n/)
      .filter(Boolean) ?? [];
  const followups =
    matched.length >= 2
      ? [
          `Compare ${matched[0].name} and ${matched[1].name} as scorers.`,
          `Which recent games stand out for ${matched[0].name}?`,
        ]
      : matched.length === 1
        ? [
            `What were ${matched[0].name}'s best recent games?`,
            `How efficient was ${matched[0].name} recently?`,
          ]
        : [examples[1], examples[2]];
  function showSource(id: string) {
    setOpenSource(id);
    document
      .getElementById("answer-evidence")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return (
    <section
      className="answer-section"
      id="answer"
      aria-live="polite"
      aria-labelledby="answer-heading"
    >
      <SectionLabel
        number="01"
        aside={`${primarySources.length} cited · ${result.sources.length} retrieved`}
      >
        THE ANSWER
      </SectionLabel>
      <div className="answer-layout">
        <div className="answer-main">
          <div className="answer-heading-row">
            <span className="answer-badge">
              <Icon name="spark" size={15} /> STATLINE ANALYSIS
            </span>
            <span className="grounded-note">Grounded in loaded game logs</span>
          </div>
          <h2 id="answer-heading">Here’s what the numbers say.</h2>
          {result.answer ? (
            <div className="answer-copy">
              {paragraphs.map((paragraph, index) => (
                <p className={index === 0 ? "answer-lead" : ""} key={index}>
                  <CitationText
                    text={paragraph}
                    sources={primarySources}
                    onCite={showSource}
                  />
                </p>
              ))}
            </div>
          ) : (
            <p className="answer-lead">
              {result.notice ?? "There are no loaded stats to answer this yet."}
            </p>
          )}
          {matched.length > 0 && (
            <div className="answer-stats">
              <span className="mini-heading">
                FROM THE SOURCE DATA{" "}
                <small>LAST {matched[0].games_count} GAMES</small>
              </span>
              <div className="answer-stat-grid">
                {matched.map((player) => (
                  <div className="answer-player-stat" key={player.id}>
                    <span>{player.name}</span>
                    <div>
                      <strong>{player.points.toFixed(1)}</strong>
                      <small>PTS</small>
                      <strong>{player.rebounds.toFixed(1)}</strong>
                      <small>REB</small>
                      <strong>{player.assists.toFixed(1)}</strong>
                      <small>AST</small>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <aside className="answer-side" id="answer-evidence">
          <div className="aside-heading">
            <span>EVIDENCE</span>
            <span>{primarySources.length} CITED LOGS</span>
          </div>
          <p>Open a source to inspect the game log StatLine used.</p>
          <div className="evidence-list">
            {primarySources.map((source, index) => (
              <div
                className={`evidence-item${openSource === source.id ? " is-open" : ""}`}
                key={source.id}
              >
                <button
                  type="button"
                  onClick={() =>
                    setOpenSource(openSource === source.id ? null : source.id)
                  }
                  aria-expanded={openSource === source.id}
                >
                  <span className="source-number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>{source.player}</span>
                  <Icon name="chevron" size={16} />
                </button>
                {openSource === source.id && (
                  <div className="evidence-body">
                    <p>{source.content}</p>
                    <code>NBA PlayerGameLog · {source.id}</code>
                  </div>
                )}
              </div>
            ))}
          </div>
          {otherSources.length > 0 && (
            <details className="other-sources">
              <summary>{otherSources.length} other retrieved logs</summary>
              <div className="evidence-list">
                {otherSources.map((source) => (
                  <div
                    className={`evidence-item${openSource === source.id ? " is-open" : ""}`}
                    key={source.id}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setOpenSource(
                          openSource === source.id ? null : source.id,
                        )
                      }
                      aria-expanded={openSource === source.id}
                    >
                      <span>{source.player}</span>
                      <Icon name="chevron" size={16} />
                    </button>
                    {openSource === source.id && (
                      <div className="evidence-body">
                        <p>{source.content}</p>
                        <code>NBA PlayerGameLog · {source.id}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}
          {result.sources.length === 0 && <p>No source data is available.</p>}
          <div className="followups">
            <span className="mini-heading">KEEP EXPLORING</span>
            {followups.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => askFollowup(prompt)}
              >
                {prompt}
                <Icon name="arrow" size={15} />
              </button>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function PlayerDrawer({
  player,
  onClose,
  onAsk,
  onCompare,
}: {
  player: Player;
  onClose: () => void;
  onAsk: (question: string) => void;
  onCompare: (player: Player) => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    closeRef.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const focusable = [
          ...(drawerRef.current?.querySelectorAll<HTMLElement>(
            "button, a, input, [tabindex]:not([tabindex='-1'])",
          ) ?? []),
        ];
        if (focusable.length) {
          const first = focusable[0],
            last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
      previousFocus?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        ref={drawerRef}
        className="player-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`${player.name} player details`}
      >
        <div className="drawer-top">
          <span>
            PLAYER PROFILE <small>/ {player.season}</small>
          </span>
          <button
            ref={closeRef}
            className="icon-button"
            type="button"
            onClick={onClose}
            aria-label="Close player details"
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="drawer-identity">
          <PlayerAvatar name={player.name} large />
          <div>
            <span className="eyebrow">RECENT FORM</span>
            <h2>{player.name}</h2>
            <p>
              {player.season} regular season · latest {player.games_count} games
            </p>
          </div>
        </div>
        <div className="drawer-stats">
          <StatBlock label="POINTS / GAME" value={player.points.toFixed(1)} />
          <StatBlock
            label="REBOUNDS / GAME"
            value={player.rebounds.toFixed(1)}
          />
          <StatBlock label="ASSISTS / GAME" value={player.assists.toFixed(1)} />
          <StatBlock
            label="FIELD GOAL"
            value={player.field_goal_pct.toFixed(1)}
            unit="%"
          />
        </div>
        <div className="drawer-section">
          <div className="aside-heading">
            <span>SCORING FORM</span>
            <span>LAST {player.games_count}</span>
          </div>
          <TrendChart
            games={player.games}
            label={`${player.name} recent points`}
          />
        </div>
        <div className="drawer-section">
          <div className="aside-heading">
            <span>GAME LOG</span>
            <span>PTS / REB / AST</span>
          </div>
          <div className="game-log-wrap">
            <table className="game-log">
              <thead>
                <tr>
                  <th scope="col">GAME</th>
                  <th scope="col">PTS</th>
                  <th scope="col">REB</th>
                  <th scope="col">AST</th>
                </tr>
              </thead>
              <tbody>
                {player.games.map((game) => (
                  <tr key={`${game.date}-${game.matchup}`}>
                    <th scope="row">
                      <strong>{game.matchup}</strong>
                      <small>{game.date}</small>
                    </th>
                    <td>{game.points}</td>
                    <td>{game.rebounds}</td>
                    <td>{game.assists}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <button
          className="primary-button drawer-ask"
          type="button"
          onClick={() => {
            onClose();
            window.setTimeout(
              () =>
                onAsk(
                  `How has ${player.name} played over the last five games?`,
                ),
              0,
            );
          }}
        >
          Ask about {player.name.split(" ").at(-1)}{" "}
          <Icon name="arrow" size={16} />
        </button>
        <button
          className="drawer-compare"
          type="button"
          onClick={() => onCompare(player)}
        >
          Add to comparison <Icon name="plus" size={16} />
        </button>
        <p className="source-footnote">
          Source: NBA PlayerGameLog · {player.first_game}–{player.last_game}
        </p>
      </aside>
    </div>
  );
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [otherPlayers, setOtherPlayers] = useState<Player[]>([]);
  const [dataState, setDataState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [search, setSearch] = useState("");
  const [searchOptions, setSearchOptions] = useState<PlayerOption[]>([]);
  const [searchState, setSearchState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [sort, setSort] = useState<Sort>("season_ppg");
  const [selected, setSelected] = useState<string[]>([]);
  const [detail, setDetail] = useState<Player | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const questionRef = useRef(question);
  questionRef.current = question;
  useEffect(() => {
    fetch(`${API_URL}/players`)
      .then((response) => {
        if (!response.ok) throw new Error("Player data unavailable");
        return response.json();
      })
      .then((data: Player[]) => {
        setPlayers(data);
        setDataState("ready");
      })
      .catch(() => setDataState("error"));
    const onKey = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(
      () =>
        setLoadingStep((step) => Math.min(step + 1, loadingSteps.length - 1)),
      2200,
    );
    return () => window.clearInterval(timer);
  }, [loading]);
  useEffect(() => {
    if (search.trim().length < 2) {
      setSearchOptions([]);
      setSearchState("idle");
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`${API_URL}/player-search?q=${encodeURIComponent(search.trim())}`, {
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) throw new Error("Search unavailable");
          return response.json();
        })
        .then((options: PlayerOption[]) => {
          setSearchOptions(options);
          setSearchState("ready");
        })
        .catch(() => {
          if (!controller.signal.aborted) setSearchState("error");
        });
    }, 180);
    setSearchState("loading");
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [search]);
  async function openPlayer(option: PlayerOption) {
    setSearch("");
    try {
      const response = await fetch(`${API_URL}/players/${option.id}`);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Player data unavailable");
      }
      const player = (await response.json()) as Player;
      setOtherPlayers((current) =>
        current.some((item) => item.id === player.id)
          ? current
          : [...current, player],
      );
      setDetail(player);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Player data unavailable",
      );
    }
  }
  async function ask(event?: FormEvent<HTMLFormElement>, prompt?: string) {
    event?.preventDefault();
    const text = (prompt ?? questionRef.current).trim();
    if (text.length < 3 || loading) return;
    setQuestion(text);
    setLoading(true);
    setLoadingStep(0);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "StatLine could not answer right now.");
      }
      setResult((await response.json()) as AskResponse);
      window.setTimeout(
        () =>
          document
            .getElementById("answer")
            ?.scrollIntoView({ behavior: "smooth", block: "start" }),
        80,
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not reach the API.",
      );
    } finally {
      setLoading(false);
    }
  }
  function usePrompt(prompt: string) {
    setQuestion(prompt);
    inputRef.current?.focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  const closeDetail = useCallback(() => setDetail(null), []);
  function toggleCompare(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : current.length < 2
          ? [...current, id]
          : [current[1], id],
    );
  }
  const visiblePlayers = useMemo(
    () =>
      [...players].sort((a, b) =>
        sort === "name"
          ? a.name.localeCompare(b.name)
          : (b[sort] ?? -1) - (a[sort] ?? -1),
      ),
    [players, sort],
  );
  const leaders = useMemo(
    () =>
      [...players]
        .sort((a, b) => (b.season_ppg ?? 0) - (a.season_ppg ?? 0))
        .slice(0, 3),
    [players],
  );
  const compared = selected
    .map((id) =>
      [...players, ...otherPlayers].find((player) => player.id === id),
    )
    .filter((player): player is Player => Boolean(player));
  const season = players[0]?.season ?? "NBA";
  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="header-inner">
          <a href="#top" className="brand" aria-label="StatLine home">
            <span className="brand-symbol">
              <span />
              <span />
              <span />
            </span>
            <span>
              StatLine<span className="brand-period">.</span>
            </span>
          </a>
          <nav aria-label="Main navigation">
            <a href="#top">Ask</a>
            <a href="#players">Players</a>
            <a href="#compare">Compare</a>
          </nav>
          <div className="header-right">
            <span className="season-pill">{season} SEASON</span>
            <span
              className={`status-dot ${dataState === "ready" ? "active" : ""}`}
            />
            <span className="header-status">
              {dataState === "ready"
                ? "DATA CONNECTED"
                : dataState === "loading"
                  ? "CONNECTING"
                  : "DATA OFFLINE"}
            </span>
          </div>
        </div>
      </header>
      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="eyebrow-dash" /> THE NBA, IN CONTEXT
            </div>
            <h1>
              The numbers.
              <br />
              <span>The whole story.</span>
            </h1>
            <p>
              Ask about any NBA player. Get clear answers backed by game logs,
              then go straight to the source.
            </p>
          </div>
          <div className="hero-index" aria-hidden="true">
            <span>SL / 01</span>
            <div className="index-rule" />
            <span>
              ASK BETTER
              <br />
              KNOW MORE
            </span>
          </div>
        </section>
        <section className="ask-area" aria-label="Ask StatLine">
          <QueryInput
            question={question}
            setQuestion={setQuestion}
            onSubmit={ask}
            loading={loading}
            inputRef={inputRef}
          />
          <div className="suggestions">
            <span>START HERE</span>
            <div>
              {examples.map((example) => (
                <button
                  type="button"
                  key={example}
                  onClick={() => usePrompt(example)}
                >
                  {example}
                  <Icon name="arrow" size={14} />
                </button>
              ))}
            </div>
          </div>
        </section>
        {loading && (
          <div className="loading-state" role="status" aria-live="polite">
            <div className="loading-track">
              <span />
            </div>
            <div>
              <Icon name="spark" size={17} />
              <strong>{loadingSteps[loadingStep]}…</strong>
              <span>
                Checking NBA game logs and preparing a sourced answer.
              </span>
            </div>
          </div>
        )}
        {error && (
          <div className="error-box" role="alert">
            <strong>Something interrupted the play.</strong>
            <span>{error}</span>
            <button type="button" onClick={() => ask()}>
              Try again <Icon name="arrow" size={14} />
            </button>
          </div>
        )}
        {result && (
          <AnswerPanel
            key={question}
            result={result}
            players={[...players, ...otherPlayers]}
            askFollowup={usePrompt}
          />
        )}
        <section className="pulse-section" aria-labelledby="pulse-title">
          <SectionLabel
            number={result ? "02" : "01"}
            aside={
              players.length
                ? `${season} REGULAR SEASON · NBA LEAGUELEADERS`
                : "LOADING SCORING DATA"
            }
          >
            SCORING LEADERS
          </SectionLabel>
          <div className="pulse-layout">
            <div className="pulse-intro">
              <span className="eyebrow">A QUICK READ</span>
              <h2 id="pulse-title">
                The league’s,
                <br />
                <em>top scorers.</em>
              </h2>
              <p>
                Recommended players ranked by {season} regular-season points per
                game. Open a player to see their last five games.
              </p>
              <a href="#players" className="text-link">
                Explore the leaders <Icon name="arrow" size={17} />
              </a>
            </div>
            <div className="leaders-list">
              {dataState === "loading"
                ? [1, 2, 3].map((number) => (
                    <div className="leader-skeleton" key={number} />
                  ))
                : leaders.map((player, index) => (
                    <button
                      className="leader-row"
                      type="button"
                      key={player.id}
                      onClick={() => setDetail(player)}
                    >
                      <span className="leader-rank">
                        {String(player.rank ?? index + 1).padStart(2, "0")}
                      </span>
                      <PlayerAvatar name={player.name} />
                      <span className="leader-identity">
                        <strong>{player.name}</strong>
                        <small>{player.season_games} SEASON GAMES</small>
                      </span>
                      <span className="leader-points">
                        <strong>{player.season_ppg?.toFixed(1)}</strong>
                        <small>SEASON PPG</small>
                      </span>
                      <Icon name="arrow" size={17} />
                    </button>
                  ))}
              {dataState === "error" && (
                <p className="data-unavailable">
                  Player data is unavailable. The Ask feature may still work if
                  the API reconnects.
                </p>
              )}
              {dataState === "ready" && players.length === 0 && (
                <p className="data-unavailable">
                  No player summaries are loaded yet.
                </p>
              )}
            </div>
          </div>
        </section>
        <section
          className="players-section"
          id="players"
          aria-labelledby="players-title"
        >
          <SectionLabel
            number={result ? "03" : "02"}
            aside={`${players.length} RECOMMENDED PLAYERS`}
          >
            PLAYER DISCOVERY
          </SectionLabel>
          <div className="section-title-row">
            <div>
              <span className="eyebrow">RECOMMENDED BY SEASON PPG</span>
              <h2 id="players-title">Explore the players.</h2>
              <p>
                The scoring leaders are a starting point. Search for any NBA
                player to open their recent game log.
              </p>
            </div>
            <div className="player-search-wrap">
              <label className="player-search">
                <Icon name="search" size={18} />
                <span className="sr-only">Search all NBA players</span>
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search any player"
                  autoComplete="off"
                />
              </label>
              {search.trim().length >= 2 && (
                <div
                  className="search-results"
                  role="region"
                  aria-label="Player search results"
                >
                  {searchState === "loading" && <p>Searching NBA players…</p>}
                  {searchState === "error" && (
                    <p>Player search is unavailable.</p>
                  )}
                  {searchState === "ready" && searchOptions.length === 0 && (
                    <p>No NBA players found.</p>
                  )}
                  {searchOptions.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => openPlayer(option)}
                    >
                      <PlayerAvatar name={option.name} />
                      <span>
                        {option.name}
                        <small>
                          {option.active ? "ACTIVE PLAYER" : "FORMER PLAYER"}
                        </small>
                      </span>
                      <Icon name="arrow" size={15} />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="table-wrap">
            <table className="players-table">
              <thead>
                <tr>
                  <th scope="col">
                    <button type="button" onClick={() => setSort("name")}>
                      PLAYER {sort === "name" && "↑"}
                    </button>
                  </th>
                  <th scope="col">
                    <button type="button" onClick={() => setSort("season_ppg")}>
                      SEASON PPG {sort === "season_ppg" && "↓"}
                    </button>
                  </th>
                  {(
                    [
                      "points",
                      "rebounds",
                      "assists",
                      "field_goal_pct",
                    ] as Metric[]
                  ).map((metric) => (
                    <th key={metric} scope="col">
                      <button type="button" onClick={() => setSort(metric)}>
                        {metric === "points"
                          ? "LAST 5 PTS"
                          : metricLabels[metric]}{" "}
                        {sort === metric && "↓"}
                      </button>
                    </th>
                  ))}
                  <th scope="col" className="compare-header">
                    COMPARE
                  </th>
                </tr>
              </thead>
              <tbody>
                {visiblePlayers.map((player) => (
                  <tr key={player.id}>
                    <th scope="row">
                      <button
                        className="table-player"
                        type="button"
                        onClick={() => setDetail(player)}
                      >
                        <PlayerAvatar name={player.name} />
                        <span>
                          <strong>{player.name}</strong>
                          <small>
                            #{player.rank} · {player.season_games} GP
                          </small>
                        </span>
                      </button>
                    </th>
                    <td className="emphasis">
                      {player.season_ppg?.toFixed(1)}
                    </td>
                    <td>{player.points.toFixed(1)}</td>
                    <td>{player.rebounds.toFixed(1)}</td>
                    <td>{player.assists.toFixed(1)}</td>
                    <td>{player.field_goal_pct.toFixed(1)}%</td>
                    <td>
                      <button
                        className={`compare-add${selected.includes(player.id) ? " selected" : ""}`}
                        type="button"
                        aria-label={`${selected.includes(player.id) ? "Remove" : "Add"} ${player.name} ${selected.includes(player.id) ? "from" : "to"} comparison`}
                        aria-pressed={selected.includes(player.id)}
                        onClick={() => toggleCompare(player.id)}
                      >
                        {selected.includes(player.id) ? (
                          <Icon name="close" size={16} />
                        ) : (
                          <Icon name="plus" size={16} />
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {dataState === "ready" && visiblePlayers.length === 0 && (
              <p className="empty-table">No scoring leaders are available.</p>
            )}
            {dataState === "loading" && (
              <p className="empty-table">Loading the player index…</p>
            )}
            {dataState === "error" && (
              <p className="empty-table">
                Player index is unavailable. Check that the API is running.
              </p>
            )}
          </div>
          <p className="table-note">
            Season PPG and games played come from the NBA scoring leaderboard.
            Other statistics are averages from each player’s latest five
            regular-season games.
          </p>
        </section>
        <section
          className="compare-section"
          id="compare"
          aria-labelledby="compare-title"
        >
          <SectionLabel number={result ? "04" : "03"} aside="SIDE BY SIDE">
            PLAYER COMPARISON
          </SectionLabel>
          <div className="compare-intro">
            <div>
              <span className="eyebrow">TWO PLAYERS. SAME WINDOW.</span>
              <h2 id="compare-title">See the difference.</h2>
              <p>
                Compare recent numbers for two players from the leaders or
                all-player search.
              </p>
            </div>
            {compared.length > 0 && (
              <button
                className="clear-button"
                type="button"
                onClick={() => setSelected([])}
              >
                Clear selection <Icon name="close" size={15} />
              </button>
            )}
          </div>
          {compared.length < 2 ? (
            <div className="compare-empty">
              <div className="compare-empty-visual">
                <span>
                  {compared[0] ? (
                    <PlayerAvatar name={compared[0].name} large />
                  ) : (
                    <Icon name="plus" size={24} />
                  )}
                </span>
                <span>VS</span>
                <span>
                  <Icon name="plus" size={24} />
                </span>
              </div>
              <strong>
                {compared.length === 1
                  ? "Pick one more player"
                  : "Your matchup starts here"}
              </strong>
              <p>
                {compared.length === 1
                  ? `${compared[0].name} is ready. Add another player from the index.`
                  : "Use the + controls above or search any player to build a comparison."}
              </p>
              <a href="#players" className="text-link">
                Browse players <Icon name="arrow" size={16} />
              </a>
            </div>
          ) : (
            <div className="comparison-panel">
              <div className="comparison-head">
                {compared.map((player) => (
                  <div key={player.id}>
                    <PlayerAvatar name={player.name} />
                    <strong>{player.name}</strong>
                    <small>LAST {player.games_count} GAMES</small>
                  </div>
                ))}
              </div>
              <ComparisonMetric
                label="POINTS / GAME"
                left={compared[0].points}
                right={compared[1].points}
              />
              <ComparisonMetric
                label="REBOUNDS / GAME"
                left={compared[0].rebounds}
                right={compared[1].rebounds}
              />
              <ComparisonMetric
                label="ASSISTS / GAME"
                left={compared[0].assists}
                right={compared[1].assists}
              />
              <ComparisonMetric
                label="FIELD GOAL %"
                left={compared[0].field_goal_pct}
                right={compared[1].field_goal_pct}
                suffix="%"
              />
              <div className="comparison-trends">
                {compared.map((player) => (
                  <div key={player.id}>
                    <span className="mini-heading">
                      {player.name.toUpperCase()} · POINTS BY GAME
                    </span>
                    <TrendChart
                      games={player.games}
                      label={`${player.name} scoring`}
                    />
                  </div>
                ))}
              </div>
              <button
                className="primary-button compare-ask"
                type="button"
                onClick={() =>
                  usePrompt(
                    `Compare ${compared[0].name} and ${compared[1].name} over their last five games.`,
                  )
                }
              >
                Ask StatLine about this matchup <Icon name="arrow" size={16} />
              </button>
            </div>
          )}
        </section>
      </main>
      <footer className="site-footer">
        <div className="footer-inner">
          <div>
            <span className="brand footer-brand">
              <span className="brand-symbol">
                <span />
                <span />
                <span />
              </span>
              <span>
                StatLine<span className="brand-period">.</span>
              </span>
            </span>
            <p>NBA questions. Answers with receipts.</p>
          </div>
          <div>
            <span>DATA SCOPE</span>
            <p>
              {season} regular season · {players.length || "loaded"} player
              summaries
              <br />
              Sources: NBA LeagueLeaders and regular-season game logs
            </p>
          </div>
          <a href="#top">BACK TO TOP ↑</a>
        </div>
      </footer>
      {detail && (
        <PlayerDrawer
          player={detail}
          onClose={closeDetail}
          onAsk={usePrompt}
          onCompare={(player) => {
            toggleCompare(player.id);
            closeDetail();
            document
              .getElementById("compare")
              ?.scrollIntoView({ behavior: "smooth" });
          }}
        />
      )}
    </div>
  );
}
