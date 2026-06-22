create table if not exists public.transactions (
    id bigserial primary key,
    transaction_date date not null,
    description text not null,
    category text not null default 'Uncategorised',
    group_name text not null default 'Living',
    amount_gbp numeric(12, 2) not null check (amount_gbp >= 0),
    amount_hkd numeric(12, 2) check (amount_hkd is null or amount_hkd >= 0),
    tax_deductable boolean not null default false,
    payment_method text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_transactions_updated_at on public.transactions;

create trigger trg_transactions_updated_at
before update on public.transactions
for each row
execute function public.set_updated_at();

alter table public.transactions enable row level security;

create table if not exists public.finance_snapshot_entries (
    id bigserial primary key,
    snapshot_date date not null default current_date,
    institution text not null,
    account text not null,
    currency text not null,
    balance numeric(14, 2) not null,
    account_type text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_finance_snapshot_entries_updated_at on public.finance_snapshot_entries;

create trigger trg_finance_snapshot_entries_updated_at
before update on public.finance_snapshot_entries
for each row
execute function public.set_updated_at();

alter table public.finance_snapshot_entries enable row level security;
