# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Status
In development — spec (`yahoo_pricing_saas_requirements.md`) and initial source files exist.
External API: **Yahoo! Japan Shopping API v3**.

## Planned Stack

### Backend
- **Language / Framework:** Python 3 + FastAPI (async preferred over sync routes)
- **ORM:** SQLAlchemy (async flavour — `asyncpg` driver shown in `.env.example`)
- **DB:** PostgreSQL (Neon or Supabase free tier) — JSONB for rule storage, RLS for tenant isolation
- **Cache / Queue:** Redis (Upstash free tier) — rate-limit control, task queue state, tenant-policy cache
- **Worker:** Celery or RQ (background rule evaluation + LINE notification dispatch)
- **Scheduler:** GitHub Actions cron **or** APScheduler/Celery beat (hourly/daily crawl trigger)
- **Deploy:** Render.com / Fly.io / Railway (free tier — no persistent process assumed on Render)

### Frontend (served by FastAPI — no separate build step)
- **Template Engine:** Jinja2 (FastAPI built-in via `Jinja2Templates`) — renders HTML server-side
- **Dynamic UI / Async Communication:** HTMX — partial page updates via `hx-get` / `hx-post` attributes; no custom JS required for standard CRUD flows
- **CSS Framework:** Tailwind CSS (CDN `<script>` tag — zero build tooling, no Node.js required)
- **Charts:** Chart.js (CDN) — competitor price-history timeline and recommended-price trend graphs

**Rationale:** Eliminates Node.js / React build pipelines entirely.  The FastAPI process serves both the JSON API (`/api/v1/...`) and the HTML UI (`/ui/...`) from a single Render.com free-tier dyno.  HTMX endpoints return HTML fragments; JSON API endpoints remain untouched for future mobile/external consumers.

## Environment Variables (from `.env.example`)
```
DATABASE_URL=postgresql+asyncpg://...   # asyncpg driver — must match SQLAlchemy async engine
REDIS_URL=redis://localhost:6379/0
YAHOO_CLIENT_ID=                        # Yahoo! Japan Shopping API v3 client ID
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

### Data Pipeline — Yahoo! Shopping API Rate Limiting
- Yahoo! Shopping API v3 endpoint: `https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch`
- Authentication: `appid=<YAHOO_CLIENT_ID>` query parameter (no OAuth for item search)
- Implement Token Bucket or sleep-based throttle inside the crawler to respect API rate limits
- Crawl results must be written as **time-series snapshots** to `Price_Histories` (append-only, never UPDATE)

### Audit Log — Append-Only
- `Audit_Logs` table is immutable: no UPDATE or DELETE endpoints, no soft-delete
- Every rule change + every rule-engine firing must produce one audit row in the same DB transaction as the price recommendation save (atomicity — N-2)

### Notification
- LINE push is dispatched **after** the audit log commit, queued via Redis/Celery — not inline in the HTTP request
- Triggered only on: (a) new all-time low detected, (b) recommended price computed by rule engine

### Frontend — Architecture Constraints
- HTML UI routes live under `/ui/...`; they are **separate from** the JSON API routes under `/api/v1/...`
- Jinja2 templates reside in `app/templates/`; static files (none expected — all via CDN) in `app/static/`
- HTMX partial-update endpoints must return **HTML fragments only** (not full pages); use a shared `_base.html` layout template
- Tailwind CSS and Chart.js are loaded via CDN `<script>`/`<link>` tags in `_base.html` — **do not add a `package.json`, `node_modules/`, or any JS build config to this repository**
- JWT auth for UI: store access token in an `httpOnly` cookie (set by `/ui/auth/login`); the HTMX fragments read it automatically — do not expose the token in `localStorage` or URL params
- HTMX requests that require auth must include `HX-Request: true` header; server validates the cookie-based JWT before returning the fragment, same `get_current_user` dependency as the JSON API
- Chart.js data is fetched via a dedicated lightweight JSON endpoint (`GET /api/v1/histories/...`) called from a minimal inline `<script>` block inside the chart template fragment — this is the **only** place custom JS is permitted

## Key DB Models
`Tenants` → `Users` (RBAC: OWNER / MANAGER / VIEWER) → `My_Products` → `Product_Mappings` (bridge) → `Competitor_Products`
`Pricing_Rules` (JSONB condition) → `Price_Histories` (time-series) → `Audit_Logs` (append-only)

## External API Reference
- **Yahoo! Shopping API v3 itemSearch:**
  `GET https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch?appid=<id>&query=<keyword>&results=10&sort=-score`
- Response key fields per hit: `name`, `price`, `url`, `code`, `seller.name`, `image.medium`
- Client implementation: `app/services/yahoo.py` — `YahooShoppingClient` (async context manager)
