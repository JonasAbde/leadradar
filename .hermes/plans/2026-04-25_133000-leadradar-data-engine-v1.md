# LeadRadar Data Engine v1 — Implementation Plan

**Date:** 2026-04-25 13:30 CEST
**Author:** Hermes (Ops)
**Status:** Planning — ready for autonomous execution
**Workspace:** `/home/ubuntu/leadradar`

---

## Goal

Build LeadRadar Data Engine v1: A production-grade tender data pipeline that delivers real, relevant, deduplicated Danish leads to users on day one.

## Current Context

| Component | Status | Notes |
|---|---|---|
| **TED API endpoint** | `POST https://api.ted.europa.eu/v3/notices/search` | Verified — returns 200 |
| **TED query syntax** | Expert search string format | `buyer-country='DNK' AND classification-cpv IN (90910000 ...)` |
| **TED API spec** | Downloaded | `scripts/ted_api_spec.yaml` |
| **Existing scraper** | `app/ted_scraper.py` | Broken — uses Playwright, returns 0 |
| **Spike test** | `scripts/test_ted_api.py` | Exists but broken payload + wrong URL |
| **Auth, dashboard, CVR, CRM, alerts** | ✅ Built | Framework ready |
| **DB** | `data/leadradar.db` | Active, 8 users, 3 leads (test data) |
| **Orphaned DB** | `leadradar.db` | 1 user (test@rendetalje.dk) |
| **Stripe** | ⏸ Blocked | Needs account + credentials |
| **SMTP** | ⏸ Blocked | Needs credentials |
| **Domain/HTTPS** | ⏸ Blocked | Needs domain purchase |

### Known Technical Facts

- **Country code:** `'DNK'` (ISO 3166-1 alpha-3)
- **CPV field name:** `classification-cpv`
- **CPV query syntax:** `classification-cpv IN (90910000 90911000 ...)` — space-separated, no commas
- **Response fields:** `notice-identifier`, `publication-number`, `notice-type`, `buyer-country`, `classification-cpv`, `publication-date`, `deadline-receipt-tender-date`
- **Pagination:** `limit` (max 250), `page`
- **Scope:** `ACTIVE` / `LATEST` / `ALL`
- **Idempotency key:** `notice-identifier` or `publication-number` (format: `XXXXXX-YYYY`)

### Architecture

```
User → (chooses pack) → Source → TEDTenderProvider → API → Normalize → Dedup → Score → Save as Lead → Dashboard
```

---

## Proposed Approach

Build incrementally via 10 autonomous chunks. Each chunk is atomic: commit + test + STATE.md update before next. No blocking questions unless money/account/secrets needed.

### CPV Codes by Vertical Pack

| Pack | CPV Codes | Rationale |
|---|---|---|
| **Cleaning/Facility** | 90910000 (Cleaning services), 90911000 (Window cleaning), 90911200 (Building cleaning), 90911300 (Office cleaning), 90919200 (Cleaning + maintenance), 50000000 (Repair/maintenance), 50800000 (Maintenance/repair of building installations) | Core cleaning + facility management |
| **IT/Software** | 72000000 (IT services), 72100000 (Hardware consulting), 72200000 (Software services), 72210000 (Programming), 72220000 (Systems consulting), 72230000 (Custom software), 72240000 (IT systems management), 72260000 (IT support), 72270000 (Network services), 72300000 (IT equipment) | Full IT service spectrum |
| **Construction/Maintenance** | 45000000 (Construction), 45200000 (Works for complete buildings), 45210000 (Construction work), 45230000 (Civil engineering), 45240000 (Water works), 45300000 (Building installation), 45400000 (Building completion), 50700000 (Maintenance of roads) | Construction + infrastructure |
| **Consulting/Business** | 73000000 (R&D services), 73100000 (Market research), 73200000 (Market research services), 73400000 (R&D), 78000000 (Recruitment), 79000000 (Business services), 79100000 (Legal services), 79200000 (Accounting/auditing), 79300000 (Market research), 79500000 (Employment services), 79700000 (Security services) | Professional services |

---

## Step-by-Step Plan

### CHUNK 1 — TED API Core (Spike Validation)

**Goal:** Verify API integration and query syntax before building the provider.

**Steps:**
1. Rewrite `scripts/test_ted_api.py` using correct endpoint + `classification-cpv` field
2. Test all 4 vertical packs with DK country filter
3. Print: total count + 3 normalized samples per pack
4. If any field in `fields` array fails (400 error), reduce to minimum known-safe fields and introspect response structure
5. Verify `classification-cpv` returns actual CPV values in response
6. Commit: `feat: TED API spike test with classification-cpv`
7. Update STATE.md

**Validation:** API returns ≥1 results for cleaning pack. 3 normalized samples print cleanly.

**Files changed:** `scripts/test_ted_api.py`, `STATE.md`

---

### CHUNK 2 — TED Provider Implementation

