-- Per-customer overrides of the shared settings (e.g. each person's own tax share and mortgage rate).
-- A customer without a row for a key uses the shared value from public.settings.

create table if not exists public.customer_settings (
  customer_id text not null references public.customers (customer_id) on delete cascade,
  key         text not null references public.settings (key) on delete cascade,
  value       numeric not null,
  updated_at  timestamptz not null default now(),
  primary key (customer_id, key)
);

-- Same limits as the shared setting (a CHECK constraint can't look at another table).
create or replace function public.check_customer_setting() returns trigger
language plpgsql set search_path = '' as $$
declare
  lo numeric;
  hi numeric;
begin
  select min_value, max_value into lo, hi from public.settings where key = new.key;
  if new.value < lo or new.value > hi then
    raise exception 'customer setting % = % is outside % to %', new.key, new.value, lo, hi;
  end if;
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists customer_settings_check on public.customer_settings;
create trigger customer_settings_check before insert or update on public.customer_settings
  for each row execute function public.check_customer_setting();

alter table public.customer_settings enable row level security;

-- A signed-in user may see their own assumptions (e.g. "assumes 24% tax"); nobody else's.
drop policy if exists "read own customer settings" on public.customer_settings;
create policy "read own customer settings" on public.customer_settings
  for select to authenticated using (customer_id = (select public.current_customer_id()));
