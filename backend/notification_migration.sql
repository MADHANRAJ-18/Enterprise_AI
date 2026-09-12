-- ─────────────────────────────────────────────────────────────
-- Module: Company Document Update Notification
-- Tables: user_preferences, notifications
-- ─────────────────────────────────────────────────────────────

-- 1. Create user_preferences table
create table if not exists public.user_preferences (
  user_id               uuid primary key references auth.users(id) on delete cascade,
  company_file_updates  boolean not null default true,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists user_preferences_user_id_idx on public.user_preferences (user_id);

alter table public.user_preferences enable row level security;

drop policy if exists "Users can read own preferences" on public.user_preferences;
create policy "Users can read own preferences"
  on public.user_preferences for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists "Users can insert own preferences" on public.user_preferences;
create policy "Users can insert own preferences"
  on public.user_preferences for insert
  to authenticated
  with check (user_id = auth.uid());

drop policy if exists "Users can update own preferences" on public.user_preferences;
create policy "Users can update own preferences"
  on public.user_preferences for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());


-- 2. Create notifications table
create table if not exists public.notifications (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references auth.users(id) on delete cascade,
  company_id           uuid references public.companies(id) on delete cascade,
  type                 text not null default 'company_document_update',
  title                text not null,
  message              text not null,
  related_document_id  uuid,
  is_read              boolean not null default false,
  created_at           timestamptz not null default now()
);

create index if not exists notifications_user_id_idx       on public.notifications (user_id, created_at desc);
create index if not exists notifications_user_unread_idx   on public.notifications (user_id, is_read);
create index if not exists notifications_company_id_idx    on public.notifications (company_id);

alter table public.notifications enable row level security;

drop policy if exists "Users can read own notifications" on public.notifications;
create policy "Users can read own notifications"
  on public.notifications for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists "Users can update own notifications" on public.notifications;
create policy "Users can update own notifications"
  on public.notifications for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

drop policy if exists "Users can delete own notifications" on public.notifications;
create policy "Users can delete own notifications"
  on public.notifications for delete
  to authenticated
  using (user_id = auth.uid());


-- 3. Populate preferences for existing users (default: company_file_updates = true)
insert into public.user_preferences (user_id, company_file_updates)
select id, true from auth.users
on conflict (user_id) do nothing;
