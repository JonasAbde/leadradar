# LeadRadar Build Protocol
## Version: 1.0 | Date: 2026-04-24
## Purpose: No lost work, no forgotten state, no timeout casualties

---

## Core Rules

1. **NEVER build in session-only memory**
   - Every code change is a git commit within 30 minutes
   - Every decision is written to a file on disk
   - Every TODO is tracked in a file, not just conversation

2. **Atomic checkpoints**
   - Work in 20-30 minute chunks
   - At end of each chunk: commit, push, write status
   - If session dies, next session reads file, not memory

3. **Idempotent builds**
   - Every script is safe to run twice
   - Every migration checks before running
   - No "this only works the first time" code

4. **Local file = source of truth**
   - `~/leadradar/STATE.md` — current build status
   - `~/leadradar/BUILD_LOG.md` — what was done, when, by whom
   - `~/leadradar/DECISIONS.md` — why choices were made
   - `~/leadradar/TODO.md` — what's next

5. **Session recovery protocol**
   - On every startup: read STATE.md + git log
   - Never trust session memory for project state
   - Always verify current branch, uncommitted files, running processes

---

## File Structure

```
~/leadradar/
├── STATE.md          # Current phase, what's done, what's next
├── BUILD_LOG.md      # Timestamped actions
├── DECISIONS.md      # Architecture and product decisions
├── TODO.md           # Prioritized task list
├── .git/             # Git repo (main branch)
├── check_state.py    # Script to verify current state
└── [app code]
```

---

## Phase Structure

Each phase is a folder with:
- `phase_X_NAME/`
  - `plan.md` — what to build
  - `test.md` — how to verify
  - `done.md` — what was completed

Phases:
1. **CVR API** — Replace HTML scraper with official API
2. **ENRICHMENT** — Add phone/email/size/decision-maker to leads
3. **ALERTS** — Real-time email + Slack webhooks
4. **PAYMENTS** — Stripe integration (requires Jonas)
5. **CRM** — HubSpot/Pipedrive sync
6. **SCALE** — PostgreSQL migration

---

## Build Discipline

### Before starting work:
1. Read `STATE.md`
2. Run `git status`
3. Check if app is running: `curl http://localhost:8000/health`
4. Read last 20 lines of `BUILD_LOG.md`

### During work:
1. Make changes
2. Test locally
3. Commit with descriptive message
4. Push to GitHub
5. Update `BUILD_LOG.md`
6. Update `STATE.md`

### After work (before session ends):
1. Final commit + push
2. Update `STATE.md` with exact status
3. Write `TODO.md` for next session
4. Confirm no uncommitted changes

---

## Recovery Checklist

If session resets mid-work:
```bash
cd ~/leadradar
git status
git log --oneline -5
cat STATE.md
curl http://localhost:8000/health
```

This 30-second check tells you exactly where you are.

---

## Why This Works

**Before:** Work lived in conversation → session dies → lost.
**After:** Work lives in committed files → session dies → `git log` + `STATE.md` tells all.

No trust in memory. No trust in session history. Only git + files.

---

## Author
Hermes, LeadRadar operator
Last updated: 2026-04-24
