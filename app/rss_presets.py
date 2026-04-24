"""
Hardcoded Danish RSS presets for instant lead signals.
No user configuration needed beyond selecting a preset name.
"""

RSS_PRESETS = {
    "version2_tech": {
        "url": "https://www.version2.dk/rss",
        "name": "Version2.dk — Tech News",
        "category": "news",
    },
    "ingenioren_tech": {
        "url": "https://ing.dk/rss",
        "name": "Ingeniøren — Engineering News",
        "category": "news",
    },
    "berlingske_business": {
        "url": "https://www.berlingske.dk/rss/business",
        "name": "Berlingske Business",
        "category": "news",
    },
}

# TED is blocked by Cloudflare/JS rendering — documented in STATE.md
# To re-enable: switch to TED XML bulk download API (large files, requires parsing)
