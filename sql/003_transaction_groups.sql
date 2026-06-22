alter table public.transactions
add column if not exists group_name text not null default 'Living';
