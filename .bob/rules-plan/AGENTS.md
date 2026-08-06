# Project Architecture Rules (Plan Mode)

## Non-Obvious Architectural Constraints

- **RLS is the primary tenant-isolation layer** — application-level `tenant_id` filtering is a second line of defence, not the first; schema design must enable `SET LOCAL app.current_tenant_id` before every query
- **JSONB rule storage is intentional** — `Pricing_Rules.condition` stores the full rule expression as JSONB so rules can be changed without DB migrations; do NOT normalise rule conditions into columns
- **The simulation endpoint must be stateless** (F-6) — it receives hypothetical competitor prices in the request body and returns the computed price without writing to DB; plan a separate route, not a flag on the save endpoint
- **Atomicity boundary** (N-2): `Price_Histories` insert + `Audit_Logs` insert + Redis queue push must be treated as one unit — if LINE queue push fails, the DB transaction must still commit (outbox pattern recommended)
- **Redis serves three distinct roles**: (1) Yahoo! Shopping API rate-limit token bucket, (2) Celery/RQ broker for LINE notification jobs, (3) cache for tenant policy metadata — use separate Redis DB indices (0/1/2) to avoid key collisions
- **Render.com free tier spins down after inactivity** — the crawl worker and the API server cannot be the same process if deploying on Render free; plan separate services or use GitHub Actions as the scheduler to avoid keep-alive requirements
- **`Audit_Logs` must be immutable at the DB level** — add a PostgreSQL trigger or application-level constraint to block UPDATE/DELETE on this table; do not rely on application code alone
- **Yahoo! Shopping API integration** — crawler service must use `app/services/yahoo.py` (`YahooShoppingClient`); `YAHOO_CLIENT_ID` is passed as `appid` query param; response hits are parsed from the `hits` array with fields `name`, `price`, `url`, `code`, `seller.name`, `image.medium`
- **`yahoo_item_code` is the stable competitor polling key** — stored in `competitor_products.yahoo_item_code` (UNIQUE); used as the identifier for periodic API polling cycles
