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
