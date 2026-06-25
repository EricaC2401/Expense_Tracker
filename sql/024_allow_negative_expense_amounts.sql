do $$
declare
    constraint_name text;
begin
    for constraint_name in
        select con.conname
        from pg_constraint con
        where con.conrelid = 'public.transactions'::regclass
          and con.contype = 'c'
          and pg_get_constraintdef(con.oid) in (
              'CHECK ((amount_gbp >= (0)::numeric))',
              'CHECK (((amount_hkd IS NULL) OR (amount_hkd >= (0)::numeric)))'
          )
    loop
        execute format(
            'alter table public.transactions drop constraint %I',
            constraint_name
        );
    end loop;

    for constraint_name in
        select con.conname
        from pg_constraint con
        where con.conrelid = 'public.recurring_expenses'::regclass
          and con.contype = 'c'
          and pg_get_constraintdef(con.oid) in (
              'CHECK ((amount_gbp >= (0)::numeric))',
              'CHECK (((amount_hkd IS NULL) OR (amount_hkd >= (0)::numeric)))'
          )
    loop
        execute format(
            'alter table public.recurring_expenses drop constraint %I',
            constraint_name
        );
    end loop;
end;
$$;
