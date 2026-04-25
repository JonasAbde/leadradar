# LeadRadar: MVP → Production-Ready SaaS
# Dato: 2026-04-25
# Scope: Full production readiness — infra, security, payments, email, UX
# Ansvar: Hermes autonom (undtagen Jonas-blokeringer)

---

## Mål
Gå fra "fungerende MVP med security gaps" til et produkt der kan sælges til betalende kunder.
Ingen placeholders, ingen mock data, ingen plaintext cookies.

## Nuværende Status (Ærlig)

### Fungerer ✅
- Auth (JWT cookie + bcrypt)
- Dashboard med filters, pagination, search
- Scrapers: RSS presets (Version2, Ingeniøren, Berlingske)
- CVR enrichment (cvrapi.dk)
- CRM: mock default, HubSpot adapter ready
- Real-time alerts (web bell)
- systemd: auto-restart, ~67MB RAM
- Tests: 11+ passing

### Mangler 🔴
- **2 SQLite DBs** — data kan være spredt
- **SMTP** — email alerts print kun til stdout
- **Stripe** — checkout fejler uden keys
- **HTTPS** — cookies i plaintext
- **Rate limiting** — kun delvis på auth
- **CSRF tokens** — ingen
- **Email verification** — ingen
- **Password reset** — ingen
- **ted_scraper.py** — dead code (Cloudflare blocked)
- **Ingen backup** — DB kan slettes uigenkaldeligt
- **Alembic mangler** — manual migrations
- **Dashboard kræver auth** — kan ikke screenshot uden login

