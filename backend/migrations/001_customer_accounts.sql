-- Minimal account database. Repository source, file paths, and scan results are
-- intentionally excluded so a hosted account database cannot become a source
-- code archive. Supabase Auth stores credentials and refresh-token sessions.
create table if not exists public.customer_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  account_status text not null default 'active' check (account_status in ('active', 'deletion_pending'))
);

alter table public.customer_profiles enable row level security;
revoke all on public.customer_profiles from anon;
grant select on public.customer_profiles to authenticated;
drop policy if exists "customers can read their own profile" on public.customer_profiles;
create policy "customers can read their own profile"
  on public.customer_profiles for select to authenticated using (auth.uid() = user_id);

-- Profile rows are created by a trusted trigger, never by a client-supplied role.
create or replace function public.create_customer_profile()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.customer_profiles (user_id) values (new.id)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_profile on auth.users;
create trigger on_auth_user_created_profile
  after insert on auth.users for each row execute procedure public.create_customer_profile();

-- A deletion request stores only the account identifier and timestamp. The
-- account identity is erased when the request is completed by the operator.
create table if not exists public.account_deletion_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  requested_at timestamptz not null default now(),
  status text not null default 'pending' check (status in ('pending', 'completed'))
);
alter table public.account_deletion_requests enable row level security;
revoke all on public.account_deletion_requests from anon;
grant select on public.account_deletion_requests to authenticated;
drop policy if exists "customers can view their deletion requests" on public.account_deletion_requests;
create policy "customers can view their deletion requests"
  on public.account_deletion_requests for select to authenticated using (auth.uid() = user_id);
drop policy if exists "customers can request their own account deletion" on public.account_deletion_requests;
create policy "customers can request their own account deletion"
  on public.account_deletion_requests for insert to authenticated
  with check (auth.uid() = user_id and status = 'pending');

-- One open request per account avoids accidental duplicate submissions while
-- leaving an operator able to mark a request complete before a later request.
create unique index if not exists one_pending_deletion_request_per_customer
  on public.account_deletion_requests (user_id) where status = 'pending';

-- Keep direct client inserts disabled. This small RPC derives the user from the
-- verified Supabase session and always creates a pending request, so a browser
-- cannot mark its own request completed or target another customer's account.
revoke insert on public.account_deletion_requests from authenticated;
create or replace function public.request_account_deletion()
returns uuid language plpgsql security definer set search_path = '' as $$
declare
  request_id uuid;
  requesting_user uuid := auth.uid();
begin
  if requesting_user is null then
    raise exception 'Sign in to request account deletion';
  end if;
  insert into public.account_deletion_requests (user_id, status)
  values (requesting_user, 'pending')
  on conflict (user_id) where status = 'pending' do nothing
  returning id into request_id;
  if request_id is null then
    select id into request_id from public.account_deletion_requests
      where user_id = requesting_user and status = 'pending';
  end if;
  return request_id;
end;
$$;
revoke all on function public.request_account_deletion() from public, anon;
grant execute on function public.request_account_deletion() to authenticated;

-- No client update/delete grant: only a trusted operator workflow completes
-- deletion after verifying the request and backing up the audit trail as needed.
