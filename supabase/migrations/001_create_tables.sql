-- Chatty Friend Supabase Schema
-- Run this in your Supabase SQL Editor
-- https://supabase.com/dashboard/project/YOUR_PROJECT/sql

-- ============================================
-- DEVICES TABLE
-- Stores device configuration, encrypted secrets, and sync state
-- ============================================

create table if not exists devices (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid references auth.users(id) on delete cascade not null,
    name text not null,
    location text,
    
    -- Configuration stored as JSONB for flexibility
    config_data jsonb default '{}'::jsonb,
    
    -- Secrets are encrypted client-side before storage
    secrets_encrypted text,
    secrets_passphrase_hint text,
    
    -- Version tracking
    current_version text,
    target_version text,
    
    -- Sync flags (set by admin/web UI, cleared by device after processing)
    config_pending boolean default false,
    upgrade_pending boolean default false,
    
    -- Timestamps
    last_seen timestamp with time zone,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

-- Index for faster lookups by owner
create index if not exists devices_owner_id_idx on devices(owner_id);

-- Enable Row Level Security
alter table devices enable row level security;

-- RLS Policy: Users can only see and manage their own devices
create policy "Users can manage own devices" on devices
    for all 
    using (auth.uid() = owner_id)
    with check (auth.uid() = owner_id);

-- Automatically set owner_id on insert
create or replace function set_device_owner()
returns trigger as $$
begin
    new.owner_id := auth.uid();
    return new;
end;
$$ language plpgsql security definer;

create trigger set_device_owner_trigger
    before insert on devices
    for each row
    execute function set_device_owner();

-- Automatically update updated_at on update
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at := now();
    return new;
end;
$$ language plpgsql;

create trigger devices_updated_at_trigger
    before update on devices
    for each row
    execute function update_updated_at();


-- ============================================
-- DEVICE_ACTIVITY TABLE
-- Stores conversation usage statistics for tracking and billing
-- ============================================

create table if not exists device_activity (
    id uuid primary key default gen_random_uuid(),
    device_id uuid references devices(id) on delete cascade not null,
    
    -- Session timing
    session_start timestamp with time zone,
    session_end timestamp with time zone default now(),
    
    -- Usage metrics
    message_count integer default 0,
    cost decimal(10,4) default 0,
    
    -- Metadata for future expansion
    metadata jsonb default '{}'::jsonb,
    
    created_at timestamp with time zone default now()
);

-- Index for faster lookups by device
create index if not exists device_activity_device_id_idx on device_activity(device_id);
create index if not exists device_activity_session_end_idx on device_activity(session_end);

-- Enable Row Level Security
alter table device_activity enable row level security;

-- RLS Policy: Users can only see activity for their own devices
create policy "Users can view own device activity" on device_activity
    for select
    using (
        device_id in (
            select id from devices where owner_id = auth.uid()
        )
    );

-- RLS Policy: Users can insert activity for their own devices
create policy "Users can insert own device activity" on device_activity
    for insert
    with check (
        device_id in (
            select id from devices where owner_id = auth.uid()
        )
    );


-- ============================================
-- HELPFUL VIEWS
-- ============================================

-- View to get device summary with activity stats
create or replace view device_summary as
select 
    d.id,
    d.name,
    d.location,
    d.current_version,
    d.target_version,
    d.config_pending,
    d.upgrade_pending,
    d.last_seen,
    d.created_at,
    coalesce(sum(a.message_count), 0) as total_messages,
    coalesce(sum(a.cost), 0) as total_cost,
    count(a.id) as session_count,
    max(a.session_end) as last_session
from devices d
left join device_activity a on d.id = a.device_id
group by d.id;


-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to flag a device for config update
create or replace function mark_config_pending(p_device_id uuid)
returns void as $$
begin
    update devices 
    set config_pending = true, updated_at = now()
    where id = p_device_id 
    and owner_id = auth.uid();
end;
$$ language plpgsql security definer;

-- Function to flag a device for upgrade
create or replace function mark_upgrade_pending(p_device_id uuid, p_target_version text)
returns void as $$
begin
    update devices 
    set upgrade_pending = true, 
        target_version = p_target_version,
        updated_at = now()
    where id = p_device_id 
    and owner_id = auth.uid();
end;
$$ language plpgsql security definer;

-- Function to get usage stats for a time period
create or replace function get_device_usage(
    p_device_id uuid,
    p_start_date timestamp with time zone default now() - interval '30 days',
    p_end_date timestamp with time zone default now()
)
returns table(
    total_messages bigint,
    total_cost decimal,
    session_count bigint,
    avg_messages_per_session decimal,
    avg_cost_per_session decimal
) as $$
begin
    return query
    select 
        coalesce(sum(a.message_count), 0)::bigint as total_messages,
        coalesce(sum(a.cost), 0) as total_cost,
        count(a.id) as session_count,
        coalesce(avg(a.message_count), 0)::decimal as avg_messages_per_session,
        coalesce(avg(a.cost), 0) as avg_cost_per_session
    from device_activity a
    join devices d on a.device_id = d.id
    where a.device_id = p_device_id
    and d.owner_id = auth.uid()
    and a.session_end between p_start_date and p_end_date;
end;
$$ language plpgsql security definer;


-- ============================================
-- GRANT PERMISSIONS
-- ============================================

-- Grant access to authenticated users
grant usage on schema public to authenticated;
grant all on devices to authenticated;
grant all on device_activity to authenticated;
grant select on device_summary to authenticated;

