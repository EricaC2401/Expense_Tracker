alter table public.finance_snapshot_entries
add column if not exists related_expense_item text,
add column if not exists related_expense_amount numeric(14, 2);
