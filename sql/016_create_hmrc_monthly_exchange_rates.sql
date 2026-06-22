create table if not exists public.hmrc_monthly_exchange_rates (
    rate_month date not null,
    currency_code text not null,
    units_per_gbp numeric(18, 8) not null,
    fetched_at timestamptz not null default now(),
    primary key (rate_month, currency_code)
);

alter table public.hmrc_monthly_exchange_rates enable row level security;
