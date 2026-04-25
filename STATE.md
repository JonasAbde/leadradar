# LeadRadar State
## Updated: 2026-04-24 08:30 CEST
## Phase: 0 — Audit Complete, Awaiting Build Direction

---

## Current Status
- App: Running at http://57.128.215.250:8000
- Repo: Clean, main branch pushed to GitHub
- DB: SQLite, `data/leadradar.db` active, `leadradar.db` orphaned
- Tests: None
- Stripe: Not configured (no account)
- SMTP: Not configured (no credentials)
- Domain: Not purchased
- HTTPS: Not enabled

---

## Phase 1+2: CVR ENRICHMENT API ✅ DONE
Priority: HIGHEST | Impact: Data accuracy + lead value
- cvrapi.dk integration built and tested
- Auto-enrichment on every new lead during scrape
- Fields added: phone, email, CVR, address, owner, industry, employees
- DB migration: 12 new columns on leads table
- Tested: 3/3 leads enriched successfully
- Commits: 9d5b804, 59ee3f4

## Phase 3: CRM Integration ✅ DONE
Priority: HIGH | Impact: Product stickiness
- Chunk 1 ✅: CRM abstraction layer (mock provider, models, migrations)
- Chunk 2 ✅: HubSpot adapter (env token, idempotency, no hardcoded secrets)
- Chunk 3 ✅: Sync queue/worker (retry, backoff, resumable)
- Chunk 4 ✅: Dashboard UI (CRM buttons, status badges, settings)
- Chunk 5 ✅: Tests (mock integration, idempotency, lint)
- Commits: 42a45a4, eebf1dc, 47c0527

## Phase 3b: Real-Time Alerts ✅ DONE
Priority: HIGH | Impact: Product stickiness
- Chunk 1 ✅: Alert DB model + migration
- Chunk 2 ✅: Alert dispatch engine
- Chunk 3 ✅: Auto-trigger on new lead
- Chunk 4 ✅: Dashboard UI
- Chunk 5 ✅: API endpoints + tests
- Commits: b3a86b6, 27d2508, cedfc75, b0527af, 94482d5

## Phase 3c: Real Data Sources ✅ IN PROGRESS
Priority: CRITICAL | Impact: Dashboard emptiness = churn
- TED EU tenders: BLOCKED by Cloudflare/JS rendering. Need XML bulk API or headless browser.
- RSS Presets ✅: Version2.dk, Ingeniøren, Berlingske Business — live, returns 10+ leads per scrape
- Next: Test with real user flow, add more feeds

## Phase 4: Payments
Priority: HIGH | Impact: Revenue
- Stripe checkout + webhooks
- Blocked: Needs Stripe account (Jonas)

## Phase 5: CRM Integration
Priority: MEDIUM | Impact: Stickiness
- HubSpot/Pipedrive API sync
- Blocked: None, but Phase 1+2 first

## Phase 6: PostgreSQL
Priority: MEDIUM | Impact: Scale
- Replace SQLite with PostgreSQL
- Blocked: Needs Jonas to choose Supabase vs self-host

---

## Last Action
- Phase 1 audit completed
- Research on competitors, data sources, pricing completed
- BUILD_PROTOCOL.md created

## Next Action (Pending Jonas)
Choose Phase 1, 2, or 3 to start building.

---

## Dual SQLite Database Problem

There are two SQLite database files in the project root:

### `data/leadradar.db` (ACTIVE)
- Path: `./data/leadradar.db`
- Configured via `DATABASE_URL=sqlite:///./data/leadradar.db` in `.env`
- This is the production database used by the running application
- All migrations (001-005) have been applied to this file
- Contains all user data, leads, sources, alerts, etc.

### `leadradar.db` (ORPHANED)
- Path: `./leadradar.db` (project root)
- Legacy database from initial setup before `data/` directory was created
- Original `DATABASE_URL` pointed to `sqlite:///./leadradar.db`
- Contains 1 user account but no migrated schema
- **No longer connected to the application**

### Resolution
- The orphan database is being relocated to `data/leadradar_legacy.db` for safekeeping.
- If data from the orphan is needed, it can be inspected with `sqlite3 data/leadradar_legacy.db` and manually migrated.
- Future deployments will only use `data/leadradar.db`.

### Migration Steps (if needed)
```bash
# Inspect orphan database
sqlite3 data/leadradar_legacy.db ".tables"
sqlite3 data/leadradar_legacy.db "SELECT * FROM users;"

# If you need to merge data, copy specific tables or records manually
# The active DB (data/leadradar.db) is the source of truth.
```
