# Jobful

End-to-end autonomous job application system. Upload your CV, pick skill tags, search live listings, track applications, and generate tailored documents — all in one place.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router) + Tailwind CSS + Shadcn UI |
| Backend | FastAPI (Python) — no ORM, raw SQL only |
| Database | Supabase (PostgreSQL) |
| AI / CV parsing | Groq LLM (`llama-3.3-70b-versatile`) via LangChain |
| Job sources | JSearch (RapidAPI) + Adzuna |
| Auth | Custom JWT — access + refresh token rotation |
| PDF generation | Playwright Chromium (HTML → PDF) |
| Storage | Supabase Storage bucket (`generated-documents`) |
| Deployment | Single Docker image → Railway · DB + Storage → Supabase |

---

## Features

- **Email auth** — register, verify code, login, refresh-token rotation, logout
- **CV ingestion** — upload PDF → PyMuPDF extracts text → Groq returns structured education / experience / project data → user reviews and confirms before any DB write
- **5NF profile** — normalized education, experiences, projects, and a shared keyword vocabulary per user
- **Tag system** — 41 canonical skill tags; auto-suggested from CV data; user selects up to 5 for job search
- **Live job search** — queries JSearch + Adzuna per tag; deduplicates across sources; groups results by recency (24h / 7d / older)
- **Two-tier job filter** — algorithmic tier (age, region, seniority, skill overlap) + Groq AI gate for borderline results; each card shows why it matched
- **Application tracker** — track → applying → applied → response → placed; full status history in DB
- **Stale-job detection** — parallel HTTP freshness checks (cached 1h) on every dashboard load; clickable notification dropdown in header that scrolls to the offending job
- **Dashboard** — profile snapshot, tracked roles, application stats per tag, instant in-place updates on track/status-change
- **Application workspace** (`/applications/[id]`) — generate tailored CV + cover letter via Groq, edit HTML in side-by-side editor, compile to PDF via Playwright, upload to Supabase Storage, download
- **Regenerate flow** — old PDF deleted from Supabase before new one created (no archive bloat)

---

## File Structure

```
Jobful/
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── controllers/        # request handlers
│   │   ├── dependencies/       # auth + common DI
│   │   ├── routes/             # FastAPI routers
│   │   └── schemas/            # Pydantic models
│   ├── core/
│   │   ├── config.py
│   │   ├── limiter.py          # rate limiting
│   │   └── security.py         # JWT helpers
│   ├── db/
│   │   ├── connection.py       # psycopg2 via Supabase pooler
│   │   ├── executor.py
│   │   ├── query_loader.py
│   │   └── queries/            # .sql files (auth / cv / jobs / onboarding)
│   ├── services/               # business logic
│   └── utils/
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # landing
│   │   ├── login/
│   │   ├── register/
│   │   ├── onboarding/         # profile editor + CV upload
│   │   ├── dashboard/          # tracked jobs + profile snapshot
│   │   └── jobs/               # live search + tracker
│   ├── components/
│   │   ├── auth/
│   │   ├── onboarding/
│   │   └── site-header.tsx
│   ├── context/auth-context.tsx
│   └── services/               # API client (auth.ts, api.ts)
├── database/
│   ├── schema/
│   │   └── setup.sql           # single rerunnable file — drop + recreate + seed
│   ├── migrations/             # incremental migration files
│   ├── functions/
│   ├── queries/
│   ├── seeds/
│   └── views/
├── docs/
│   └── architecture.md
├── scripts/
│   └── setup.ps1
├── run_all.ps1                 # starts backend + frontend together
└── workflow.md                 # full system spec + implementation log
```

---

## Initial Setup

### 1. Database (Supabase)

Run `database/schema/setup.sql` in the **Supabase SQL editor**. This file is drop-and-recreate — rerun it any time you need a clean slate. It handles:

- Extensions (`pgcrypto`, `citext`)
- All tables in dependency order
- Indexes, triggers, and stored functions
- `job_sources` seed (jsearch / adzuna / linkedin)
- `canonical_tags` seed (41 tags)
- Bootstrap RLS policies

> **Connection note:** Use the **transaction pooler** URL (`aws-1-ap-southeast-2.pooler.supabase.com:6543`), not the direct host. The direct host is IPv6-only and unreachable from Windows libpq.
>
> Free-tier projects auto-pause after ~1 week. Restore at supabase.com/dashboard before running.

### 2. Backend environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require
APP_DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require

JWT_SECRET_KEY=<run: openssl rand -hex 32>
JWT_ISSUER=jobful-api
JWT_AUDIENCE=jobful-client
JWT_ACTIVE_KID=v1

GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

RAPIDAPI_KEY=...
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...

# Supabase Storage (PDF uploads)
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...      # service_role, NOT anon
SUPABASE_STORAGE_BUCKET=generated-documents

# SMTP (verification emails)
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM_EMAIL=...
SMTP_USE_TLS=true
```

> **Storage bucket:** Create a private bucket named `generated-documents` in Supabase dashboard → Storage before first PDF compile.

### 3. Frontend environment

Copy `frontend/.env.local.example` to `frontend/.env.local` and set `NEXT_PUBLIC_API_URL` to your backend URL.

### 4. Install dependencies

```bash
# backend (uses uv)
cd backend && uv sync

# frontend
cd frontend && npm install
```

---

## Running Locally

**Windows — one command:**

```powershell
.\run_all.ps1
```

Kills any leftover node/python processes, syncs backend deps, then starts both servers:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |

**Or start separately:**

```bash
# backend
cd backend
uv run uvicorn main:app --reload --reload-dir api --reload-dir core --reload-dir db --reload-dir services --reload-dir utils --host 0.0.0.0 --port 8000

# frontend
cd frontend
npm run dev
```

---

## User Flow

1. **Register** → email verification code sent
2. **Verify** → account created, tokens issued
3. **Onboarding** → fill profile, upload CV (parsed live, confirmed on save), pick skill tags
4. **Jobs** → select tags, search live listings, filter by type / location / salary, track roles
5. **Dashboard** → view tracked applications, update statuses, monitor stale listings

---
