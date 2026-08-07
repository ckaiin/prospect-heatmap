-- Prospect heat map — Supabase schema.
-- Apply in the Supabase dashboard: SQL Editor -> paste -> Run. Safe to re-run.
--
-- Two tables:
--   venue_notes  — your visit tracker, synced across devices (private, RLS-guarded)
--   openings     — the SLA new-openings feed, refreshed server-side (public read)

-- ---------------------------------------------------------------------------
-- 1. VISIT TRACKER
-- ---------------------------------------------------------------------------
-- One row per venue you've touched. venue_id is the map's own id (OSM or SLA),
-- so it joins straight back to restaurants.js / openings.js without a lookup.
--
-- user_id is carried even though this starts single-user: it costs nothing now
-- and means adding teammates later is a policy change, not a migration.
create table if not exists public.venue_notes (
  user_id    uuid        not null references auth.users(id) on delete cascade,
  venue_id   text        not null,
  status     text        check (status in ('new','contacted','customer','not-interested')),
  note       text,
  updated_at timestamptz not null default now(),
  primary key (user_id, venue_id)
);

alter table public.venue_notes enable row level security;

-- Each signed-in user sees and writes only their own rows.
drop policy if exists "own notes" on public.venue_notes;
create policy "own notes" on public.venue_notes
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Sync is last-write-wins per venue, so the client sends its own updated_at.
-- Guard against a stale device clobbering a newer edit from another device.
create or replace function public.venue_notes_no_stale_write()
returns trigger language plpgsql as $$
begin
  if tg_op = 'UPDATE' and new.updated_at < old.updated_at then
    return old;                      -- incoming write is older; keep what's here
  end if;
  return new;
end $$;

drop trigger if exists venue_notes_no_stale on public.venue_notes;
create trigger venue_notes_no_stale
  before update on public.venue_notes
  for each row execute function public.venue_notes_no_stale_write();

-- ---------------------------------------------------------------------------
-- 2. OPENINGS FEED
-- ---------------------------------------------------------------------------
-- Written only by the refresh-openings Edge Function (service role). Public
-- read: this is public NY State Liquor Authority record, and the map is public.
create table if not exists public.openings (
  id            text        primary key,      -- e.g. sla-NA-0340-26-104941
  name          text        not null,
  category      text        not null default 'Restaurant',
  cuisine       text        not null default '',
  street        text        not null,
  lat           double precision not null,
  lng           double precision not null,
  fit_score     int         not null,
  monthly_value int         not null,
  opening       jsonb       not null,         -- {type, stage, received|issued, source}
  first_seen    timestamptz not null default now(),
  last_seen     timestamptz not null default now()
);

create index if not exists openings_last_seen_idx on public.openings (last_seen desc);

alter table public.openings enable row level security;

drop policy if exists "openings are public" on public.openings;
create policy "openings are public" on public.openings
  for select using (true);
-- No insert/update/delete policy: only the service-role key (the Edge Function)
-- can write, since service role bypasses RLS.

-- ---------------------------------------------------------------------------
-- 3. FOOT-TRAFFIC CACHE
-- ---------------------------------------------------------------------------
-- Real popular-times forecasts from BestTime, cached because each live fetch
-- costs an API credit. Written only by the foot-traffic Edge Function.
create table if not exists public.foot_traffic (
  venue_id   text        primary key,
  name       text,
  address    text,
  days       jsonb       not null,        -- [7][24] of 0..1, days[0] = Sunday
  fetched_at timestamptz not null default now()
);

alter table public.foot_traffic enable row level security;

drop policy if exists "foot traffic readable" on public.foot_traffic;
create policy "foot traffic readable" on public.foot_traffic
  for select using (true);

-- ---------------------------------------------------------------------------
-- 4. WEEKLY REFRESH (replaces the GitHub Action)
-- ---------------------------------------------------------------------------
-- Requires the pg_cron and pg_net extensions — enable both under
-- Database -> Extensions in the dashboard, then run this block.
--
-- Substitute <PROJECT-REF> and <SERVICE-ROLE-KEY> before running. The service
-- role key is a secret: it belongs only here (server-side), never in the page.
--
-- create extension if not exists pg_cron;
-- create extension if not exists pg_net;
--
-- select cron.schedule(
--   'refresh-openings-weekly',
--   '0 12 * * 1',                                  -- Mondays 12:00 UTC
--   $$
--   select net.http_post(
--     url     := 'https://<PROJECT-REF>.supabase.co/functions/v1/refresh-openings',
--     headers := '{"Content-Type":"application/json","Authorization":"Bearer <SERVICE-ROLE-KEY>"}'::jsonb,
--     timeout_milliseconds := 120000
--   );
--   $$
-- );
--
-- Inspect runs:   select * from cron.job_run_details order by start_time desc limit 10;
-- Remove:         select cron.unschedule('refresh-openings-weekly');
