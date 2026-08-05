# Project Coding Rules (Agent Mode)

## Non-Obvious Implementation Constraints

- **asyncpg driver is mandatory** — `DATABASE_URL` uses `postgresql+asyncpg://`; using `psycopg2` (sync) will break the async SQLAlchemy engine
- **JWT `tenant_id` claim must be extracted in every route** — use a FastAPI dependency (`get_current_tenant`) that reads `tenant_id` from the decoded token and sets a session-level Postgres variable (`SET LOCAL app.current_tenant_id = ...`) for RLS enforcement
- **Rule evaluation is a pure function** — `evaluate_rule(rule_json, competitor_prices, cost, min_margin) -> int` — keep side-effect-free so the simulation endpoint (F-6) can call it without writing to DB
- **Defensive price floor** = `cost + min_margin_amount`; never return a recommended price below this regardless of rule output
- **`Price_Histories` is append-only** — no update/upsert; always `INSERT` a new snapshot row with `recorded_at = now()`
- **`Audit_Logs` write must be in the same transaction** as `Price_Histories` insert — use `async with session.begin()` and commit both atomically
- **LINE notify is async** — push to Redis queue after transaction commit; do not `await` LINE HTTP call inside the route handler
- **Rakuten API throttle** — wrap crawler calls with a token-bucket decorator; the bucket capacity and refill rate must be configurable via env var, not hardcoded
- **RBAC enforcement** — `VIEWER` role must receive 403 on any mutating endpoint; enforce in the dependency layer, not in each route