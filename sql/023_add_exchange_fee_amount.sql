alter table public.exchange_records
add column if not exists fee_amount numeric(14, 2);
