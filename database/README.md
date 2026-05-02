# Database Setup

This project uses Supabase PostgreSQL directly with raw SQL.

## One-shot setup

Run `schema/setup.sql` in the Supabase SQL editor:

- [schema/setup.sql](./schema/setup.sql)

It resets the project objects it owns, recreates the backend-aligned schema, applies the job-tracking fields, seeds `job_sources`, seeds `canonical_tags`, prepares the generated-document tables for upcoming CV/cover-letter generation, creates the `application_summary` view, and enables bootstrap RLS policies.

## Connection string

Use the PostgreSQL connection string in `backend/.env` as `DATABASE_URL`.

If the password contains spaces or other reserved URL characters, URL-encode it first.

Examples:

- Space -> `%20`
- `#` -> `%23`
- `@` -> `%40`

Do not wrap the password in square brackets. The brackets in examples like `[YOUR-PASSWORD]` are placeholders only.

Example:

```text
DATABASE_URL=postgresql://postgres:my%20secret%20password@db.ytunhsgecrmkaurhcmwb.supabase.co:5432/postgres
```

## Best practice notes

- Keep the backend as a thin SQL execution layer.
- Prefer views and stored functions for reusable database logic.
- RLS is enabled in the base schema and bootstrap permissive policies are shipped for the current backend-only access model.
- Add RLS policies that match your auth model before exposing user-specific data.
