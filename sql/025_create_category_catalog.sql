create table if not exists public.category_catalog (
    id bigserial primary key,
    category text not null,
    group_name text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint category_catalog_group_category_unique unique (category, group_name)
);

drop trigger if exists trg_category_catalog_updated_at on public.category_catalog;
create trigger trg_category_catalog_updated_at
before update on public.category_catalog
for each row
execute function public.set_updated_at();

insert into public.category_catalog (category, group_name)
values
    ('Housing', 'Living'),
    ('Groceries', 'Living'),
    ('C Groceries', 'Living'),
    ('Food', 'Living'),
    ('Drink', 'Living'),
    ('Transport', 'Living'),
    ('Car Related: Fuel', 'Living'),
    ('Car Related: Parking', 'Living'),
    ('Car Related: Annual', 'Living'),
    ('Car Related: One-off', 'Living'),
    ('Car Related: Other', 'Living'),
    ('Eating out', 'Living'),
    ('Shopping', 'Living'),
    ('Bills', 'Living'),
    ('Subscriptions', 'Living'),
    ('Healthcare', 'Living'),
    ('Travel', 'Living'),
    ('Gift', 'Living'),
    ('Dating', 'Living'),
    ('Exam', 'Living'),
    ('Visa', 'Living'),
    ('Money Transfer', 'Living'),
    ('Flight Ticket', 'Living'),
    ('Learning', 'Living'),
    ('Learning to Drive', 'Living'),
    ('Electronics', 'Living'),
    ('Tax', 'Living'),
    ('Trip', 'Living'),
    ('Necessaries', 'Living'),
    ('Appearance Related', 'Living'),
    ('Clothing', 'Living'),
    ('Snacks', 'Living'),
    ('Gathering', 'Living'),
    ('LH', 'Living'),
    ('Other', 'Living'),
    ('Uncategorised', 'Living')
on conflict (category, group_name) do nothing;

insert into public.category_catalog (category, group_name)
select distinct category, group_name
from public.transactions
where coalesce(trim(category), '') <> ''
  and coalesce(trim(group_name), '') <> ''
on conflict (category, group_name) do nothing;

insert into public.category_catalog (category, group_name)
select distinct category, 'Living'
from public.recurring_expenses
where coalesce(trim(category), '') <> ''
on conflict (category, group_name) do nothing;

alter table public.category_catalog enable row level security;
