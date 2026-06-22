create table if not exists public.income_tax_due_entries (
    id bigserial primary key,
    tax_date date not null,
    tax_period text not null,
    amount_gbp numeric(14, 2) not null check (amount_gbp > 0),
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_income_tax_due_entries_updated_at on public.income_tax_due_entries;

create trigger trg_income_tax_due_entries_updated_at
before update on public.income_tax_due_entries
for each row
execute function public.set_updated_at();

alter table public.income_tax_due_entries enable row level security;
