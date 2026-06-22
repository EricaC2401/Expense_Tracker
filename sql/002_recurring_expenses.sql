create table if not exists public.recurring_expenses (
    id bigserial primary key,
    description text not null,
    category text not null default 'Uncategorised',
    amount_gbp numeric(12, 2) not null check (amount_gbp >= 0),
    amount_hkd numeric(12, 2) check (amount_hkd is null or amount_hkd >= 0),
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

alter table public.transactions
add column if not exists recurring_expense_id bigint references public.recurring_expenses (id),
add column if not exists generated_for_month date;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'transactions_recurring_generated_unique'
    ) then
        alter table public.transactions
        add constraint transactions_recurring_generated_unique
        unique (recurring_expense_id, generated_for_month);
    end if;
end;
$$;

drop trigger if exists trg_recurring_expenses_updated_at on public.recurring_expenses;

create trigger trg_recurring_expenses_updated_at
before update on public.recurring_expenses
for each row
execute function public.set_updated_at();

alter table public.recurring_expenses enable row level security;
