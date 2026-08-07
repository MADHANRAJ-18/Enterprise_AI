# Supabase Setup – Module 3: Document Upload & Management

Run these SQL statements in your **Supabase SQL Editor** (Dashboard → SQL Editor → New Query).

---

## Step 1 – Create the `documents` Table

```sql
-- ── documents table ─────────────────────────────────────────
create table if not exists public.documents (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  file_name    text not null,
  file_type    text not null,
  file_size    bigint not null,
  storage_path text not null,
  category     text not null default 'General',
  status       text not null default 'Uploaded'
                 check (status in ('Uploaded', 'Processing', 'Indexed', 'Failed')),
  uploaded_at  timestamptz not null default now()
);

-- ── Performance index ────────────────────────────────────────
create index if not exists documents_user_id_idx
  on public.documents (user_id, uploaded_at desc);

-- ── Unique constraint: prevent same filename+size per user ───
create unique index if not exists documents_user_file_unique
  on public.documents (user_id, file_name, file_size);
```

---

## Step 2 – Enable Row Level Security

```sql
-- Enable RLS
alter table public.documents enable row level security;

-- Single policy: users can only see and manage their own documents
create policy "Users can manage their own documents"
  on public.documents
  for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);
```

---

## Step 3 – Create the Storage Bucket

In **Supabase Dashboard → Storage → New Bucket**:
- **Name**: `enterprise-documents`
- **Public**: No (keep private — files accessed via signed URLs)

---

## Step 4 – Storage RLS Policies

Run in SQL Editor:

```sql
-- Allow authenticated users to upload to their own folder
create policy "Authenticated users can upload to own folder"
  on storage.objects
  for insert
  to authenticated
  with check (
    bucket_id = 'enterprise-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Allow authenticated users to read their own files
create policy "Authenticated users can read own files"
  on storage.objects
  for select
  to authenticated
  using (
    bucket_id = 'enterprise-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Allow authenticated users to delete their own files
create policy "Authenticated users can delete own files"
  on storage.objects
  for delete
  to authenticated
  using (
    bucket_id = 'enterprise-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
```

---

## Step 5 – Verify Setup

```sql
select table_name, row_security
from information_schema.tables
where table_schema = 'public' and table_name = 'documents';
```

---

## Table Schema Reference

| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` | Primary key (auto-generated) |
| `user_id` | `uuid` | FK to auth.users.id |
| `file_name` | `text` | Original filename |
| `file_type` | `text` | PDF, DOCX, or TXT |
| `file_size` | `bigint` | Size in bytes |
| `storage_path` | `text` | Path inside enterprise-documents bucket |
| `category` | `text` | General, HR, Finance, Legal, IT, Policies, Research |
| `status` | `text` | Uploaded, Processing, Indexed, Failed |
| `uploaded_at` | `timestamptz` | Upload timestamp (auto-set) |
