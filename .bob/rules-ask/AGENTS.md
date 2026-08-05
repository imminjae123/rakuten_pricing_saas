# Project Documentation Context (Ask Mode)

## Non-Obvious Context

- **The entire codebase is spec-only** (`rakuten_pricing_saas_requirements.md`) — there is no source code; all implementation questions must reference that document
- **"Rule Engine" is not a library** — it is a custom Python function that parses JSONB conditions and applies arithmetic; no external rule-engine dependency is planned
- **`Product_Mappings` is a bridge table** between `My_Products` (own shop) and `Competitor_Products` (Rakuten item codes) — it is 1:N from own product to competitor, not true M:M
- **Cost and margin data lives only in `My_Products`** — `Competitor_Products` has no cost field; this distinction is security-critical (tenant isolation)
- **Two separate crawl triggers are planned**: GitHub Actions (simplest, free) **and** Celery beat — the spec leaves the choice open; GitHub Actions is preferred for zero-infrastructure cost
- **LINE notification fires on two distinct events only** (spec F-9): (a) new historical price low detected, (b) rule engine outputs a recommended price — not on every crawl cycle