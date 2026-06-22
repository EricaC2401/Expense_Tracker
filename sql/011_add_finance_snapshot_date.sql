alter table public.finance_snapshot_entries
add column if not exists snapshot_date date not null default current_date;
