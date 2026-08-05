# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Status
Pre-implementation — only the spec (`rakuten_pricing_saas_requirements.md`) and `.env.example` exist. No source code yet.

## Planned Stack
- **Language / Framework:** Python 3 + FastAPI (async preferred over sync routes)
- **ORM:** SQLAlchemy (async flavour — `asyncpg` driver shown in `.env.example`)
- **DB:** PostgreSQL (Neon or Supabase free tier) — JSONB for rule storage, RLS for tenant isolation
- **Cache / Queue:** Redis (Upstash free tier) — rate-limit control, task queue state, tenant-policy cache
- **Worker:** Celery or RQ (background rule evaluation + LINE notification dispatch)
- **Scheduler:** GitHub Actions cron **or** APScheduler/Celery beat (hourly/daily crawl trigger)
- **Deploy:** Render.com / Fly.io / Railway (free tier — no persistent process assumed on Render)

## Environment Variables (from `.env.example`)
```
DATABASE_URL=postgresql+asyncpg://...   # asyncpg driver — must match SQLAlchemy async engine
REDIS_URL=redis://localhost:6379/0
RAKUTEN_APPLICATION_ID=
LINE_CHANNEL_ACCESS_TOKEN=
SECRET_KEY=                             # JWT signing key
APP_ENV=development
PORT=8000
```

## Critical Architecture Constraints

### Multi-Tenancy — tenant isolation is a hard requirement
- **Every** DB query must filter by the authenticated user's `tenant_id` — no cross-tenant data leakage
- Recommended approach: PostgreSQL Row-Level Security (RLS) + SQLAlchemy session-level `SET LOCAL app.current_tenant_id`
- `My_Products` cost/margin data is the most sensitive column — extra care needed in serialization

### Rule Engine
- Rules are stored as **JSONB** in `Pricing_Rules.condition` — do not flatten to columns
- Rule evaluation order matters: compute `recommended_price` → check minimum margin → apply defensive price floor
- Minimum defensive price = `cost + min_margin_amount` — never recommend below this floor
- Provide a simulation endpoint (`POST /rules/{id}/simulate`) **before** save — required by spec (F-6)

### Data Pipeline — Rakuten API Rate Limiting
- Rakuten `IchibaItem/Search` API has a **per-second call limit** — implement Token Bucket or sleep-based throttle inside the crawler
- Crawl results must be written as **time-series snapshots** to `Price_Histories` (append-only, never UPDATE)

### Audit Log — Append-Only
- `Audit_Logs` table is immutable: no UPDATE or DELETE endpoints, no soft-delete
- Every rule change + every rule-engine firing must produce one audit row in the same DB transaction as the price recommendation save (atomicity — N-2)

### Notification
- LINE push is dispatched **after** the audit log commit, queued via Redis/Celery — not inline in the HTTP request
- Triggered only on: (a) new all-time low detected, (b) recommended price computed by rule engine

## Key DB Models
`Tenants` → `Users` (RBAC: OWNER / MANAGER / VIEWER) → `My_Products` → `Product_Mappings` (bridge) → `Competitor_Products`
`Pricing_Rules` (JSONB condition) → `Price_Histories` (time-series) → `Audit_Logs` (append-only)