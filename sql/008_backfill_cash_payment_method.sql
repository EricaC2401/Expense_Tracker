update public.transactions
set payment_method = 'Cash'
where cash = true
  and payment_method is null;
