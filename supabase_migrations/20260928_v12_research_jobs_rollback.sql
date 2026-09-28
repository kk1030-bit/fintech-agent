-- Rollback for 20260928_v12_research_jobs.sql — DRAFT, NOT APPLIED.
-- Drops only the V1.2 tables; macro_data and fundamental_data are untouched.
drop table if exists public.report_versions;
drop table if exists public.evidence_versions;
drop table if exists public.model_usage;
drop table if exists public.job_events;
drop table if exists public.research_jobs;
