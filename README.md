# LeadRadar

**Automated lead intelligence for Danish SMBs.** Monitor EU public tenders, Danish companies, and business news — get scored leads delivered daily.

## Overview

LeadRadar is a SaaS platform that aggregates procurement opportunities from multiple sources, enriches them with Danish CVR company data, and delivers them through a clean dashboard with real-time alerts. Built for businesses that need to find and bid on public tenders before their competitors do.

## Features

### Data Sources
- **TED EU Tenders** — Real-time access to the EU's Tenders Electronic Daily database, filtered by CPV codes and country
- **RSS Business News** — Danish tech and business publications (Version2, Ingeniøren, Berlingske Business)
- **CVR Enrichment** — Automatic company data enrichment from Denmark's Central Business Register

### Core Functionality
- **Lead Packs** — Pre-configured industry filters (IT & Software, Construction, Consulting, Cleaning) with relevant CPV codes
- **Lead Scoring** — Automatic relevance scoring based on pack keywords
- **Dashboard** — Full-featured UI with search, filtering, sorting, and pagination
- **Lead Actions** — Mark status, relevance, add notes, set follow-up dates
- **CRM Integration** — Sync leads to HubSpot (or mock provider) via queue-based worker
- **Real-Time Alerts** — In-app notifications on new leads
- **Daily Reports** — Email digests of new leads (SMTP pending)
- **CSV Export** — Export your leads for offline analysis
- **User Onboarding** — Guided pack selection with initial scrape

### Infrastructure
- Rate-limited API (slowapi)
- Backup script with gzip + rsync
- Health check endpoint
- SQLite database (PostgreSQL migration path planned)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI |
| Templates | Jinja2 (server-side rendered) |
| Database | SQLite (SQLAlchemy ORM) |
| Auth | JWT cookies, bcrypt hashing |
| Rate Limiting | slowapi |
| HTTP Client | httpx |
| Testing | pytest |
| Deployment | systemd service, uvicorn |

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/your-org/leadradar.git
cd leadradar
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file:
```env
# App
SECRET_KEY=your-secret-key-here
PUBLIC_BASE_URL=http://localhost:8000

# SQLite DB (optional, default: data/leadradar.db)
DATABASE_URL=sqlite:///data/leadradar.db

# TED API (optional, no key required for public access)
# TED_API_URL=https://api.ted.europa.eu/v3/notices/search

# Stripe (blocking — needs account)
# STRIPE_SECRET_KEY=sk_live_...
# STRIPE_PUBLISHABLE_KEY=pk_live_...
# STRIPE_PRICE_ID_PRO=price_...
# STRIPE_PRICE_ID_AGENCY=price_...
# STRIPE_WEBHOOK_SECRET=whsec_...

# SMTP (blocking — needs credentials)
# SMTP_HOST=smtp.sendgrid.net
# SMTP_PORT=587
# SMTP_USER=apikey
# SMTP_PASS=SG.xxx

# HubSpot CRM (optional)
# HUBSPOT_API_KEY=pat-na1-...

# Security
HTTPS_ENABLED=false
```

### 3. Run
```bash
python run.py
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Visit
- Home: `http://localhost:8000/`
- Demo: `http://localhost:8000/demo`
- Dashboard: `http://localhost:8000/dashboard`
- Pricing: `http://localhost:8000/pricing`

### Database Migrations
Run migration scripts in order (all in repo root):
```bash
python migrate_001_enrichment.py
python migrate_002_crm.py
python migrate_003_alerts.py
python migrate_004_ted_fields.py
python migrate_005_lead_actions.py
```

### Merge Orphan DB
If you have an old `leadradar.db` at the root level:
```bash
python scripts/merge_dbs.py
```

### Run Tests
```bash
pytest tests/ -v
```

## Data Sources

| Source | Type | Endpoint | Auth |
|--------|------|----------|------|
| TED EU Tenders | REST API (POST) | `api.ted.europa.eu/v3/notices/search` | None (public) |
| CVR Enrichment | REST API | `cvrapi.dk/api` | None (free tier) |
| Version2.dk | RSS Feed | `https://www.version2.dk/xml/rss/all` | None |
| Ingeniøren | RSS Feed | `https://www.ing.dk/rss` | None |
| Berlingske Business | RSS Feed | `https://www.berlingske.dk/rss` | None |

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
│  users · sources · leads · alerts                    │
│  CRM queue · notification prefs · CRM configs        │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
leadradar/
├── app/
│   ├── main.py              # FastAPI app, all routes
│   ├── models.py            # SQLAlchemy models
│   ├── auth.py              # JWT auth, password utilities
│   ├── scrapers.py          # Scraper factory/abstraction
│   ├── ted_provider.py      # TED EU API client
│   ├── rss_presets.py       # Pre-configured RSS feeds
│   ├── scoring.py           # Lead relevance scoring
│   ├── lead_packs.py        # Industry pack definitions
│   ├── cvr_enrichment.py    # CVR API enrichment
│   ├── alert_dispatcher.py  # Alert creation & dispatch
│   ├── scheduler.py         # Background job scheduler
│   ├── mail.py              # Email sending (SMTP)
│   ├── stripe_config.py     # Stripe checkout + webhooks
│   ├── crm/                 # CRM providers
│   │   ├── __init__.py
│   │   ├── mock_provider.py
│   │   └── hubspot_provider.py
│   └── crm_sync_worker.py   # CRM sync queue processor
├── templates/
│   ├── landing.html         # Marketing homepage
│   ├── demo.html            # Public live tenders demo
│   ├── pricing.html         # Pricing plans
│   ├── login.html
│   ├── register.html
│   ├── onboard.html         # Pack selection
│   └── dashboard.html       # User dashboard
├── scripts/
│   ├── test_ted_api.py      # TED API test script
│   ├── backup.sh            # DB backup script
│   └── merge_dbs.py         # Orphan DB migration
├── tests/
│   ├── __init__.py
│   └── test_app.py          # App tests
├── data/
│   └── leadradar.db         # Active SQLite database
├── migrate_00*.py           # Database migration scripts
├── run.py                   # Entry point
├── requirements.txt
├── .env                     # Configuration (not committed)
├── leadradar.service        # systemd service file
└── deploy.sh                # Deployment script
```

## Current State

Chunks 1–10 complete. Core product is functional with real data from TED and CVR.

**Blocked on Jonas**: Stripe account, SMTP credentials, domain purchase.

See `STATE.md` for detailed status.
