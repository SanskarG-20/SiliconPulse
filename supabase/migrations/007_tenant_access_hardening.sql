-- Tenant policies for direct Supabase clients. Backend service-role access is
-- still checked in application code because service_role bypasses RLS.

alter table public.queries enable row level security;
alter table public.insights enable row level security;
alter table public.signals enable row level security;
alter table public.watchlists enable row level security;
alter table public.briefs enable row level security;
alter table public.digest_prefs enable row level security;
alter table public.api_keys enable row level security;
alter table public.team_webhooks enable row level security;
alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.workspace_watchlist enable row level security;
alter table public.rss_feeds enable row level security;
alter table public.brief_comments enable row level security;

drop policy if exists "Users can manage own queries" on public.queries;
create policy "Users can manage own queries" on public.queries
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Users can manage own insights" on public.insights;
create policy "Users can manage own insights" on public.insights
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Users can manage own signals" on public.signals;
create policy "Users can manage own signals" on public.signals
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Users can manage own watchlist" on public.watchlists;
create policy "Users can manage own watchlist" on public.watchlists
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Brief owners manage briefs" on public.briefs;
create policy "Brief owners manage briefs" on public.briefs
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);
drop policy if exists "Public or workspace briefs readable" on public.briefs;
create policy "Public or workspace briefs readable" on public.briefs
  for select using (
    is_public = true
    or user_id = auth.uid()::text
    or (workspace_id is not null and (
      exists (select 1 from public.workspaces w where w.id = briefs.workspace_id and w.owner_id = auth.uid()::text)
      or exists (select 1 from public.workspace_members m where m.workspace_id = briefs.workspace_id and m.user_id = auth.uid()::text)
    ))
  );

drop policy if exists "Users manage own digest preferences" on public.digest_prefs;
create policy "Users manage own digest preferences" on public.digest_prefs
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);
drop policy if exists "Users manage own api keys" on public.api_keys;
create policy "Users manage own api keys" on public.api_keys
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);
drop policy if exists "Users manage own team webhooks" on public.team_webhooks;
create policy "Users manage own team webhooks" on public.team_webhooks
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);
drop policy if exists "Users manage own rss feeds" on public.rss_feeds;
create policy "Users manage own rss feeds" on public.rss_feeds
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

drop policy if exists "Workspace owners manage workspace" on public.workspaces;
create policy "Workspace owners manage workspace" on public.workspaces
  for all using (owner_id = auth.uid()::text) with check (owner_id = auth.uid()::text);
drop policy if exists "Workspace members read workspace" on public.workspaces;
create policy "Workspace members read workspace" on public.workspaces
  for select using (
    owner_id = auth.uid()::text
    or exists (select 1 from public.workspace_members m where m.workspace_id = workspaces.id and m.user_id = auth.uid()::text)
  );

-- Membership changes go through authenticated backend endpoints; direct clients
-- may read membership only when they already belong to the workspace.
drop policy if exists "Users can manage workspace membership" on public.workspace_members;
drop policy if exists "Members can read workspace membership" on public.workspace_members;
create policy "Members can read workspace membership" on public.workspace_members
  for select using (
    user_id = auth.uid()::text
    or exists (select 1 from public.workspaces w where w.id = workspace_members.workspace_id and w.owner_id = auth.uid()::text)
  );

drop policy if exists "Members manage workspace watchlist" on public.workspace_watchlist;
create policy "Members manage workspace watchlist" on public.workspace_watchlist
  for all using (
    exists (select 1 from public.workspace_members m where m.workspace_id = workspace_watchlist.workspace_id and m.user_id = auth.uid()::text)
    or exists (select 1 from public.workspaces w where w.id = workspace_watchlist.workspace_id and w.owner_id = auth.uid()::text)
  ) with check (
    exists (select 1 from public.workspace_members m where m.workspace_id = workspace_watchlist.workspace_id and m.user_id = auth.uid()::text)
    or exists (select 1 from public.workspaces w where w.id = workspace_watchlist.workspace_id and w.owner_id = auth.uid()::text)
  );

drop policy if exists "Users can manage own brief comments" on public.brief_comments;
create policy "Users can manage own brief comments" on public.brief_comments
  for all using (user_id = auth.uid()::text) with check (
    user_id = auth.uid()::text
    and exists (select 1 from public.briefs b where b.id = brief_id and b.is_public = true)
  );
drop policy if exists "Anyone can read comments on public briefs" on public.brief_comments;
create policy "Anyone can read comments on public briefs" on public.brief_comments
  for select using (exists (select 1 from public.briefs b where b.id = brief_id and b.is_public = true));
