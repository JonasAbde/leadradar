# LeadRadar Guidelines

## Karpathy Principles

See `karpathy-coding-principles` skill for full details. Core rules:

1. **Think Before Coding** — State assumptions explicitly. Surface tradeoffs. Ask before guessing.
2. **Simplicity First** — Minimum code. No speculative features, abstractions, or "flexibility."
3. **Surgical Changes** — Touch only what you must. Match existing style. No drive-by refactoring.
4. **Goal-Driven Execution** — Define success criteria. Loop until verified. Tests first.

## Project-Specific

### Stack
- **Framework:** FastAPI + Uvicorn
- **Database:** SQLite via SQLAlchemy (no PostgreSQL/Redis on VPS)
- **Deploy:** OVH VPS, systemd service: `leadradar.service`
- **Template:** Jinja2 (no React SPA — server-side rendered)

### Two Databases (known tech debt)
- `leads.db` — leads/contacts
- `app.db` — users/subscriptions
- **Do NOT add a third.** Migration plan: consolidate into one.

### Style
- Python 3.11+, f-strings preferred
- Single quotes for strings (match existing)
- Type hints on function signatures, not on every internal variable
- No ABCs, Protocols, or abstract factories unless there are 3+ implementations

### Security (VPS constraints)
- No HTTPS yet (self-signed cert available if needed for testing)
- No secrets in code — use `.env` or config
- Input validation on all API endpoints

### Testing
- `pytest --tb=short -x` 
- Test critical paths before deploy
- New feature → test first

### Git
- Direct pushes to `main` (single dev)
- Meaningful commit messages
