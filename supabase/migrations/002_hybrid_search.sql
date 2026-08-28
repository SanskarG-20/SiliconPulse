-- Migration: Add Hybrid Search (Vector + Full-Text Search) with Reciprocal Rank Fusion (RRF)

-- 1) Add a generated tsvector column for fast full-text search
-- This combines the title (from metadata jsonb) and the document content.
alter table public.signals_vec
add column if not exists fts tsvector generated always as (
  to_tsvector('english', coalesce(metadata->>'title', '') || ' ' || coalesce(document, ''))
) stored;

-- 2) Create a GIN index on the new fts column to speed up text queries
create index if not exists idx_signals_vec_fts on public.signals_vec using gin(fts);

-- 3) Create a function to perform hybrid search using Reciprocal Rank Fusion (RRF)
-- RRF combines the ranks of full-text search and semantic vector search.
create or replace function public.match_signals_hybrid(
  query_text text,
  query_embedding vector(768),
  match_count int default 20,
  full_text_weight float default 1.0,
  semantic_weight float default 1.0,
  rrf_k int default 50
)
returns table (
  id text,
  document text,
  metadata jsonb,
  similarity float,
  rank_score float
)
language sql stable
as $$
  with full_text as (
    select
      id,
      -- Rank based on ts_rank using websearch_to_tsquery which supports OR, "", - etc.
      row_number() over (order by ts_rank(fts, websearch_to_tsquery('english', query_text)) desc) as rank_ix
    from public.signals_vec
    where fts @@ websearch_to_tsquery('english', query_text)
    -- We limit the subquery to a reasonable number to prevent full table scans on common words
    limit 100
  ),
  semantic as (
    select
      id,
      1 - (embedding <=> query_embedding) as similarity,
      row_number() over (order by embedding <=> query_embedding) as rank_ix
    from public.signals_vec
    limit 100
  )
  select
    v.id,
    v.document,
    v.metadata,
    coalesce(s.similarity, 0.0) as similarity,
    -- Compute the RRF score
    (coalesce(1.0 / (rrf_k + f.rank_ix), 0.0) * full_text_weight) +
    (coalesce(1.0 / (rrf_k + s.rank_ix), 0.0) * semantic_weight) as rank_score
  from public.signals_vec v
  -- Full outer join ensures we consider documents found by EITHER method
  full outer join full_text f on v.id = f.id
  full outer join semantic s on v.id = s.id
  where f.id is not null or s.id is not null
  order by rank_score desc
  limit match_count;
$$;
