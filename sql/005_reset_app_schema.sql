-- WARNING:
-- This script drops and recreates the app tables from scratch.
-- Running it will permanently delete all data in:
--   - public.transactions
--   - public.recurring_expenses
--   - public.finance_snapshot_entries

begin;

drop table if exists public.transactions cascade;
drop table if exists public.recurring_expenses cascade;
drop table if exists public.finance_snapshot_entries cascade;
drop function if exists public.set_updated_at() cascade;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create table public.recurring_expenses (
    id bigserial primary key,
    description text not null,
    category text not null default 'Uncategorised',
    amount_gbp numeric(12, 2) not null,
    amount_hkd numeric(12, 2),
    tax_deductable boolean not null default false,
    payment_method text,
    notes text,
    day_of_month integer not null check (day_of_month between 1 and 31),
    start_date date not null,
    end_date date check (end_date is null or end_date >= start_date),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.transactions (
    id bigserial primary key,
    transaction_date date not null,
    description text not null,
    category text not null default 'Uncategorised',
    group_name text not null default 'Living',
    amount_gbp numeric(12, 2) not null,
    amount_hkd numeric(12, 2),
    tax_deductable boolean not null default false,
    payment_method text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    recurring_expense_id bigint references public.recurring_expenses (id),
    generated_for_month date,
    constraint transactions_recurring_generated_unique
        unique (recurring_expense_id, generated_for_month)
);

create table public.finance_snapshot_entries (
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

drop trigger if exists trg_recurring_expenses_updated_at on public.recurring_expenses;
create trigger trg_recurring_expenses_updated_at
before update on public.recurring_expenses
for each row
execute function public.set_updated_at();

drop trigger if exists trg_transactions_updated_at on public.transactions;
create trigger trg_transactions_updated_at
before update on public.transactions
for each row
execute function public.set_updated_at();

drop trigger if exists trg_finance_snapshot_entries_updated_at on public.finance_snapshot_entries;
create trigger trg_finance_snapshot_entries_updated_at
before update on public.finance_snapshot_entries
for each row
execute function public.set_updated_at();

alter table public.transactions enable row level security;
alter table public.recurring_expenses enable row level security;
alter table public.finance_snapshot_entries enable row level security;

commit;
