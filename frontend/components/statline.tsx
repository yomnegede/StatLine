"use client";

import type { ReactNode } from "react";

export type RecentGame = {
  date: string;
  matchup: string;
  points: number;
  rebounds: number;
  assists: number;
};
export type Player = {
  id: string;
  name: string;
  season: string;
  games_count: number;
  first_game: string;
  last_game: string;
  points: number;
  rebounds: number;
  assists: number;
  field_goal_pct: number;
  games: RecentGame[];
  source_id: string;
  rank: number | null;
  season_ppg: number | null;
  season_games: number | null;
};
export type PlayerOption = { id: number; name: string; active: boolean };
export type Source = {
  id: string;
  player: string;
  content: string;
  distance: number;
};
export type AskResponse = {
  answer: string | null;
  sources: Source[];
  status: "answered" | "answer_unavailable" | "no_data";
  notice: string | null;
};

export const metricLabels = {
  points: "PTS",
  rebounds: "REB",
  assists: "AST",
  field_goal_pct: "FG%",
} as const;
export type Metric = keyof typeof metricLabels;

export function Icon({
  name,
  size = 18,
}: {
  name: "arrow" | "search" | "chevron" | "plus" | "close" | "spark";
  size?: number;
}) {
  const paths = {
    arrow: (
      <>
        <path d="M4 12h15" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
    search: (
      <>
        <circle cx="10.8" cy="10.8" r="6.5" />
        <path d="m16 16 4 4" />
      </>
    ),
    chevron: <path d="m8 10 4 4 4-4" />,
    plus: (
      <>
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </>
    ),
    close: (
      <>
        <path d="M6 6 18 18" />
        <path d="M18 6 6 18" />
      </>
    ),
    spark: (
      <>
        <path d="m12 2 1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9L12 2Z" />
        <path d="m19 17 .6 1.4L21 19l-1.4.6L19 21l-.6-1.4L17 19l1.4-.6L19 17Z" />
      </>
    ),
  };
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

export function PlayerAvatar({
  name,
  large = false,
}: {
  name: string;
  large?: boolean;
}) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("");
  return (
    <span
      className={`player-avatar${large ? " player-avatar-large" : ""}`}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}

export function SectionLabel({
  number,
  children,
  aside,
}: {
  number: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="section-label">
      <div>
        <span className="section-number">{number}</span>
        <span>{children}</span>
      </div>
      {aside && <span className="section-aside">{aside}</span>}
    </div>
  );
}

export function StatBlock({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | number;
  unit?: string;
}) {
  return (
    <div className="stat-block">
      <span className="stat-value">
        {value}
        <small>{unit}</small>
      </span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export function TrendChart({
  games,
  label,
  metric = "points",
}: {
  games: RecentGame[];
  label: string;
  metric?: "points" | "rebounds" | "assists";
}) {
  const ordered = [...games].reverse();
  const max = Math.max(1, ...ordered.map((game) => game[metric]));
  return (
    <div
      className="trend-chart"
      role="img"
      aria-label={`${label}: ${ordered.map((game) => `${game.matchup} ${game[metric]}`).join(", ")}`}
    >
      {ordered.map((game, index) => (
        <div className="trend-item" key={`${game.date}-${index}`}>
          <span
            style={{ height: `${Math.max(7, (game[metric] / max) * 100)}%` }}
          />
          <small>{game[metric]}</small>
        </div>
      ))}
    </div>
  );
}

export function ComparisonMetric({
  label,
  left,
  right,
  suffix = "",
}: {
  label: string;
  left: number;
  right: number;
  suffix?: string;
}) {
  const max = Math.max(left, right, 1);
  return (
    <div className="comparison-metric">
      <div className="comparison-values">
        <strong className={left > right ? "leader" : ""}>
          {left.toFixed(1)}
          {suffix}
        </strong>
        <span>{label}</span>
        <strong className={right > left ? "leader" : ""}>
          {right.toFixed(1)}
          {suffix}
        </strong>
      </div>
      <div
        className="comparison-bars"
        aria-label={`${label}: ${left.toFixed(1)} versus ${right.toFixed(1)}`}
      >
        <span>
          <i style={{ width: `${(left / max) * 100}%` }} />
        </span>
        <span>
          <i style={{ width: `${(right / max) * 100}%` }} />
        </span>
      </div>
    </div>
  );
}
