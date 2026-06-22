create table if not exists public.recurring_income_templates (
    id bigserial primary key,
    description text not null,
    source text not null,
    currency text not null,
    gross_amount numeric(14, 2) not null check (gross_amount > 0),
    payment_account text,
    notes text,
    day_of_month integer not null check (day_of_month between 1 and 31),
    start_date date not null,
    end_date date check (end_date is null or end_date >= start_date),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.income_transactions
add column if not exists recurring_income_id bigint references public.recurring_income_templates (id),
add column if not exists generated_for_month date;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'income_transactions_recurring_generated_unique'
    ) then
        alter table public.income_transactions
        add constraint income_transactions_recurring_generated_unique
        unique (recurring_income_id, generated_for_month);
    end if;
end;
$$;

drop trigger if exists trg_recurring_income_templates_updated_at on public.recurring_income_templates;

create trigger trg_recurring_income_templates_updated_at
before update on public.recurring_income_templates
for each row
execute function public.set_updated_at();

alter table public.recurring_income_templates enable row level security;
