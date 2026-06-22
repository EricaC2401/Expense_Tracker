create table if not exists public.income_transactions (
    id bigserial primary key,
    income_date date not null,
    description text not null,
    source text not null,
    currency text not null,
    gross_amount numeric(14, 2) not null,
    payment_account text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_income_transactions_updated_at on public.income_transactions;

create trigger trg_income_transactions_updated_at
before update on public.income_transactions
for each row
execute function public.set_updated_at();

alter table public.income_transactions enable row level security;
