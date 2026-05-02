create extension if not exists pgcrypto;
create extension if not exists citext;

drop view if exists application_summary cascade;

drop table if exists document_generation_runs cascade;
drop table if exists document_versions cascade;
drop table if exists generated_documents cascade;
drop table if exists application_status_history cascade;
drop table if exists applications cascade;
drop table if exists job_tags cascade;
drop table if exists project_keywords cascade;
drop table if exists experience_keywords cascade;
drop table if exists user_projects cascade;
drop table if exists user_experiences cascade;
drop table if exists user_education cascade;
drop table if exists keywords cascade;
drop table if exists user_selected_tags cascade;
drop table if exists user_assigned_tags cascade;
drop table if exists jobs cascade;
drop table if exists job_sources cascade;
drop table if exists refresh_sessions cascade;
drop table if exists users cascade;
drop table if exists canonical_tags cascade;

drop function if exists upsert_application_status(uuid, text);
drop function if exists enforce_user_selected_tags() cascade;  -- cascade drops the trigger too
drop function if exists set_updated_at();
drop function if exists calculate_user_experience_years(uuid);
drop function if exists refresh_experience_years() cascade;

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table canonical_tags (
  tag_id uuid primary key default gen_random_uuid(),
  tag_name text not null unique,
  created_at timestamptz not null default now()
);

