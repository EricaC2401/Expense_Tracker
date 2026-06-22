create index if not exists idx_finance_snapshot_entries_account_latest
on public.finance_snapshot_entries (
    institution,
    account,
    currency,
    snapshot_date desc,
    id desc
);

create index if not exists idx_finance_snapshot_entries_snapshot_date
on public.finance_snapshot_entries (snapshot_date desc);
