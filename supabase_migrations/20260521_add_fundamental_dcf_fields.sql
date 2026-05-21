-- Optional Supabase schema upgrade for the DCF module.
-- Run this in Supabase SQL Editor when you have database owner access.
-- The Python uploader already works with the current compact schema by storing
-- FinMind numbers in summary JSON, but these columns make the data cleaner.

alter table public.fundamental_data
  add column if not exists currency text,
  add column if not exists revenue numeric,
  add column if not exists operating_income numeric,
  add column if not exists net_income numeric,
  add column if not exists operating_cash_flow numeric,
  add column if not exists capital_expenditure numeric,
  add column if not exists free_cash_flow numeric,
  add column if not exists shares_outstanding numeric,
  add column if not exists net_debt numeric,
  add column if not exists pe_ratio numeric,
  add column if not exists pb_ratio numeric,
  add column if not exists strengths text,
  add column if not exists fcf_forecast jsonb,
  add column if not exists data_source text,
  add column if not exists updated_at timestamptz default now();

create unique index if not exists fundamental_data_stock_year_uidx
  on public.fundamental_data (stock_code, year);
