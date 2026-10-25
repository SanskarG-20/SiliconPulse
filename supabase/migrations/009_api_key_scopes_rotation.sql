-- Add least-privilege API key scopes, expiry and atomic key rotation.
alter table public.api_keys
  add column if not exists scopes text[] not null default array['signals:read','query:read','trends:read','compare:read','reports:generate'],
  add column if not exists expires_at timestamptz;

-- Give previously unexpired keys a transition window after rollout.
update public.api_keys
set expires_at = now() + interval '90 days'
where expires_at is null and revoked = false;

create index if not exists idx_api_keys_active_expiry
  on public.api_keys (expires_at) where revoked = false;

create or replace function public.rotate_user_api_key(
  p_user_id text,
  p_old_key_id uuid,
  p_key_hash text,
  p_key_prefix text,
  p_expires_at timestamptz
) returns table(id uuid, name text, scopes text[])
language plpgsql security definer set search_path = public as $$
declare
  old_key public.api_keys%rowtype;
  new_id uuid;
begin
  select * into old_key from public.api_keys
    where api_keys.id = p_old_key_id and api_keys.user_id = p_user_id and revoked = false
    for update;
  if not found then
    return;
  end if;
  update public.api_keys set revoked = true where api_keys.id = p_old_key_id and user_id = p_user_id;
  insert into public.api_keys(user_id, name, key_hash, key_prefix, scopes, expires_at)
    values (p_user_id, old_key.name, p_key_hash, p_key_prefix, old_key.scopes, p_expires_at)
    returning api_keys.id into new_id;
  return query select new_id, old_key.name, old_key.scopes;
end;
$$;

revoke all on function public.rotate_user_api_key(text, uuid, text, text, timestamptz) from public, anon, authenticated;
grant execute on function public.rotate_user_api_key(text, uuid, text, text, timestamptz) to service_role;