create table users (
  user_id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  password_hash text not null,
  full_name text not null,
  raw_job_title text not null default '',
  bio text,
  phone_number text,
  github_url text,
  linkedin_url text,
  notion_url text,
  email_verified_at timestamptz,
  email_verification_code_hash text,
  email_verification_code_salt text,
  email_verification_expires_at timestamptz,
  email_verification_sent_at timestamptz,
  email_verification_attempts integer not null default 0,
  cv_uploaded boolean not null default false,
  experience_years smallint not null default -1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table refresh_sessions (
  refresh_session_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  current_jti text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  revoke_reason text,
  rotated_at timestamptz,
  last_seen_at timestamptz,
  created_at timestamptz not null default now()
);

create table job_sources (
  source_id uuid primary key default gen_random_uuid(),
  source_name text not null unique,
  source_type text not null check (source_type in ('manual', 'api', 'crawler', 'rss')),
  base_url text,
  created_at timestamptz not null default now()
);

create table jobs (
  job_id uuid primary key default gen_random_uuid(),
  source_id uuid references job_sources(source_id) on delete set null,
  title text not null,
  company text not null,
  description text not null,
  location text,
  salary_range text,
  apply_url text,
  source_url text,
  external_job_key text,
  is_active boolean not null default true,
  stale_reason text,
  last_checked_at timestamptz,
  stale_detected_at timestamptz,
  posted_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table user_assigned_tags (
  user_id uuid not null references users(user_id) on delete cascade,
  tag_id uuid not null references canonical_tags(tag_id) on delete cascade,
  primary key (user_id, tag_id)
);

create table user_selected_tags (
  user_id uuid not null references users(user_id) on delete cascade,
  tag_id uuid not null references canonical_tags(tag_id) on delete cascade,
  primary key (user_id, tag_id)
);

-- education history (weak entity, owned by user)
create table user_education (
  education_id   uuid primary key default gen_random_uuid(),
  user_id        uuid not null references users(user_id) on delete cascade,
  institution    text not null,
  degree         text not null,
  degree_level   text not null check (degree_level in ('high_school', 'diploma', 'ug', 'pg', 'phd', 'other')),
  field_of_study text,
  start_date     date,
  end_date       date,            -- null = currently enrolled
  grade          text,
  description    text,
  tag_id         uuid not null references canonical_tags(tag_id) on delete restrict,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- shared keyword vocabulary; each row is a single normalized tech keyword (lowercased + trimmed)
create table keywords (
  keyword_id uuid primary key default gen_random_uuid(),
  keyword text not null unique,
  created_at timestamptz not null default now()
);

-- weak entity: experience belongs to a user, deletes with user
create table user_experiences (
  experience_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  company text not null,
  location text,
  role text not null,
  experience_type text not null check (experience_type in (
    'internship','freelance','full_time','part_time','unpaid_internship','advisor'
  )),
  start_date date not null,
  end_date date,
  description text,
  tag_id uuid references canonical_tags(tag_id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 5NF junction: experience -> shared keyword
create table experience_keywords (
  experience_id uuid not null references user_experiences(experience_id) on delete cascade,
  keyword_id uuid not null references keywords(keyword_id) on delete restrict,
  primary key (experience_id, keyword_id)
);

-- weak entity: project belongs to a user, deletes with user
create table user_projects (
  project_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  name text not null,
  description text,
  github_url text,
  demo_url text,
  tag_id uuid references canonical_tags(tag_id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 5NF junction: project -> shared keyword
create table project_keywords (
  project_id uuid not null references user_projects(project_id) on delete cascade,
  keyword_id uuid not null references keywords(keyword_id) on delete restrict,
  primary key (project_id, keyword_id)
);

create table job_tags (
  job_id uuid not null references jobs(job_id) on delete cascade,
  tag_id uuid not null references canonical_tags(tag_id) on delete cascade,
  primary key (job_id, tag_id)
);

create table applications (
  application_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  job_id uuid not null references jobs(job_id) on delete cascade,
  status text not null check (status in ('interested', 'applying', 'applied', 'response', 'placed')),
  current_cv_document_id uuid,
  current_cover_letter_document_id uuid,
  applied_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, job_id)
);

create table application_status_history (
  history_id uuid primary key default gen_random_uuid(),
  application_id uuid not null references applications(application_id) on delete cascade,
  previous_status text check (previous_status in ('interested', 'applying', 'applied', 'response', 'placed')),
  new_status text not null check (new_status in ('interested', 'applying', 'applied', 'response', 'placed')),
  changed_by uuid references users(user_id) on delete set null,
  changed_at timestamptz not null default now(),
  note text
);

create table generated_documents (
  document_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  job_id uuid references jobs(job_id) on delete cascade,
  application_id uuid references applications(application_id) on delete set null,
  document_type text not null check (document_type in ('cv', 'cover_letter')),
  title text not null,
  content text not null,
  content_format text not null default 'markdown' check (content_format in ('text', 'markdown', 'html', 'json', 'latex')),
  template_name text,
  generation_status text not null default 'draft' check (generation_status in ('draft', 'queued', 'generating', 'ready', 'failed', 'archived')),
  storage_bucket text,
  storage_path text,
  mime_type text,
  file_size_bytes bigint,
  rendered_content text,
  rendered_format text check (rendered_format in ('pdf', 'docx', 'html', 'markdown', 'latex', 'json', 'text')),
  rendered_storage_bucket text,
  rendered_storage_path text,
  rendered_mime_type text,
  rendered_file_size_bytes bigint,
  source_document_id uuid references generated_documents(document_id) on delete set null,
  based_on_version_id uuid,
  parent_document_id uuid references generated_documents(document_id) on delete set null,
  source_profile_snapshot jsonb,
  source_job_snapshot jsonb,
  generation_params jsonb,
  generation_error text,
  provider text,
  model_name text,
  prompt_version text,
  latest_version_number integer not null default 1,
  generation_source text not null check (generation_source in ('manual', 'ai', 'hybrid')),
  is_current boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table document_versions (
  version_id uuid primary key default gen_random_uuid(),
  document_id uuid not null references generated_documents(document_id) on delete cascade,
  version_number integer not null,
  content text not null,
  content_format text not null default 'markdown' check (content_format in ('text', 'markdown', 'html', 'json', 'latex')),
  rendered_content text,
  rendered_format text check (rendered_format in ('pdf', 'docx', 'html', 'markdown', 'latex', 'json', 'text')),
  storage_bucket text,
  storage_path text,
  mime_type text,
  file_size_bytes bigint,
  rendered_storage_bucket text,
  rendered_storage_path text,
  rendered_mime_type text,
  rendered_file_size_bytes bigint,
  source_profile_snapshot jsonb,
  source_job_snapshot jsonb,
  generation_params jsonb,
  generation_error text,
  provider text,
  model_name text,
  prompt_version text,
  created_at timestamptz not null default now(),
  unique (document_id, version_number)
);

alter table generated_documents
  add constraint generated_documents_based_on_version_fk
  foreign key (based_on_version_id) references document_versions(version_id) on delete set null;

alter table applications
  add constraint applications_current_cv_document_fk
  foreign key (current_cv_document_id) references generated_documents(document_id) on delete set null;

alter table applications
  add constraint applications_current_cover_letter_document_fk
  foreign key (current_cover_letter_document_id) references generated_documents(document_id) on delete set null;

create table document_generation_runs (
  generation_run_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  job_id uuid references jobs(job_id) on delete cascade,
  application_id uuid references applications(application_id) on delete set null,
  document_id uuid references generated_documents(document_id) on delete set null,
  document_type text not null check (document_type in ('cv', 'cover_letter')),
  status text not null check (status in ('queued', 'running', 'completed', 'failed', 'cancelled')),
  provider text,
  model_name text,
  prompt_version text,
  template_name text,
  source_profile_snapshot jsonb,
  source_job_snapshot jsonb,
  generation_params jsonb,
  output_summary jsonb,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists users_email_lower_key on users (lower(email::text));
create index if not exists refresh_sessions_user_id_idx on refresh_sessions (user_id);
create index if not exists refresh_sessions_expires_at_idx on refresh_sessions (expires_at);
create index if not exists refresh_sessions_revoked_at_idx on refresh_sessions (revoked_at);
create index if not exists jobs_posted_at_idx on jobs (posted_at desc);
create index if not exists jobs_source_id_idx on jobs (source_id);
create unique index if not exists jobs_source_url_key on jobs (source_url) where source_url is not null;
create unique index if not exists jobs_external_job_key_key on jobs (external_job_key) where external_job_key is not null;
create index if not exists user_assigned_tags_user_id_idx on user_assigned_tags (user_id);
create index if not exists user_assigned_tags_tag_id_idx on user_assigned_tags (tag_id);
create index if not exists user_selected_tags_user_id_idx on user_selected_tags (user_id);
create index if not exists user_selected_tags_tag_id_idx on user_selected_tags (tag_id);
create index if not exists job_tags_job_id_idx on job_tags (job_id);
create index if not exists job_tags_tag_id_idx on job_tags (tag_id);
create index if not exists applications_user_id_idx on applications (user_id);
create index if not exists applications_job_id_idx on applications (job_id);
create index if not exists application_status_history_application_id_idx on application_status_history (application_id);
create index if not exists application_status_history_changed_at_idx on application_status_history (changed_at desc);
create index if not exists generated_documents_user_id_idx on generated_documents (user_id);
create index if not exists generated_documents_job_id_idx on generated_documents (job_id);
create index if not exists generated_documents_application_id_idx on generated_documents (application_id);
create index if not exists generated_documents_status_idx on generated_documents (generation_status);
create unique index if not exists generated_documents_one_current_per_application_type
  on generated_documents (application_id, document_type)
  where is_current = true;
create index if not exists document_versions_document_id_idx on document_versions (document_id);
create index if not exists document_generation_runs_user_id_idx on document_generation_runs (user_id);
create index if not exists document_generation_runs_job_id_idx on document_generation_runs (job_id);
create index if not exists document_generation_runs_application_id_idx on document_generation_runs (application_id);
create index if not exists document_generation_runs_document_id_idx on document_generation_runs (document_id);
create index if not exists document_generation_runs_status_idx on document_generation_runs (status);
create index if not exists user_education_user_id_idx on user_education (user_id);
create index if not exists user_experiences_user_id_idx on user_experiences (user_id);
create index if not exists user_experiences_tag_id_idx on user_experiences (tag_id);
create index if not exists user_projects_user_id_idx on user_projects (user_id);
create index if not exists user_projects_tag_id_idx on user_projects (tag_id);
create index if not exists experience_keywords_keyword_id_idx on experience_keywords (keyword_id);
create index if not exists project_keywords_keyword_id_idx on project_keywords (keyword_id);
create index if not exists keywords_keyword_idx on keywords (keyword);

drop trigger if exists users_set_updated_at on users;
create trigger users_set_updated_at
before update on users
for each row execute function set_updated_at();

drop trigger if exists applications_set_updated_at on applications;
create trigger applications_set_updated_at
before update on applications
for each row execute function set_updated_at();

drop trigger if exists generated_documents_set_updated_at on generated_documents;
create trigger generated_documents_set_updated_at
before update on generated_documents
for each row execute function set_updated_at();

drop trigger if exists user_education_set_updated_at on user_education;
create trigger user_education_set_updated_at
before update on user_education
for each row execute function set_updated_at();

drop trigger if exists user_experiences_set_updated_at on user_experiences;
create trigger user_experiences_set_updated_at
before update on user_experiences
for each row execute function set_updated_at();

drop trigger if exists user_projects_set_updated_at on user_projects;
create trigger user_projects_set_updated_at
before update on user_projects
for each row execute function set_updated_at();

-- experience_years: auto-calculated from user_experiences
-- -1 = no experiences, 0 = < 1 yr, 1 = 1-2 yrs, N = N to N+1 yrs
create or replace function calculate_user_experience_years(p_user_id uuid)
returns smallint
language sql
stable
as $$
  select case
    when count(*) filter (where start_date is not null) = 0 then -1::smallint
    else greatest(0,
      (sum(
        extract(year  from age(coalesce(end_date, current_date), start_date)) * 12 +
        extract(month from age(coalesce(end_date, current_date), start_date))
      ) / 12)::smallint
    )
  end
  from user_experiences
  where user_id = p_user_id
    and start_date is not null;
$$;

create or replace function refresh_experience_years()
returns trigger
language plpgsql
as $$
begin
  update users
  set experience_years = calculate_user_experience_years(
    coalesce(new.user_id, old.user_id)
  )
  where user_id = coalesce(new.user_id, old.user_id);
  return coalesce(new, old);
end;
$$;

drop trigger if exists trg_experience_years_refresh on user_experiences;
create trigger trg_experience_years_refresh
after insert or update or delete on user_experiences
for each row execute function refresh_experience_years();

-- enforce_user_selected_tags trigger removed:
-- no limit on tag selection during onboarding; limit of 5 applied at job-search time only

create or replace function upsert_application_status(
  p_application_id uuid,
  p_new_status text
)
returns void
language plpgsql
as $$
declare
  v_previous_status text;
begin
  select status
  into v_previous_status
  from applications
  where application_id = p_application_id
  for update;

  if not found then
    raise exception 'application % not found', p_application_id;
  end if;

  update applications
  set status = p_new_status,
      updated_at = now()
  where application_id = p_application_id;

  if v_previous_status is distinct from p_new_status then
    insert into application_status_history (
      application_id,
      previous_status,
      new_status,
      changed_by,
      note
    ) values (
      p_application_id,
      v_previous_status,
      p_new_status,
      null,
      null
    );
  end if;
end;
$$;

create or replace view application_summary
with (security_invoker = true)
as
select
  a.application_id,
  a.user_id,
  u.full_name as user_full_name,
  u.email as user_email,
  a.job_id,
  j.title as job_title,
  j.company,
  j.location,
  j.salary_range,
  j.source_url,
  j.external_job_key,
  j.posted_at,
  a.status,
  a.applied_at,
  a.updated_at
from applications a
join users u on u.user_id = a.user_id
join jobs j on j.job_id = a.job_id;

alter view application_summary set (security_invoker = true);

-- seed search providers (idempotent)
insert into job_sources (source_name, source_type, base_url) values
  ('jsearch',  'api', 'https://jsearch.p.rapidapi.com'),
  ('adzuna',   'api', 'https://api.adzuna.com'),
  ('linkedin', 'api', 'https://jsearch.p.rapidapi.com')
on conflict (source_name) do nothing;

-- canonical tags seed (bundled into setup so one rerun is enough)
insert into canonical_tags (tag_name) values
  ('frontend'),
  ('backend'),
  ('fullstack'),
  ('mobile'),
  ('embedded-systems'),
  ('systems-programming'),
  ('devops'),
  ('cloud'),
  ('security'),
  ('testing'),
  ('software development'),
  ('ai-ml'),
  ('data-science'),
  ('data-engineering'),
  ('research'),
  ('automation'),
  ('product-management'),
  ('consulting'),
  ('technical-writing'),
  ('agile'),
  ('ui-ux'),
  ('product-design'),
  ('graphic-design'),
  ('motion-design'),
  ('video-editing'),
  ('content-creation'),
  ('photography'),
  ('3d-modelling'),
  ('game-development'),
  ('ar-vr'),
  ('robotics'),
  ('blockchain'),
  ('ios'),
  ('android'),
  ('electronics'),
  ('biotech'),
  ('fintech'),
  ('sales-growth'),
  ('operations'),
  ('hr-people'),
  ('legal-compliance')
on conflict (tag_name) do nothing;

alter table canonical_tags enable row level security;
alter table users enable row level security;
alter table refresh_sessions enable row level security;
alter table job_sources enable row level security;
alter table jobs enable row level security;
alter table user_assigned_tags enable row level security;
alter table user_selected_tags enable row level security;
alter table job_tags enable row level security;
alter table applications enable row level security;
alter table application_status_history enable row level security;
alter table generated_documents enable row level security;
alter table document_versions enable row level security;
alter table document_generation_runs enable row level security;
alter table user_education enable row level security;
alter table keywords enable row level security;
alter table user_experiences enable row level security;
alter table experience_keywords enable row level security;
alter table user_projects enable row level security;
alter table project_keywords enable row level security;

drop policy if exists canonical_tags_all on canonical_tags;
create policy canonical_tags_all on canonical_tags
for all
using (true)
with check (true);

drop policy if exists users_all on users;
create policy users_all on users
for all
using (true)
with check (true);

drop policy if exists refresh_sessions_all on refresh_sessions;
create policy refresh_sessions_all on refresh_sessions
for all
using (true)
with check (true);

drop policy if exists job_sources_all on job_sources;
create policy job_sources_all on job_sources
for all
using (true)
with check (true);

drop policy if exists jobs_all on jobs;
create policy jobs_all on jobs
for all
using (true)
with check (true);

drop policy if exists user_assigned_tags_all on user_assigned_tags;
create policy user_assigned_tags_all on user_assigned_tags
for all
using (true)
with check (true);

drop policy if exists user_selected_tags_all on user_selected_tags;
create policy user_selected_tags_all on user_selected_tags
for all
using (true)
with check (true);

drop policy if exists job_tags_all on job_tags;
create policy job_tags_all on job_tags
for all
using (true)
with check (true);

drop policy if exists applications_all on applications;
create policy applications_all on applications
for all
using (true)
with check (true);

drop policy if exists application_status_history_all on application_status_history;
create policy application_status_history_all on application_status_history
for all
using (true)
with check (true);

drop policy if exists generated_documents_all on generated_documents;
create policy generated_documents_all on generated_documents
for all
using (true)
with check (true);

drop policy if exists document_versions_all on document_versions;
create policy document_versions_all on document_versions
for all
using (true)
with check (true);

drop policy if exists document_generation_runs_all on document_generation_runs;
create policy document_generation_runs_all on document_generation_runs
for all
using (true)
with check (true);

-- TODO: tighten by ownership before exposing direct DB access. Backend connects as `postgres` (BYPASSRLS), so policies are enforced at FastAPI middleware layer for now.

drop policy if exists user_education_all on user_education;
create policy user_education_all on user_education for all using (true) with check (true);

drop policy if exists keywords_all on keywords;
create policy keywords_all on keywords
for all
using (true)
with check (true);

drop policy if exists user_experiences_all on user_experiences;
create policy user_experiences_all on user_experiences
for all
using (true)
with check (true);

drop policy if exists experience_keywords_all on experience_keywords;
create policy experience_keywords_all on experience_keywords
for all
using (true)
with check (true);

drop policy if exists user_projects_all on user_projects;
create policy user_projects_all on user_projects
for all
using (true)
with check (true);

drop policy if exists project_keywords_all on project_keywords;
create policy project_keywords_all on project_keywords
for all
using (true)
with check (true);
