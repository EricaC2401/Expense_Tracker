alter table public.income_transactions
add column if not exists is_taxable boolean not null default true;

alter table public.recurring_income_templates
add column if not exists is_taxable boolean not null default true;
