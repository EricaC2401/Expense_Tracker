alter table public.finance_snapshot_entries
add column if not exists related_record_type text;