**Goal:** Build `TEDTenderProvider` that fetches + saves tenders as leads via official API only.

**Steps:**
1. Create `app/ted_provider.py` with class `TEDTenderProvider(BaseScraper)`
2. Implement `scrape()` method using `requests.post` against TED API
3. Build JSON payload: country, CPV codes, fields, pagination
4. Handle pagination (iterate pages until no more results)
5. Normalize each notice→dict: title, buyer_name, buyer_country, cpv_codes, publication_date, deadline, estimated_value, notice_url, description, notice_subtype, publication_number
6. Create `idempotency_key` = `publication_number` or `notice_id`
7. In `save_ted_notices_to_db()`: check existing by `idempotency_key` + `user_id`, skip duplicates
8. Map TED notice → `Lead` model fields (may need DB migration for tender-specific fields)
9. Replace/deprecate old Playwright-based `app/ted_scraper.py`
10. Commit: `feat: TED tender provider via official API`

**Likely DB additions needed:**
- `notice_id` (string, unique, indexed) — idempotency key
- `cpv_codes` (text, JSON array)
- `estimated_value` (float, nullable)
- `currency` (string, nullable)
- `deadline` (datetime, nullable)
- `procurement_type` (string)
- `notice_subtype` (string)
- `source_url` (string, the TED notice page URL)

**Files changed:** `app/ted_provider.py` (new), `app/scrapers.py`, `app/models.py`, `migrate_004_ted_fields.py`, `STATE.md`, tests

---

### CHUNK 3 — Vertical Lead Packs

**Goal:** Define structured pack configurations for the 4 verticals.

**Steps:**
1. Create `app/lead_packs.py` with pack definitions
2. Each pack: name, description, CPV codes list, country (DNK), keywords, scope, relevance rules
3. Create preset sources tied to packs (auto-created during onboarding)
4. Add pack selection to source creation flow
5. Test each pack: run query, log result count, auto-expand if <5 results
6. Commit: `feat: vertical lead packs`

**Files changed:** `app/lead_packs.py` (new), `app/main.py`, `app/models.py`, `templates/onboard.html`, `STATE.md`

---

### CHUNK 4 — Relevance Scoring

**Goal:** Each lead gets a relevance score (0-100) + "why this lead" explanation.

**Steps:**
1. Add `lead_score` (int 0-100) and `score_reasons` (text/JSON) to Lead model
2. Scoring algorithm in `app/scoring.py`:
   - CPV exact match: +30
   - CPV parent match (first 2 digits): +20
   - Country match: +20 (always true for DNK filter, reserve for multi-country later)
   - Deadline within 30 days: +15
   - Deadline within 7 days: +10 (additional)
   - Estimated value > 0: +5
   - Keyword match in title: +10
   - Published < 7 days ago: +10
3. Normalize to 0-100 range
4. Dashboard: show score badge + "Why this lead?" tooltip
5. Commit: `feat: relevance scoring engine`

**Files changed:** `app/scoring.py` (new), `app/models.py`, `app/ted_provider.py`, `templates/dashboard.html`, `STATE.md`

---

### CHUNK 5 — Data Quality & Dedup

**Goal:** Ensure no duplicates, clean data, proper lifecycle tracking.

**Steps:**
1. Dedup across sources: unified `idempotency_key` = normalized `(source_type + external_id)`
2. Normalize titles: strip whitespace, collapse multiple spaces, title case
3. Normalize buyer names: remove legal suffixes (A/S, ApS, I/S)
4. Add `source_confidence` (high/medium/low based on data completeness)
5. Add `last_seen_at` — updated every time scraper re-runs
6. Add `is_stale` — marked after deadline passed
7. Add `is_closed` — when award notice detected
8. Pre-flight dedup in scrapers: check before insert
9. Commit: `feat: data quality and dedup`

**Files changed:** `app/ted_provider.py`, `app/scrapers.py`, `app/models.py`, `migrate_005_dedup.py`, `app/main.py`, `STATE.md`

---

### CHUNK 6 — Onboarding Flow

**Goal:** New user chooses pack → auto-creates source → first fetch runs → sees leads.

**Steps:**
1. Add "Choose your lead pack" step to onboarding
2. Packs: Cleaning/Facility, IT/Software, Construction, Consulting, Custom keywords
3. After selection: auto-create `Source` with pack config, run first `scrape()`
4. Show "Found X leads" result page
5. If 0 results: suggest broader pack or wider country
6. Custom keywords: free-text → search TED title/description
7. Commit: `feat: pack-based onboarding`

**Files changed:** `templates/onboard.html`, `app/main.py`, `app/lead_packs.py`, `app/scrapers.py`, `STATE.md`

---

### CHUNK 7 — Dashboard Value

**Goal:** Dashboard becomes immediately useful with real lead management.

