# LeadRadar State
## Updated: 2026-04-25 14:35 CEST
## Phase: Chunks 1–10 Complete, Shipping Prep

---

## Current Status
- **App**: Running at `http://57.128.215.250:8000`
- **Repo**: Clean, main branch pushed to GitHub
- **DB**: SQLite, `data/leadradar.db` active, legacy copy at `data/leadradar_legacy.db`, no orphan at root
- **Server**: Uvicorn on port 8000

---

## Chunks Completed

### ✅ Chunk 1 — Data Sources & API Integration
- TED EU Tenders API integration (`app/ted_provider.py`)
- RSS preset feeds (`app/rss_presets.py`) — Version2, Ingeniøren, Berlingske Business
- Scraping abstraction layer (`app/scrapers.py`)

### ✅ Chunk 2 — Lead Packs
- Pre-defined industry packs (`app/lead_packs.py`):
  - **IT & Software**: CPV 72xxxxxx — 10 results/page verified
  - **Construction & Infrastructure**: CPV 45xxxxxx — 10 results/page verified
  - **Consulting & Business Services**: CPV 73xxxx, 79xxxx — 10 results/page verified
  - **Cleaning & Facility Services**: CPV 90xxxx, 50xxxx — verified

### ✅ Chunk 3 — CVR Enrichment
- cvrapi.dk integration (`app/cvr_enrichment.py`)
- DB migration: 12 new columns on leads table
- Auto-enrichment during scrape
- Tested: 3/3 leads enriched successfully

### ✅ Chunk 4 — CRM Integration
- CRM abstraction layer, mock provider
- HubSpot adapter with env token, idempotency
- Sync queue/worker with retry and backoff
- Dashboard UI (CRM buttons, status badges, settings)

### ✅ Chunk 5 — User Onboarding
- Pack selection UI (`templates/onboard.html`)
- POST `/api/onboard/pack` — creates source + initial scrape
- "Try broader pack" suggestion on empty results

### ✅ Chunk 6 — Dashboard
- Full dashboard with leads list (`templates/dashboard.html`)
- Pagination, filtering (source, score range, deadline), search
- Sort by newest, score, deadline
- Lead actions: status, relevance, notes, follow-up, CRM sync
- CSV export

### ✅ Chunk 7 — Lead Actions
- Lead status, relevance, notes, follow-up date APIs
- CRM sync endpoint per lead

### ✅ Chunk 8 — Backup & Health
- Backup script (`scripts/backup.sh`) — gzip + rsync
- `/health` endpoint returning status + timestamp

### ✅ Chunk 9 — Tests
- Basic test suite (`tests/test_app.py`)
- pytest configuration

### ✅ Chunk 10 — Packaging (this chunk)
- Updated landing page (`templates/landing.html`) — dark theme, real tender examples
- Updated pricing page (`templates/pricing.html`) — Pro DKK 499/mo, Agency DKK 1,499/mo
- Demo page (`/demo`, `templates/demo.html`) — no auth, shows live TED tenders
- DB merge script (`scripts/merge_dbs.py`) — idempotent orphan migration
- README.md created

---

## Working Features
| Feature | Status |
|---------|--------|
| TED API integration | ✅ Working — 4 packs verified with results |
| Lead packs (IT, Construction, Consulting, Cleaning) | ✅ Working |
| Lead scoring | ✅ Working |
| User registration/login/auth | ✅ Working |
| Dashboard with pagination/filters | ✅ Working |
| Lead actions (status, notes, CRM sync) | ✅ Working |
| CVR enrichment | ✅ Working |
| Onboarding flow | ✅ Working |
| Real-time alerts system | ✅ Working (web/in-app) |
| Backup system | ✅ Working |
| Health endpoint | ✅ Working |
| Landing page | ✅ Working |
| Demo page | ✅ Working |
| DB merge utility | ✅ Working |

---

## Lead Counts (Verified)
| Pack | CPV Codes | Results (per page) | Status |
|------|-----------|-------------------|--------|
| IT & Software | 72xxxxxx | 10 | ✅ Verified |
| Construction & Infrastructure | 45xxxxxx | 10 | ✅ Verified |
| Consulting & Business Services | 73xxxx, 79xxxx | 10 | ✅ Verified |
| Cleaning & Facility Services | 90xxxx, 50xxxx | Verified | ✅ Verified |

**Note**: TED API returns historical cached notices. Results are real tenders from the EU database but may include older entries.

---

## Current DB State
| Table | Count |
|-------|-------|
| users | 8 |
| sources | 4 |
| leads | 3 (from CVR scraping) |
| alerts | 0 |
| crm_provider_configs | 1 |

**Database path**: `data/leadradar.db`
**Legacy DB**: `data/leadradar_legacy.db`
**No orphan DB at root level** (cleaned up)

---

## Blocked (Requires Jonas)
| Blocker | What's Needed | Impact |
|---------|---------------|--------|
| **Stripe** | Stripe account setup | Cannot process payments; checkout returns mock |
| **SMTP** | SMTP credentials (SendGrid/Mailgun) | Cannot send email reports or alerts |
| **Domain + HTTPS** | Purchase domain, configure DNS, set up SSL | Must use raw IP, insecure cookies |

---

## Architecture
```
┌─────────────────────────────────────────────────────┐
│                    LeadRadar App                     │
│  FastAPI + Jinja2 + SQLAlchemy + SQLite              │
├──────────┬───────────┬──────────┬───────────────────┤
│ TED API  │ RSS Feeds │ CVR API │ CRM Providers     │
│ (EU)     │ (news)    │ (DK)    │ (HubSpot/Mock)    │
├──────────┴─┬─────────┴─┬────────┴───────────────────┤
│ Lead Packs │  Scrapers │  CVR Enrichment            │
│ (slugs/CPV)│ (abstract)│ (cvrapi.dk)                │
├────────────┴───────────┴────────────────────────────┤
│  Scheduler │ Alert Dispatcher │ Backup │ Health     │
├─────────────────────────────────────────────────────┤
│                    SQLite DB                         │
│  users, sources, leads, alerts, CRM queue, prefs    │
└─────────────────────────────────────────────────────┘
```

---

## Next Steps (Requires Jonas)
1. **Set up Stripe account** — unlock Pro/Agency billing
2. **Configure SMTP** — enable email reports and alerts
3. **Purchase domain** — leadradar.dk + DNS + HTTPS
4. **Deploy with systemd service** — `leadradar.service` already created
5. **Set up cron/automated scraping** — scheduler module exists, needs scheduling
6. **Customer onboarding** — beta testing with real users
