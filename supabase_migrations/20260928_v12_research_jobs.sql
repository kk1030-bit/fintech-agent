-- V1.2 research-job storage — DRAFT (W02-L). NOT APPLIED to any database.
-- Rehearse on a separate test project first, together with the rollback file
-- 20260928_v12_research_jobs_rollback.sql. Existing macro_data and
-- fundamental_data are not touched (no annual data is removed).
-- Table names follow handbook ch.02; a prefix, if any, is locked once by the team lead.

create table if not exists public.research_jobs (
  job_id uuid primary key,
  idempotency_key text not null unique,
  ticker text not null check (ticker in ('2330', '2317', '2454')),
  market text not null default 'TW',
  currency text not null default 'TWD',
  question_version text not null,
  cutoff_at timestamptz not null,
  source_snapshot_id text not null,
  mode text not null check (mode in ('workflow', 'single', 'dual')),
  status text not null check (status in ('queued', 'running', 'paused_quota', 'succeeded',
                                         'insufficient_evidence', 'timed_out', 'failed', 'cancelled')),
  stage text not null check (stage in ('research', 'tools', 'review', 'revision', 'finished')),
  model_id text,
  prompt_version text not null,
  calls_used int not null default 0 check (calls_used between 0 and 8),
  tokens_observed int not null default 0,
  tokens_reserved int not null default 0,
  tool_calls_used int not null default 0 check (tool_calls_used between 0 and 10),
  supplement_rounds int not null default 0 check (supplement_rounds between 0 and 2),
  active_seconds numeric not null default 0,
  stop_reason text,
  checkpoint_version int not null default 1,
  checkpoint jsonb,
  lease_owner text,
  lease_token bigint not null default 0,
  lease_expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- at most one running job with a live lease is enforced in the claim function;
-- this index keeps the claim query cheap
create index if not exists research_jobs_status_created_idx on public.research_jobs (status, created_at);

create table if not exists public.job_events (
  job_id uuid not null references public.research_jobs(job_id),
  event_seq int not null,
  created_at timestamptz not null default now(),
  role text,
  event_type text not null,
  tool_name text,
  detail jsonb not null default '{}'::jsonb,   -- redacted args, hashes, usage; never secrets or hidden reasoning
  primary key (job_id, event_seq)
);

create table if not exists public.model_usage (
  usage_id bigserial primary key,
  job_id uuid references public.research_jobs(job_id),
  sent_at timestamptz not null default now(),
  day_key date not null,                         -- Pacific-time day (Gemini RPD reset)
  role text,
  model_id text not null,
  prompt_version text not null,
  prompt_hash text not null,
  reserved_tokens int not null,
  total_tokens int,                              -- null = provider usage unknown, reservation kept
  outcome text not null
);
create index if not exists model_usage_day_idx on public.model_usage (day_key);
create index if not exists model_usage_sent_idx on public.model_usage (sent_at);

create table if not exists public.evidence_versions (
  evidence_version_id text primary key,
  source_snapshot_id text not null,
  source_url text not null,
  source_type text not null check (source_type in ('financial', 'macro', 'price', 'official_document')),
  published_at timestamptz,                      -- null when the provider has no announcement time
  captured_at timestamptz not null,
  available_at timestamptz not null,             -- never back-filled earlier than captured_at when unknown
  period text,
  period_basis text check (period_basis in ('single_quarter', 'ytd', 'annual', 'instant')),
  currency text,
  unit text,
  content_hash text not null,
  synthetic_fixture boolean not null default false,
  body jsonb
);
create index if not exists evidence_versions_snapshot_idx on public.evidence_versions (source_snapshot_id);

create table if not exists public.report_versions (
  report_version_id text primary key,
  job_id uuid not null references public.research_jobs(job_id),
  status text not null check (status in ('draft', 'approved', 'pdf_failed', 'published')),
  report_json jsonb not null,
  report_hash text not null,
  pdf_hash text,
  storage_key text,
  approved_by text,
  approved_at timestamptz,
  published_at timestamptz,
  created_at timestamptz not null default now()
);

-- Backend-only access: RLS on, no anon/authenticated policies. The server uses
-- the service role from env; the browser never receives it. Published report
-- read access for the public site is added in W07 after the approval gate exists.
alter table public.research_jobs enable row level security;
alter table public.job_events enable row level security;
alter table public.model_usage enable row level security;
alter table public.evidence_versions enable row level security;
alter table public.report_versions enable row level security;
