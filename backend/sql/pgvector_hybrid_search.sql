-- Upgrade existing pgvector installations to indexed keyword + vector RRF.
-- Run after pgvector_schema.sql in the Supabase SQL editor.

alter table signals_vec
  add column if not exists search_vector tsvector
  generated always as (to_tsvector('simple', coalesce(document, ''))) stored;

create index if not exists signals_vec_search_vector_idx
  on signals_vec using gin (search_vector);

create or replace function match_signals_hybrid(
  query_text text,
  query_embedding vector(768),
  match_count int,
  full_text_weight float default 1.0,
  semantic_weight float default 1.0
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
  with parsed_query as (
    select websearch_to_tsquery('simple', coalesce(query_text, '')) as tsq
  ),
  keyword_hits as (
    select s.id, s.document, s.metadata,
      row_number() over (order by ts_rank_cd(s.search_vector, q.tsq) desc, s.id) as search_rank
    from signals_vec s cross join parsed_query q
    where numnode(q.tsq) > 0 and s.search_vector @@ q.tsq
    order by ts_rank_cd(s.search_vector, q.tsq) desc, s.id
    limit greatest(match_count * 4, match_count)
  ),
  semantic_hits as (
    select s.id, s.document, s.metadata,
      1 - (s.embedding <=> query_embedding) as similarity,
      row_number() over (order by s.embedding <=> query_embedding, s.id) as search_rank
    from signals_vec s
    where s.embedding is not null
    order by s.embedding <=> query_embedding, s.id
    limit greatest(match_count * 4, match_count)
  ),
  fused as (
    select k.id, full_text_weight / (60.0 + k.search_rank) as contribution
    from keyword_hits k
    union all
    select v.id, semantic_weight / (60.0 + v.search_rank) as contribution
    from semantic_hits v
  ),
  scores as (
    select f.id, sum(f.contribution) as rank_score from fused f group by f.id
  )
  select s.id, s.document, s.metadata,
    coalesce(v.similarity, 0)::float as similarity, scores.rank_score::float
  from scores
  join signals_vec s on s.id = scores.id
  left join semantic_hits v on v.id = s.id
  order by scores.rank_score desc, s.id
  limit greatest(match_count, 1);
$$;
