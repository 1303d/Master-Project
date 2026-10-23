-- Section B skill taxonomy: entity-relationship tables on top of supabase_schema.sql (Sprint 3 draft).
-- Apply with:  py src/db.py --init        (runs after supabase_schema.sql; safe to re-run: "if not exists")
--
-- Entities and relationships (already existing tables in brackets):
--   posting --requires--> skill        [skill_statements.skill_key]
--   skill   --maps_to-->  ESCO / O*NET [skill_links]
--   skill   --alias_of--> skill        skill_aliases
--   skill   --member_of-> topic        skill_topics   (per clustering run; strong / weak / unassigned)
--   topic   --broader-->  family       topics.parent_topic_id
--   skill   --related_to-> skill       skill_relations (per run; nearest neighbours)
--   library skill --used_in--> topic   skill_library + library_links (co-occurrence, strong / weak)
-- Three kinds of id: skill_key (permanent), topic_id (persistent across runs), cluster_id (one run only).

-- alias_of: spelling variants and verified aliases point to one canonical skill_key.
create table if not exists skill_aliases (
  alias_key    text primary key,                 -- lower(trim(skill)) as extracted
  skill_key    text not null,                    -- canonical key that is embedded and clustered
  rule         text,                             -- R1/R2/R3 (normalize_aliases.py) or 'review'
  reviewed_by  text,                             -- null = rule-based, not human checked
  created_at   timestamptz not null default now()
);
create index if not exists skill_aliases_skill on skill_aliases (skill_key);

-- One row per clustering run (method + settings + input hash). Only one run is active at a time.
create table if not exists cluster_runs (
  run_id          text primary key,              -- e.g. leiden_20.0 or hdbscan_10_umap10_ms1 + date
  method          text not null,
  params          jsonb not null,
  vectors_sha256  text not null,
  metrics         jsonb,                         -- sweep + stability numbers
  is_active       boolean not null default false,
  created_at      timestamptz not null default now()
);
create unique index if not exists cluster_runs_one_active on cluster_runs (is_active) where is_active;

-- Persistent topics and families (level). Ids survive re-clustering via Jaccard + Hungarian matching.
create table if not exists topics (
  topic_id         text primary key,             -- T0001 (topic) / F001 (family)
  level            text not null check (level in ('family', 'topic')),
  label            text,
  parent_topic_id  text references topics (topic_id),  -- broader: topic -> family
  status           text not null default 'active' check (status in ('active', 'retired')),
  is_transversal   boolean not null default false, -- > 50% of mentions are library skills; not a link target
  split_from       text references topics (topic_id),
  merged_into      text references topics (topic_id),
  first_run        text references cluster_runs (run_id),
  last_run         text references cluster_runs (run_id),
  label_reviewed_by text
);

-- Which run-specific cluster became which persistent topic, and how (continue / split / merge / new).
create table if not exists run_clusters (
  run_id      text not null references cluster_runs (run_id) on delete cascade,
  cluster_id  int  not null,
  topic_id    text not null references topics (topic_id),
  event       text not null check (event in ('continue', 'split', 'merge', 'new')),
  jaccard     real,                              -- overlap with the matched previous topic
  primary key (run_id, cluster_id)
);

-- member_of: a skill's topic per run. Weak = has a best topic but low confidence; unassigned = no topic.
create table if not exists skill_topics (
  run_id     text not null references cluster_runs (run_id) on delete cascade,
  skill_key  text not null,
  topic_id   text not null references topics (topic_id),  -- unassigned skills have no row here
  role       text not null default 'primary' check (role in ('primary', 'secondary')),
  state      text not null check (state in ('assigned', 'weak')),
  score      real,                               -- cosine to topic centroid
  margin     real,                               -- best minus second-best centroid cosine
  primary key (run_id, skill_key, topic_id)       -- a skill may link to several topics
);
create index if not exists skill_topics_topic on skill_topics (run_id, topic_id);

-- related_to: nearest neighbour skills per run, so noise / weak skills still have useful links.
create table if not exists skill_relations (
  run_id       text not null references cluster_runs (run_id) on delete cascade,
  skill_key    text not null,
  related_key  text not null,
  rank         smallint not null,                -- 1 = closest
  similarity   real not null,
  primary key (run_id, skill_key, rank)
);

-- The skill library: a label on a canonical skill (no second id) for cross-sector skills and tools
-- (attention to detail, customer service, excel...). Rule library-v1 (build_library.py): >= 5 postings,
-- >= 4 of 8 sectors, no sector > 50%. The skill keeps its normal topic too; library_links adds domain links.
create table if not exists skill_library (
  skill_key     text primary key,
  status        text not null check (status in ('confirmed', 'candidate')),  -- confirmed = >= 10 postings
  n_postings    int  not null,
  n_unknown     int  not null,                   -- postings with no named sector (not in the spread stats)
  n_sectors     int  not null,
  top_share     real not null,                   -- share of postings in its biggest sector
  entropy       real not null,                   -- sector entropy / ln 8: 0 = one sector, 1 = even
  rule_version  text not null,
  run_id        text not null references cluster_runs (run_id) on delete cascade
);

-- used_in: library skill -> domain topic, by co-occurrence in the same postings (not by meaning).
-- library-v2: counted per job template (company + title), so a job copied to many cities counts once.
-- strong = >= 5 templates, lift >= 1.5 and BH q < 0.05 over all eligible pairs; else weak (thin line).
create table if not exists library_links (
  skill_key   text not null references skill_library (skill_key) on delete cascade,
  topic_id    text not null references topics (topic_id),
  n_postings  int  not null,
  lift        real not null,
  p_value     double precision not null,         -- hypergeometric
  q_value     double precision not null,         -- Benjamini-Hochberg
  strength    text not null check (strength in ('strong', 'weak')),
  primary key (skill_key, topic_id)
);

-- library-v2 additions (skill_types.py: tool / knowledge / skill / trait / unknown, ESCO reuse level)
alter table skill_library add column if not exists n_templates int;
alter table skill_library add column if not exists skill_type  text;
alter table skill_library add column if not exists reuse_level text;
alter table library_links add column if not exists n_templates int;

alter table skill_library   enable row level security;
alter table library_links   enable row level security;
alter table skill_aliases   enable row level security;
alter table cluster_runs    enable row level security;
alter table topics          enable row level security;
alter table run_clusters    enable row level security;
alter table skill_topics    enable row level security;
alter table skill_relations enable row level security;

-- What the UI / search read: the active run only.
create or replace view active_skill_topics with (security_invoker = true) as
select st.skill_key, st.topic_id, t.label as topic_label, t.parent_topic_id as family_id,
       st.role, st.state, st.score, st.margin
from skill_topics st
join cluster_runs r on r.run_id = st.run_id and r.is_active
left join topics t on t.topic_id = st.topic_id;
