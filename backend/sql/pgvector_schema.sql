-- pgvector schema for SiliconPulse signals
-- Run this in Supabase SQL Editor (Database → SQL Editor)

-- Enable pgvector extension
create extension if not exists vector;

-- Table for signal embeddings (768-dim for gemini-embedding-001)
create table if not exists signals_vec (
  id text primary key,
  embedding vector(768),
  document text,
  metadata jsonb,
  created_at timestamptz default now()
);

-- Index for fast cosine similarity search
create index if not exists signals_vec_embedding_idx
  on signals_vec using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- RPC for similarity search: match_signals
-- Usage: select * from match_signals(query_embedding, match_count)
create or replace function match_signals(
  query_embedding vector(768),
  match_count int
)
returns table (
  id text,
  document text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    signals_vec.id,
    signals_vec.document,
    signals_vec.metadata,
    1 - (signals_vec.embedding <=> query_embedding) as similarity
  from signals_vec
  order by signals_vec.embedding <=> query_embedding
  limit match_count;
$$;

-- Optional: RPC to get count
create or replace function signals_vec_count()
returns int
language sql stable
as $$
  select count(*)::int from signals_vec;
$$;
