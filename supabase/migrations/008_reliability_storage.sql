-- Canonical production signal and operational state. Local JSONL/SQLite/Chroma
-- are development fallbacks or rebuildable caches only.

create extension if not exists vector;

create table if not exists public.market_signals (
  event_id text primary key,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists market_signals_created_at_idx
  on public.market_signals (created_at desc);

create table if not exists public.ingestion_checkpoints (
  source text primary key,
  last_checkpoint text not null,
  last_pull_at timestamptz not null default now()
);

create table if not exists public.websocket_tickets (
  ticket_hash text primary key,
  user_id text not null,
  expires_at timestamptz not null
);
create index if not exists websocket_tickets_expiry_idx
  on public.websocket_tickets (expires_at);

grant select, insert, update, delete on public.market_signals to service_role;
grant select, insert, update, delete on public.ingestion_checkpoints to service_role;
grant select, insert, update, delete on public.websocket_tickets to service_role;
grant select, insert, update, delete on public.signals_vec to service_role;

alter table public.market_signals enable row level security;
alter table public.ingestion_checkpoints enable row level security;
alter table public.websocket_tickets enable row level security;

create or replace function public.ingest_market_signals(p_events jsonb)
returns table(event_id text, payload jsonb)
language plpgsql
security definer
set search_path = public
as $$
declare
  item jsonb;
  inserted_id text;
  inserted_payload jsonb;
begin
  for item in select value from jsonb_array_elements(coalesce(p_events, '[]'::jsonb)) loop
    insert into public.market_signals as stored (event_id, payload)
    values (item->>'event_id', item->'payload')
    on conflict (event_id) do nothing
    returning stored.event_id, stored.payload into inserted_id, inserted_payload;
    if found then
      event_id := inserted_id;
      payload := inserted_payload;
      return next;
    end if;
  end loop;
end;
$$;

create or replace function public.list_market_signals(p_limit integer)
returns table(payload jsonb)
language sql stable security definer
set search_path = public
as $$
  select s.payload
  from public.market_signals s
  order by s.created_at desc
  limit greatest(1, least(coalesce(p_limit, 200), 5000));
$$;

create or replace function public.market_signal_count()
returns bigint
language sql stable security definer
set search_path = public
as $$ select count(*) from public.market_signals; $$;

create or replace function public.consume_websocket_ticket(p_ticket_hash text)
returns text
language sql volatile security definer
set search_path = public
as $$
  delete from public.websocket_tickets
  where ticket_hash = p_ticket_hash and expires_at > now()
  returning user_id;
$$;

revoke all on function public.ingest_market_signals(jsonb) from public, anon, authenticated;
revoke all on function public.list_market_signals(integer) from public, anon, authenticated;
revoke all on function public.market_signal_count() from public, anon, authenticated;
revoke all on function public.consume_websocket_ticket(text) from public, anon, authenticated;
grant execute on function public.ingest_market_signals(jsonb) to service_role;
grant execute on function public.list_market_signals(integer) to service_role;
grant execute on function public.market_signal_count() to service_role;
grant execute on function public.consume_websocket_ticket(text) to service_role;
