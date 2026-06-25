create table if not exists public.exchange_records (
    id bigserial primary key,
    exchange_date date not null,
    from_institution text not null,
    from_account text not null,
    from_currency text not null,
    from_amount numeric(14, 2) not null,
    fee_amount numeric(14, 2),
    to_institution text not null,
    to_account text not null,
    to_currency text not null,
    to_amount numeric(14, 2) not null,
    display_rate_value numeric(18, 8) not null,
    display_rate_base_currency text not null,
    display_rate_quote_currency text not null,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_exchange_records_updated_at on public.exchange_records;

create trigger trg_exchange_records_updated_at
before update on public.exchange_records
for each row
execute function public.set_updated_at();

alter table public.exchange_records enable row level security;
