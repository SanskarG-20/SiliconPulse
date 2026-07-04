-- SiliconPulse Supabase schema
-- Run this in Supabase SQL editor.

create extension if not exists "pgcrypto";

create table if not exists public.users (
  id text primary key,
  email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  user_id text references public.users(id) on delete set null,
  source text not null,
  title text not null,
  content text,
  url text,
  company text,
  event_type text,
  event_timestamp timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.queries (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  query_text text not null,
  k integer,
  evidence_count integer,
  signal_strength integer,
  created_at timestamptz not null default now()
);

create table if not exists public.insights (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  query_id uuid references public.queries(id) on delete set null,
  query_text text,
  insight text not null,
  model_name text,
  status text not null default 'success',
  created_at timestamptz not null default now()
);

create index if not exists idx_signals_created_at on public.signals(created_at desc);
create index if not exists idx_signals_event_timestamp on public.signals(event_timestamp desc);
create index if not exists idx_queries_user_created on public.queries(user_id, created_at desc);
create index if not exists idx_insights_user_created on public.insights(user_id, created_at desc);

-- Keep update timestamp current on users row update.
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_users_updated_at on public.users;
create trigger trg_users_updated_at
before update on public.users
for each row execute function public.set_updated_at();
