# Supabase Migration — LangGraph Preparation Module

Run these SQL statements in **Supabase Dashboard → SQL Editor → New Query**.

> 💡 **Tip:** You can copy the entire file [supabase_migration.sql](file:///c:/Users/Madhan/Enterprise_AI_Assisstant/backend/supabase_migration.sql) and run it in a single click!

---

## STEP 1 — Create `companies` & `user_profiles` Tables

```sql
-- ── 1A: companies table ──────────────────────────────────────
create table if not exists public.companies (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  created_at  timestamptz not null default now()
);

-- ── 1B: user_profiles table ──────────────────────────────────
create table if not exists public.user_profiles (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null unique references auth.users(id) on delete cascade,
  company_id  uuid references public.companies(id) on delete set null,
  role        text not null default 'employee'
                check (role in ('knowledge_admin', 'employee')),
  full_name   text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists user_profiles_user_id_idx    on public.user_profiles (user_id);
create index if not exists user_profiles_company_id_idx on public.user_profiles (company_id);
```

---

## STEP 2 — RLS Policies for Companies & Profiles

```sql
-- Companies RLS
alter table public.companies enable row level security;

drop policy if exists "Users can read their own company" on public.companies;
create policy "Users can read their own company"
  on public.companies for select
  to authenticated
  using (
    id in (
      select company_id from public.user_profiles where user_id = auth.uid()
    )
  );

-- Profiles RLS
alter table public.user_profiles enable row level security;

drop policy if exists "Users can read own profile" on public.user_profiles;
create policy "Users can read own profile"
  on public.user_profiles for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists "Users can update own profile" on public.user_profiles;
create policy "Users can update own profile"
  on public.user_profiles for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid() and role = (
    select role from public.user_profiles where user_id = auth.uid()
  ));
```

---

## STEP 3 — Auto-Create Profile Trigger

```sql
-- ── Trigger: auto-create user_profile on signup ──────────────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  default_company_id uuid;
begin
  select id into default_company_id from public.companies order by created_at asc limit 1;

  insert into public.user_profiles (user_id, company_id, role, full_name)
  values (
    new.id,
    default_company_id,
    'employee',
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1))
  )
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
```

---

## STEP 4 — Insert Default Company & Migrate Existing Users

```sql
insert into public.companies (name)
values ('My Company')
on conflict do nothing;

do $$
declare
  default_company_id uuid;
  u record;
begin
  select id into default_company_id from public.companies order by created_at asc limit 1;

  for u in select id, email, raw_user_meta_data from auth.users loop
    insert into public.user_profiles (user_id, company_id, role, full_name)
    values (
      u.id,
      default_company_id,
      'employee',
      coalesce(
        u.raw_user_meta_data->>'full_name',
        u.raw_user_meta_data->>'name',
        split_part(u.email, '@', 1)
      )
    )
    on conflict (user_id) do update
      set company_id = excluded.company_id;
  end loop;
end;
$$;
```

---

## STEP 5 — Promote Users to Knowledge Admin

```sql
update public.user_profiles
set role = 'knowledge_admin';
```

---

## STEP 6 — Alter `documents` Table

```sql
alter table public.documents
  add column if not exists company_id uuid references public.companies(id) on delete set null,
  add column if not exists scope      text not null default 'company'
    check (scope in ('company', 'workspace'));

create index if not exists documents_scope_company_idx on public.documents (company_id, scope);
create index if not exists documents_scope_user_idx    on public.documents (user_id, scope);

do $$
declare
  default_company_id uuid;
begin
  select id into default_company_id from public.companies order by created_at asc limit 1;

  update public.documents
  set
    scope      = 'company',
    company_id = default_company_id
  where scope is null or company_id is null;
end;
$$;
```

---

## STEP 7 — Update Documents RLS Policies

```sql
drop policy if exists "Users can manage their own documents" on public.documents;
drop policy if exists "Employees can read company documents" on public.documents;
drop policy if exists "Employees can manage own workspace documents" on public.documents;
drop policy if exists "Knowledge Admins can manage company documents" on public.documents;

create policy "Employees can read company documents"
  on public.documents for select
  to authenticated
  using (
    scope = 'company'
    and company_id in (
      select company_id from public.user_profiles where user_id = auth.uid()
    )
  );

create policy "Employees can manage own workspace documents"
  on public.documents for all
  to authenticated
  using  (scope = 'workspace' and user_id = auth.uid())
  with check (scope = 'workspace' and user_id = auth.uid());

create policy "Knowledge Admins can manage company documents"
  on public.documents for all
  to authenticated
  using (
    scope = 'company'
    and company_id in (
      select company_id from public.user_profiles
      where user_id = auth.uid() and role = 'knowledge_admin'
    )
  )
  with check (
    scope = 'company'
    and company_id in (
      select company_id from public.user_profiles
      where user_id = auth.uid() and role = 'knowledge_admin'
    )
  );
```

---

## STEP 8 — Alter `document_chunks` Table & Policies

```sql
alter table public.document_chunks
  add column if not exists company_id uuid references public.companies(id) on delete set null,
  add column if not exists scope      text not null default 'company'
    check (scope in ('company', 'workspace'));

create index if not exists chunks_scope_company_idx on public.document_chunks (company_id, scope);
create index if not exists chunks_scope_user_idx    on public.document_chunks (user_id, scope);

do $$
declare
  default_company_id uuid;
begin
  select id into default_company_id from public.companies order by created_at asc limit 1;

  update public.document_chunks
  set
    scope      = 'company',
    company_id = default_company_id
  where scope is null or company_id is null;
end;
$$;

alter table public.document_chunks enable row level security;

drop policy if exists "Employees can read company chunks" on public.document_chunks;
drop policy if exists "Employees can manage own workspace chunks" on public.document_chunks;
drop policy if exists "Knowledge Admins can manage company chunks" on public.document_chunks;

create policy "Employees can read company chunks"
  on public.document_chunks for select
  to authenticated
  using (
    scope = 'company'
    and company_id in (
      select company_id from public.user_profiles where user_id = auth.uid()
    )
  );

create policy "Employees can manage own workspace chunks"
  on public.document_chunks for all
  to authenticated
  using  (scope = 'workspace' and user_id = auth.uid())
  with check (scope = 'workspace' and user_id = auth.uid());

create policy "Knowledge Admins can manage company chunks"
  on public.document_chunks for all
  to authenticated
  using (
    scope = 'company'
    and company_id in (
      select company_id from public.user_profiles
      where user_id = auth.uid() and role = 'knowledge_admin'
    )
  )
  with check (
    scope = 'company'
    and company_id in (
      select company_id from public.user_profiles
      where user_id = auth.uid() and role = 'knowledge_admin'
    )
  );
```

---

## STEP 9 — Create `conversations` Table

```sql
create table if not exists public.conversations (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  company_id  uuid references public.companies(id) on delete set null,
  title       text not null default 'New Conversation',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists conversations_user_id_idx on public.conversations (user_id, created_at desc);

alter table public.conversations enable row level security;

drop policy if exists "Users can manage own conversations" on public.conversations;
create policy "Users can manage own conversations"
  on public.conversations for all
  to authenticated
  using  (user_id = auth.uid())
  with check (user_id = auth.uid());
```

---

## STEP 10 — Create `messages` Table

```sql
create table if not exists public.messages (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references public.conversations(id) on delete cascade,
  user_id          uuid not null references auth.users(id) on delete cascade,
  role             text not null check (role in ('user', 'assistant')),
  content          text not null,
  sources          jsonb default '[]'::jsonb,
  created_at       timestamptz not null default now()
);

create index if not exists messages_conversation_id_idx on public.messages (conversation_id, created_at asc);
create index if not exists messages_user_id_idx          on public.messages (user_id);

alter table public.messages enable row level security;

drop policy if exists "Users can manage messages in own conversations" on public.messages;
create policy "Users can manage messages in own conversations"
  on public.messages for all
  to authenticated
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  )
  with check (
    user_id = auth.uid()
    and conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );
```

---

## STEP 11 — Verification

```sql
select 'SUCCESS: Enterprise AI Assistant migration completed successfully!' as migration_status;
```