### Jonas-blokeringer (Hermes må IKKE røre)
- Stripe account + price IDs
- SMTP credentials (Gmail app password / Resend / SendGrid)
- Domain + DNS (til HTTPS/Let's Encrypt)
- CVR registration
- .env med rigtige værdier

---

## Fase 1: Infrastructure Cleanup (Autonom)

### 1.1 Database Merge
- Identificer forskelle mellem `leadradar.db` (root) og `data/leadradar.db` (active)
- Merge indhold til `data/leadradar.db`
- Slet `leadradar.db` fra root
- **Fil:** `scripts/merge_dbs.py` (exists, needs run)
- **Verificer:** `sqlite3 data/leadradar.db ".tables"` viser alle tabeller

### 1.2 Dead Code Cleanup
- Slet `app/ted_scraper.py` (Playwright scraper, 0 results, Cloudflare blocked)
- Fjern alle referencer til `ted_scraper` i `main.py`, `scrapers.py`, `scheduler.py`
- Fix `scripts/test_ted_api.py` — brug korrekt `api.ted.europa.eu/v3/notices/search`
- **Verificer:** `grep -r "ted_scraper" app/` → 0 results

### 1.3 Secrets Hardening
- Sikr at `SECRET_KEY` altid kræves fra env — ingen hardcoded fallback
- Tjek at `.env` aldrig committes (verify `.gitignore`)
- **Fil:** `app/auth.py` — remove hardcoded SECRET_KEY fallback

### 1.4 Alembic Migration Setup
- Initialiser Alembic: `alembic init alembic`
- Auto-generer første migration fra eksisterende schema
- Test: `alembic upgrade head` på clean DB
- Future migrations via `alembic revision --autogenerate`

### 1.5 Database Backup
- Tilføj `scripts/backup_daily.sh` — cron kører kl 03:00
- Backup til `/home/ubuntu/backups/leadradar-YYYY-MM-DD.db`
- Gem sidste 30 dage
- **Fil:** `leadradar-backup.service` (systemd timer)

---

## Fase 2: Security (Autonom)

### 2.1 Rate Limiting
- Udvid SlowAPI til alle endpoints:
  - `POST /api/login` → 5 req/min
  - `POST /api/register` → 3 req/min
  - `/api/scrape/*` → 10 req/hour
  - `/api/leads` → 100 req/hour
- **Fil:** `app/main.py` eller ny `app/rate_limit.py`

### 2.2 CSRF Protection
- Brug `itsdangerous` eller custom CSRF token i forms
- Implementer for:
  - `/api/sources` (POST)
  - `/api/leads/action` (POST)
  - `/api/register` (POST)
  - `/api/login` (POST)
- Token sendes via `<input type="hidden">` i Jinja2 templates
- **Fil:** `app/csrf.py`, opdater `templates/*.html`

### 2.3 Password Reset Flow
- `POST /api/password-reset/request` — send email med token
- `GET /reset-password?token=xxx` — vis form
- `POST /api/password-reset/confirm` — opdater password_hash
- Token: JWT med 1h expiry, single-use
- Kræver SMTP (mock indtil Jonas leverer creds)
- **Ny fil:** `templates/reset_password.html`, `app/password_reset.py`

### 2.4 Email Verification
- On registration, send verification email
- `GET /verify?token=xxx` — bekræft email, sæt `email_confirmed=True`
- Block access til dashboard indtil verified (eller warn)
- **Opdater:** `app/main.py` registration endpoint, `app/mail.py`

### 2.5 Session Security
- Set `Secure=True` på JWT cookie (når HTTPS er active)
- `HttpOnly=True`, `SameSite=Lax`
- Session expiry: 24h, auto-refresh on activity

---

## Fase 3: Payments & Billing (Blokeret på Jonas)

### 3.1 Stripe Integration
- Kræver: Jonas' Stripe account + API keys + Price IDs
- Implementer:
  - `POST /api/stripe/checkout` → create checkout session
  - `POST /api/stripe/webhook` → handle events (checkout.completed, subscription.canceled)
  - Upgrade/downgrade flow
  - Cancel subscription
- **Fil:** `app/stripe_config.py` (exists), `app/stripe_webhook.py` (new)

### 3.2 Payment-Blocked Access
- Free tier: 3 sources, ingen CRM sync, ingen CSV export
- Pro tier: 15 sources, CRM sync, daily email reports
- Agency: ubegrænset, team seats, white-label
- Enforce limits i middleware og API endpoints
- **Verificer:** Test hver tier med forskellige bruger-roller

### 3.3 Invoice & Receipt Emails
- Send receipt på payment success
- Monthly invoice via Stripe
- **Fil:** `app/mail.py` — nye templates

---

## Fase 4: Email & Reports (Blokeret delvist på Jonas)

### 4.1 SMTP Configuration
- Kræver: Jonas leverer SMTP credentials
- Indtil da: mock mode med stdout prints
- Når SMTP klar:
  - `app/mail.py` → rigtig SMTP send
  - `send_daily_report()` → sender rigtige emails
  - Alert dispatch → sender rigtige alerts

### 4.2 Email Templates
- Design HTML email templates:
  - Daily digest (leads summary)
  - Instant alert (new lead)
  - Password reset
  - Email verification
  - Payment receipt
- **Ny filer:** `templates/emails/*.html`

### 4.3 Email Preferences
- User kan vælge:
  - Instant vs digest (daglig kl 07:00)
  - Hvilke alert-tyder (leads, CRM errors, system)
  - Email frequency (daily/weekly)
- **Opdater:** `templates/dashboard.html` — settings panel

---

## Fase 5: UX & Conversion (Autonom)

### 5.1 Empty State Dashboard
- Når 0 leads: illustration + "Add a source to get started" + CTA
- Når 0 sources: onboarding flow med preset recommendations
- **Opdater:** `templates/dashboard.html`, `static/styles.css`

### 5.2 Demo Mode
- Tilføj `/demo` route — bypass auth, viser pre-loaded 10 leads
- Kan bruges til screenshots, salg, product tours
- Read-only: ingen mutations tilladt
- **Ny fil:** `app/demo.py`, `templates/demo.html` (exists, needs content)

### 5.3 Lead Detail View
- Når man klikker på en lead → side med:
  - Full details (company, CVR, score, CPV, deadline, description)
  - Actions: mark relevant/not, add note, sync to CRM, set follow-up
  - History: når oprettet, notificeret, synced
- **Ny fil:** `templates/lead_detail.html`

### 5.4 Settings Page
- User profil: email ændring, password ændring
- Notification preferences (email, Slack, digest)
- CRM config (HubSpot token input)
- Subscription status + cancel button
- **Ny fil:** `templates/settings.html`

### 5.5 Activity Log
- Log: user actions (source added/deleted, lead marked relevant, CRM sync)
- Vis i dashboard sidebar eller settings
- **Ny model:** `ActivityLog` i `app/models.py`

---

## Fase 6: Data Sources — Production (Autonom)

### 6.1 TED EU Integration (via Official API)
- Brug `POST api.ted.europa.eu/v3/notices/search` (verified working)
- Søgning: `buyer-country='DNK' AND cpv IN (...)`
- Fandt ikke CPV field navn endnu — research nødvendig
- Implementer som `TedProvider` — allerede delvis eksisterende i `app/ted_provider.py`
- **Fil:** `app/ted_provider.py` needs full implementation
- **Verificer:** `scripts/test_ted_api.py` → 200 OK + results

### 6.2 CVR API Provider (Discovery)
- Erhvervsstyrelsen tilbyder CVR API til søgning
- Find alle nystiftede selskaber i specifikke brancher
- **Research:** Er der en gratis offentlig søge-API?
- Alternativ: virk.dk data, open data DK

### 6.3 Jobindex.dk — Selector Refresh
- Nu: selectors broken (site structure changed)
- Fix: inspect ny HTML struktur, opdater CSS selectors
- Alternativ: find RSS/API feed

### 6.4 Fallback Data
- När en scraper fejler → vis placeholder/ingen data, ikke crash
- Dashboard skal aldrig være helt tomt
- Implementer graceful degradation

---

## Fase 7: Testing & Quality (Autonom)

### 7.1 Test Coverage Udvidelse
- Unit tests for hvert CRUD endpoint
- Integration tests for auth flows (login, register, reset, verify)
- Mock SMTP og Stripe i tests
- Coverage target: 70%+
- **Ny filer:** `tests/test_auth.py`, `tests/test_stripe.py`, `tests/test_email.py`

### 7.2 Lint & Format
- `ruff check app/` — find alle lint errors
- `black app/` — format
- `mypy app/` — type check
- CI i GitHub Actions (valgfrit)

### 7.3 Performance
- Profilér `/dashboard` med 500+ leads
- Implementer caching for statiske data (pricing, presets)
- Database indices på `leads.user_id`, `leads.source_id`, `leads.created_at`

---

## Fase 8: Deployment & Monitoring (Autonom, undtagen HTTPS)

### 8.1 HTTPS Setup
- Kræver: Jonas' domain + DNS adgang
- Let's Encrypt via certbot
- Nginx reverse proxy → uvicorn
- HTTP → HTTPS redirect
- Cookie `Secure=True` activate

### 8.2 Health Checks
- `GET /health` → JSON med status (DB, schedulers, scrapers)
- Systemd watchdog integration
- Log til `/var/log/leadradar/`

### 8.3 Error Tracking
- Tilføj Python logging med file rotation
- Log file: `/var/log/leadradar/app.log`
- Exception tracking: send til Sentry (valgfrit, kræver konto)

### 8.4 Deploy Script
- `deploy.sh` forbedres:
  1. Pull latest from GitHub
  2. Install deps (`pip install -r requirements.txt`)
  3. Run migrations (`alembic upgrade head`)
  4. Restart service (`sudo systemctl restart leadradar`)
  5. Health check (`curl http://localhost:8000/health`)

---

## Prioritering & Afhængigheder

```
Fase 1: Infrastructure  ──────────→ Autonom, 1-2 dage
    ↓
Fase 2: Security      ──────────→ Autonom (delvist), 2-3 dage
    ↓
Fase 3: Payments      ──────────→ BLOKERET på Jonas (Stripe)
    ↓
Fase 4: Email         ──────────→ BLOKERET på Jonas (SMTP credentials)
    ↓
Fase 5: UX/Conversion ──────────→ Autonom, kan starte parallelt med Fase 2
    ↓
Fase 6: Data Sources  ──────────→ Autonom (delvist), 2-3 dage
    ↓
Fase 7: Testing       ──────────→ Autonom, 1-2 dage
    ↓
Fase 8: Deploy/Monitor→ Autonom (delvist — HTTPS kræver Jonas)
```

## Kan startedes NU (autonom):
1. ✅ Cleanup (Fase 1)
2. ✅ Rate limiting (Fase 2)
3. ✅ CSRF (Fase 2)
4. ✅ Demo mode (Fase 5.2)
5. ✅ Empty state (Fase 5.1)
6. ✅ Lead detail view (Fase 5.3)
7. ✅ Settings page (Fase 5.4)
8. ✅ TED API fix (Fase 6.1)
9. ✅ Test coverage (Fase 7)

## Afventer Jonas:
1. 🔴 Stripe account + keys (Fase 3)
2. 🔴 SMTP credentials (Fase 4)
3. 🔴 Domain + DNS til HTTPS (Fase 8)

## Tidsramme
- **Uge 1-2:** Fase 1-2 (infra + security)
- **Uge 2-3:** Fase 5 (UX) — kan parallelt
- **Uge 3-4:** Fase 6-7 (data + tests)
- **Når Jonas klar:** Fase 3-4-8

## Risici
1. **CVR API søgning** — måske ikke gratis/offentlig tilgængelig → fallback til virk.dk
2. **TED CPV field** — ukendt felt navn → kræver documentation research
3. **SQLite → PostgreSQL** — kan være nødvendig ved scale → blocked på Jonas
4. **Testing uden SMTP/Stripe** → mock data, men ikke fuld validation
