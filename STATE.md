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

## Phase 1: CVR ENRICHMENT API (IN PROGRESS)
Priority: HIGHEST | Impact: Data accuracy + legal compliance
- Strategy shift: cvrapi.dk is LOOKUP not SEARCH
- Use for: phone, email, owner, industry, address, employee count
- Discovery stays with job/news/udbud scrapers
- Blocked: None — can build immediately

## Phase 2: Lead Enrichment (READY TO START)
Priority: HIGHEST | Impact: 10x lead value
- Add phone, email, employee count, revenue from CVR data
- Blocked: Needs Phase 1 (CVR API provides the data)

## Phase 3: Real-Time Alerts (READY TO START)
Priority: HIGH | Impact: Product stickiness
- Instant email on new lead
- Slack webhook integration
- Blocked: Needs SMTP credentials (Jonas)

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
