create extension if not exists "pgcrypto";

create table if not exists users (
  user_id uuid primary key default gen_random_uuid(),
  email text unique not null,
  username text,
  password text not null,
  created_at timestamptz default now()
);
