-- Section B skill pipeline: Supabase (Postgres) schema.
-- Apply with:  py src/db.py --init        (safe to re-run: everything is "if not exists")
--
-- Row Level Security is ON with no policies, so the public Supabase API keys cannot read or write
-- anything. Our scripts and the local UI connect with the database connection string (SUPABASE_DB_URL).

-- One row per job posting, from the Kaggle sample or the live Greenhouse feed.
create table if not exists postings (
  posting_id   text primary key,                 -- li_<id> (Kaggle) or gh_<board>_<id> (Greenhouse)
  source       text not null check (source in ('kaggle', 'greenhouse')),
  company      text,
  title        text,
  location     text,
  sector       text,
  url          text,
  description  text not null,                    -- cleaned text, contacts masked
  text_hash    text not null,                    -- sha256 of normalised text: dedupe across sources
  fetched_at   timestamptz not null default now()
);
create unique index if not exists postings_text_hash on postings (text_hash);

-- One row per extracted skill statement (LLM output, before any human review).
create table if not exists skill_statements (
  statement_id     text primary key,             -- <posting_id>:skill:<i>
  posting_id       text not null references postings (posting_id) on delete cascade,
  skill            text not null,
  skill_key        text not null,                -- lower(trim(skill)); joins skill_links
  evidence         text,
  evidence_in_text boolean,                      -- evidence phrase found verbatim in the posting
  provider         text,
  model            text,                         -- the model that actually answered (after fallback)
  prompt_version   text,
  run_id           text,
  created_at       timestamptz not null default now()
);
create index if not exists skill_statements_key on skill_statements (skill_key);
create index if not exists skill_statements_posting on skill_statements (posting_id);

-- One row per unique skill: the ESCO / O*NET verdict (rule E), then any human review on top.
create table if not exists skill_links (
  skill_key     text primary key,
  verdict       text not null check (verdict in ('known_skill', 'trait', 'new_candidate', 'not_a_skill')),
  source        text,                            -- e.g. "ESCO skill", "O*NET Work Style", "human review"
  ref_label     text,
  ref_id        text,
  score         real,
  match         text,                            -- exact / meaning / review
  review_status text not null default 'auto' check (review_status in ('auto', 'reviewed')),
  updated_at    timestamptz not null default now()
);
create index if not exists skill_links_verdict on skill_links (verdict);

-- Every human review decision (append-only). The latest decision per skill_key wins, and it is
-- reused next time, so the same unknown skill is never reviewed twice (the alias table).
create table if not exists review_decisions (
  id         bigint generated always as identity primary key,
  skill_key  text not null,
  decision   text not null check (decision in ('skill', 'trait', 'not_a_skill', 'alias')),
  alias_of   text,                               -- canonical name when decision = 'alias'
  reviewer   text not null,
  note       text,
  decided_at timestamptz not null default now()
);
create index if not exists review_decisions_key on review_decisions (skill_key, id desc);

-- Pipeline runs and their stage events, shown live in the UI.
create table if not exists pipeline_runs (
  run_id       text primary key,                 -- UTC timestamp, e.g. 20261021T143000Z
  source       text not null,
  status       text not null default 'running' check (status in ('running', 'done', 'failed')),
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  n_fetched    integer not null default 0,
  n_new        integer not null default 0,
  n_statements integer not null default 0,
  note         text
);
create table if not exists pipeline_events (
  id      bigint generated always as identity primary key,
  run_id  text not null references pipeline_runs (run_id) on delete cascade,
  ts      timestamptz not null default now(),
  stage   text not null check (stage in ('fetch', 'clean', 'dedupe', 'extract', 'link', 'load', 'model_switch')),
  status  text not null check (status in ('start', 'progress', 'done', 'error', 'info')),
  model   text,
  message text
);
create index if not exists pipeline_events_run on pipeline_events (run_id, id);

alter table postings         enable row level security;
alter table skill_statements enable row level security;
alter table skill_links      enable row level security;
alter table review_decisions enable row level security;
alter table pipeline_runs    enable row level security;
alter table pipeline_events  enable row level security;

-- One model per posting: what embeddings / RAG read (never two models' skills for the same posting).
-- Kaggle: Qwen rows where Qwen has done the posting, otherwise the Haiku research-benchmark rows.
-- Greenhouse: all rows (one pipeline model per posting, whichever the LiteLLM router used).
-- security_invoker: the view obeys the tables' Row Level Security (a plain view would bypass it).
create or replace view current_statements with (security_invoker = true) as
select s.*
from skill_statements s
join postings p using (posting_id)
where p.source = 'greenhouse'
   or s.model = 'qwen/qwen3.8-27b'
   or not exists (select 1 from skill_statements q
                  where q.posting_id = s.posting_id and q.model = 'qwen/qwen3.8-27b');

-- Shared data contract (taxonomy-skill-project/docs/data_contract.md §3): statements with kind = 'skill'.
-- Section A adds its own kind = 'task' rows; both are read through the same column names.
-- statement_id follows the contract: {run_id}:{posting_id}:{kind}:{n}, n 0-based within the posting.
-- Built on current_statements, so consumers get one model per posting. posting_id keeps our format
-- (li_<id> / gh_<board>_<id>); the contract's "greenhouse:{board}:{id}" form is still to be agreed (D4).
create or replace view statements with (security_invoker = true) as
select coalesce(s.run_id, 'norun') || ':' || s.posting_id || ':skill:' ||
         (split_part(s.statement_id, ':', -1)::int - 1)                  as statement_id,
       s.posting_id,
       null::text                                                         as snapshot_id,
       'skill'::text                                                      as kind,
       s.skill                                                            as text,
       s.evidence                                                         as source_span,
       null::text                                                         as section,
       'llm:' || s.model                                                  as extraction_method,
       s.run_id,
       s.statement_id                                                     as source_statement_id
from current_statements s;
