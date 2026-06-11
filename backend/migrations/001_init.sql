-- Radar de Narrativas — schema inicial
create schema if not exists radar;
set search_path to radar, public;

create table if not exists candidates (
    id            text primary key,
    username      text unique not null,
    display_name  text not null,
    cargo         text,
    is_competitor boolean not null default false
);

create table if not exists posts (
    id            text primary key,          -- shortcode/id do Instagram
    candidate_id  text not null references candidates(id) on delete cascade,
    url           text,
    caption       text default '',
    posted_at     timestamptz,
    like_count    integer not null default 0,
    comment_count integer not null default 0, -- total reportado pelo IG
    scraped_at    timestamptz not null default now()
);
create index if not exists idx_posts_candidate on posts(candidate_id);
create index if not exists idx_posts_posted_at on posts(posted_at desc);

create table if not exists comments (
    id             text primary key,          -- id do comentário no Instagram
    post_id        text not null references posts(id) on delete cascade,
    candidate_id   text not null references candidates(id) on delete cascade,
    text           text not null default '',
    owner_username text,
    commented_at   timestamptz,
    like_count     integer not null default 0,
    -- análise (preenchida pelo módulo de sentimento)
    sentiment       text,                     -- positive | negative | neutral
    sentiment_score real,                     -- -1.0 .. 1.0
    stance          text,                     -- apoio | contra | neutro
    themes          text[] default '{}',
    analyzed_at     timestamptz
);
create index if not exists idx_comments_post on comments(post_id);
create index if not exists idx_comments_candidate on comments(candidate_id);
create index if not exists idx_comments_analyzed on comments(analyzed_at);
create index if not exists idx_comments_sentiment on comments(sentiment);

create table if not exists scrape_runs (
    id                uuid primary key default gen_random_uuid(),
    status            text not null default 'running', -- running | completed | failed
    message           text default '',
    started_at        timestamptz not null default now(),
    finished_at       timestamptz,
    posts_scraped     integer not null default 0,
    comments_scraped  integer not null default 0,
    comments_analyzed integer not null default 0
);
create index if not exists idx_scrape_runs_started on scrape_runs(started_at desc);
