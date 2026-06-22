do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'transactions'
          and column_name = 'expense_hkd'
    ) then
        alter table public.transactions
        rename column expense_hkd to amount_hkd;
    end if;
end;
$$;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'recurring_expenses'
          and column_name = 'expense_hkd'
    ) then
        alter table public.recurring_expenses
        rename column expense_hkd to amount_hkd;
    end if;
end;
$$;
