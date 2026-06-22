alter table public.transactions
add column if not exists payment_method text;

alter table public.recurring_expenses
add column if not exists payment_method text;
