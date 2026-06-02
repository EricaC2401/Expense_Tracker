create table if not exists public.transactions (
    id bigserial primary key,
    transaction_date date not null,
    description text not null,
    category text not null default 'Uncategorised',
    amount_gbp numeric(12, 2) not null check (amount_gbp >= 0),
    expense_hkd numeric(12, 2) check (expense_hkd is null or expense_hkd >= 0),
    tax_deductable boolean not null default false,
    cash boolean not null default false,
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
