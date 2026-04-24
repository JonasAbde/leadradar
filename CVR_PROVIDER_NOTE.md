# CVR Data Provider Note

## Status

LeadRadar uses **cvrapi.dk** for CVR enrichment. This is a **third-party provider**, 
not Virk/Erhvervsstyrelsen's official API.

### What's the difference?

| | cvrapi.dk (current) | Erhvervsstyrelsen (official) |
|---|---|---|
| Cost | Free | Free |
| Data source | Aggregates from public sources | Primary source |
| Rate limits | Fair use / 429 possible | Higher, but requires registration |
| Reliability | Volunteer-run, may go down | Government-backed |
| Legal | Uses public data | Official |

### Why we use it now
- No registration required
- Instant setup (no API keys)
- Returns phone, email, address, owner, employees
- Works for enrichment (lookup by CVR or name)

### Limitation
cvrapi.dk is a **lookup** service, not a **search** service:
- Input: one CVR number or company name
- Output: one company record
- Cannot list "all new companies in rengøring" — that's what our other scrapers do

### Future migration path
When Hermes has time or cvrapi.dk becomes unreliable:
1. Register at data.virk.dk or erhvervsstyrelsen.dk
2. Implement adapter using virk_api_client or direct REST
3. Switch provider with no code changes (BaseCRMProvider pattern)

### What LeadRadar does NOT do
- We do NOT scrape virk.dk HTML pages directly (blocked by anti-bot)
- We do NOT store CVR data permanently beyond enriching leads
- We respect cvrapi.dk rate limits (polite delays between calls)

---
Document version: 2026-04-24 | Added by Chunk 5
