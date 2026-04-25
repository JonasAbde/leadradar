# LeadRadar Blockers Fix — 2026-04-25

## Goal
Address the 3 red blockers from code review before accepting paying customers.

## Blockers (Priority Order)

### 1. PostgreSQL Migration 🔴 CRITICAL
SQLite cannot handle concurrent writes under load. Must migrate before any real traffic.

**Approach:**
- Install PostgreSQL 16 on VPS
- Create `leadradar` database + user
- Use `sqlite3-to-postgres` or custom script to migrate existing data
- Update `.env` with `DATABASE_URL`
- Update `models.py` connection args (remove `check_same_thread`)
- Generate new Alembic migration for PostgreSQL
- Restart service

**Files to change:**
- `.env`
- `app/models.py`
- `alembic/env.py`
- New: `scripts/migrate_sqlite_to_postgres.py`

**Validation:**
- `pytest tests/` still passes
- Health endpoint shows `db: connected`
- Manual: create user, login, add source, fetch leads

### 2. Password Reset Flow 🔴 CRITICAL
Users locked out = support burden. No excuse for a SaaS to miss this.

**Approach:**
- New route `GET /forgot-password` + `POST /api/forgot-password`
- Generate itsdangerous timed token (same pattern as email verification)
- Send reset email with link `/reset-password/{token}`
- New route `GET /reset-password/{token}` (render form)
- New route `POST /api/reset-password` (validate token, update password)
- Templates: `forgot_password.html`, `reset_password.html`

**Files to change:**
- `app/main.py` (new routes)
- `templates/forgot_password.html`
- `templates/reset_password.html`
- `tests/test_app.py` (new tests)

**Validation:**
- Test: request reset → token valid → password updated → login with new password
- Test: expired token rejected
- Test: used token rejected (single-use)

### 3. CSRF Protection 🟡 HIGH
State-changing POSTs currently unprotected.

**Approach:**
- Wire existing `app/csrf.py` into forms
- Add `csrf_token` hidden field to all POST forms
- Validate token on: register, login, source create/delete, onboard, password reset
- Skip for API endpoints (already auth'd via JWT/bearer)

**Files to change:**
- `app/main.py` (add CSRF validation to POST handlers)
- `templates/*.html` (add hidden csrf field)
- `app/csrf.py` (minor fixes if needed)

**Validation:**
- Test: POST without CSRF token → 403
- Test: POST with valid token → 200
- All existing tests still pass

## Steps (Execution Order)
1. Install PostgreSQL, create DB
2. Write migration script, run it
3. Update models + alembic, test
4. Build password reset routes + templates
5. Wire CSRF into forms
6. Full test suite
7. Commit + push

## Risks
- **Data loss:** Backup `data/leadradar.db` before migration
- **Downtime:** 5-10 min while switching DB. Plan for maintenance window.
- **Token reuse:** Password reset tokens must be single-use. Store used tokens in DB or short expiry.

## Open Questions
- Do we want to keep SQLite for local dev? Yes — `DATABASE_URL` env handles this.
- Password reset token expiry? 1 hour is standard.