**Steps:**
1. Backend pagination (was client-side, breaks with large datasets)
2. Filters: pack/source/status/score/deadline range
3. Sort: score ↓ / deadline ↑ / newest ↓ / oldest ↓
4. Search: buyer name + title (LIKE query)
5. CSV export with full tender fields (CPV, deadline, value, etc.)
6. Empty state: "No leads yet — add a source or try a broader pack"
7. Commit: `feat: enhanced dashboard with pagination and filters`

**Files changed:** `templates/dashboard.html`, `app/main.py` (new API endpoints), `STATE.md`

---

### CHUNK 8 — Lead Actions

**Goal:** Users can interact with leads beyond viewing.

**Steps:**
1. "Mark relevant/not relevant" — updates `is_relevant` on lead
2. "Save note" — text field on lead
3. "Follow-up date" — calendar selection
4. "Send to CRM" — manual trigger (uses existing CRM sync)
5. "Retry CRM sync" — for failed syncs
6. Alert rules per pack/source: toggle email notifications
7. NO auto-sync without explicit toggle + credentials
8. Commit: `feat: lead actions`

**Files changed:** `app/models.py`, `app/main.py`, `templates/dashboard.html`, `STATE.md`

---

### CHUNK 9 — Ops Hardening

**Goal:** Production-ready infrastructure hygiene.

**Steps:**
1. Generate SECRET_KEY and move to `.env` (remove hardcoded)
2. Document 2 SQLite DBs → migration plan to single DB
3. `scripts/backup.sh` — automated SQLite backup (cron daily)
4. Health check endpoint: `/api/health` → DB ping + scheduler status
5. Test suite baseline: `test_ted_api.py`, `test_cvr_enrichment.py`, `test_scoring.py`
6. Audit logs: ensure no secrets in `server.log`
7. Add `slowapi` rate limiting to auth endpoints
8. Commit: `fix: ops hardening`

**Files changed:** `.env`, `run.py`, `scripts/backup.sh`, `app/main.py`, `tests/`, `scripts/backup.sh`, `STATE.md`

---

### CHUNK 10 — Packaging

**Goal:** Product positioning and presentation for potential users.

**Steps:**
1. Positioning: "Public tender radar for Danish service businesses"
2. Landing page: real tender examples (not fake data)
3. Pricing copy: Pro (single business), Agency (multiple clients)
4. Demo mode: `/demo` — pre-loaded with real public tenders, no auth required
5. Docs: data sources explained, limits, setup guide
6. Internal README.md update for contributors
7. NO public posting/email/publishing without explicit go from Jonas

**Files changed:** `templates/landing.html`, `templates/pricing.html`, new template `demo.html`, README.md, STATE.md

---

## Risk Assessment & Tradeoffs

| Risk | Impact | Mitigation |
|---|---|---|
| **API rate limits** | High | Implement 2s delay between pages, cache responses, use pagination efficiently |
| **CPV codes too narrow** | Medium | Auto-expand to parent CPV (2-digit) if result count < 5 |
| **TED API schema changes** | Low | Field introspection on failures, fallback to `*` fields |
| **SQLite performance** | Medium (at ~10K leads) | Plan PostgreSQL migration (Phase 6), add DB indexes on search fields |
| **2 SQLite DBs confusion** | Low | Document both, plan cleanup after Chunks 1-3 verify data model |
| **No HTTPS** | High | Flag to Jonas — needs domain + cert before any real user data |
| **No tests** | Medium | Add baseline tests in Chunk 9, but don't block progress |

## Open Questions (Non-Blocking)

1. **TED API rate limits** — Need to test max requests/minute (will discover during Chunk 1-2)
2. **Multi-country expansion** — Currently DNK only; architecture should support future expansion
3. **Supabase vs self-hosted PostgreSQL** — Deferred to Phase 6
4. **Stripe pricing** — No pricing data yet; placeholder values until Jonas configures
5. **Email template design** — Deferred until SMTP credentials available

## Execution Order

```
Chunk 1 (API spike) → Chunk 2 (Provider) → Chunk 3 (Packs) → Chunk 4 (Scoring)
→ Chunk 5 (Data Quality) → Chunk 6 (Onboarding) → Chunk 7 (Dashboard) → Chunk 8 (Actions)
→ Chunk 9 (Ops) → Chunk 10 (Packaging)
```

## Definition of Done (Overall)

- [ ] TED API successfully fetches real Danish tenders via official API
- [ ] Provider saves leads with idempotency (no duplicates on re-scrape)
- [ ] 4 vertical packs tested and working
- [ ] Relevance scoring visible on dashboard
- [ ] Onboarding: new user selects pack → sees leads in <2 minutes
- [ ] Dashboard has pagination, filters, search, CSV export
- [ ] Lead actions: relevant/not relevant, notes, follow-up dates
- [ ] SECRET_KEY moved to env, backup script exists, health check endpoint
- [ ] Landing page shows real tender examples
