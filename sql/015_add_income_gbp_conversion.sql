alter table public.income_transactions
add column if not exists gross_amount_gbp numeric(14, 2);

alter table public.income_transactions
add column if not exists fx_rate_to_gbp numeric(18, 8);
