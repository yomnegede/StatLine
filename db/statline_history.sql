-- Server-only NBA game facts. The API connects as the database owner; no Data API
-- roles receive access to this schema.
create schema if not exists statline;
revoke all on schema statline from public, anon, authenticated;

create table if not exists statline.team_games (
    season text not null,
    team_id bigint not null,
    game_id text not null,
    game_date date not null,
    matchup text not null,
    fetched_at timestamptz not null,
    primary key (team_id, game_id)
);

create index if not exists team_games_season_idx
    on statline.team_games (season);

create table if not exists statline.player_game_stats (
    season text not null,
    game_id text not null,
    player_id bigint not null,
    team_id bigint not null,
    points integer not null check (points >= 0),
    rebounds integer not null check (rebounds >= 0),
    assists integer not null check (assists >= 0),
    field_goals_made integer not null check (field_goals_made >= 0),
    field_goals_attempted integer not null check (field_goals_attempted >= field_goals_made),
    fetched_at timestamptz not null,
    primary key (game_id, player_id),
    foreign key (team_id, game_id) references statline.team_games (team_id, game_id)
);

create index if not exists player_game_stats_player_season_idx
    on statline.player_game_stats (player_id, season);
create index if not exists player_game_stats_team_game_idx
    on statline.player_game_stats (team_id, game_id);

create table if not exists statline.history_coverage (
    season text primary key,
    state text not null check (state in ('complete', 'partial')),
    team_games_count integer not null,
    player_games_count integer not null,
    source text not null,
    fetched_at timestamptz not null
);

alter table statline.team_games enable row level security;
alter table statline.player_game_stats enable row level security;
alter table statline.history_coverage enable row level security;
revoke all on all tables in schema statline from public, anon, authenticated;
