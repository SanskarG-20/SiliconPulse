-- SiliconPulse — Row Level Security (RLS)
-- Apply in Supabase Dashboard → SQL Editor or via `supabase db push`.
-- Assumes tables: users, queries, insights, signals, signals_vec
-- Uses auth.uid() (Supabase Auth user id) which maps to Clerk user_id when using Clerk ↔ Supabase JWT template.
-- Service role bypasses RLS automatically; anon/authenticated must satisfy policies.

-- 1) Ensure tables exist (idempotent)
create table if not exists public.users (
  id text primary key,
  email text,
  created_at timestamptz default now()
);

create table if not exists public.queries (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  query_text text not null,
  k int not null,
  evidence_count int not null,
  signal_strength int not null,
  created_at timestamptz default now()
);

create table if not exists public.insights (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  query_id uuid references public.queries(id) on delete set null,
  query_text text not null,
  insight text not null,
  model_name text not null,
  status text not null,
  created_at timestamptz default now()
);

create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  source text not null,
  title text not null,
  content text not null,
  event_timestamp text not null,
  company text,
  event_type text,
  url text,
  created_at timestamptz default now()
);

-- pgvector store (supabase branch)
create extension if not exists vector;
create table if not exists public.signals_vec (
  id text primary key,
  embedding vector(768),
  document text,
  metadata jsonb,
  created_at timestamptz default now()
);

-- 2) Enable RLS
alter table public.users enable row level security;
alter table public.queries enable row level security;
alter table public.insights enable row level security;
alter table public.signals enable row level security;
alter table public.signals_vec enable row level security;

-- 3) Policies — users can manage only their own rows
-- Note: service_role bypasses RLS, so backend (service_role) remains unaffected.
-- For authenticated users via Clerk JWT → Supabase (if you use anon key on client), enforce user_id = auth.uid()::text

drop policy if exists "Users can manage own row" on public.users;
create policy "Users can manage own row" on public.users
  for all using (id = auth.uid()::text) with check (id = auth.uid()::text);

drop policy if exists "Users can manage own queries" on public.queries;
create policy "Users can manage own queries" on public.queries
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Users can manage own insights" on public.insights;
create policy "Users can manage own insights" on public.insights
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Users can manage own signals" on public.signals;
create policy "Users can manage own signals" on public.signals
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

-- signals_vec is global semantic store (shared across users) but writes should still be via service_role.
-- Allow authenticated reads, block direct writes from anon/authenticated (only service_role can write).
drop policy if exists "Authenticated can read vec" on public.signals_vec;
create policy "Authenticated can read vec" on public.signals_vec
  for select using (auth.role() = 'authenticated' or auth.role() = 'service_role');

-- 4) Helper functions / indexes
create index if not exists idx_queries_user_id on public.queries(user_id);
create index if not exists idx_insights_user_id on public.insights(user_id);
create index if not exists idx_signals_user_id on public.signals(user_id);
-- ivfflat for pgvector (requires table has data; create after data load if needed)
-- create index if not exists idx_signals_vec_embedding on public.signals_vec using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 5) RPC for similarity search (used by pgvector_store.py:match_signals)
create or replace function public.match_signals(query_embedding vector(768), match_count int)
returns table (id text, document text, metadata jsonb, similarity float)
language sql stable
as $$
  select id, document, metadata, 1 - (embedding <=> query_embedding) as similarity
  from public.signals_vec
  order by embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.signals_vec_count()
returns int
language sql stable
as $$ select count(*)::int from public.signals_vec; $$;
