do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'finance_snapshot_entries'
          and column_name = 'related_expense_item'
    ) then
        alter table public.finance_snapshot_entries
        rename column related_expense_item to related_record_item;
    end if;

    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'finance_snapshot_entries'
          and column_name = 'related_expense_amount'
    ) then
        alter table public.finance_snapshot_entries
        rename column related_expense_amount to related_record_amount;
    end if;
end $$;
