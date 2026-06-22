alter table public.transactions
drop column if exists cash;

alter table public.recurring_expenses
drop column if exists cash;
