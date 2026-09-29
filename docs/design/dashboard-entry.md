# Dashboard as an entry (parked design)

Mockup: `dashboard-entry.dc.html` (Design-canvas artboard source; canvas "jn tree-first feed", board D). Unbuilt.

**Idea:** a curated home page that is itself an entry. Its markdown body holds live query blocks and transcluded entries, so a page is versioned, linkable (`#N`), replyable, and pinnable — no new data type, no special tag.

- ```` ```jn @todo --mine -@parent ```` renders as a live list (checkboxes toggle `@done`).
- ```` ```jn @agent --since 1d --by=agent ```` renders the roots view inline.
- `![[#418]]` transcludes another entry's body live.
- Sidebar lists pinned pages (entries tagged by convention, e.g. `@pin`; the web already knows nothing about it, so it would be a saved query).

**Why parked:** it only shows what you already know to query for; the roots view (`--by`) covers discovery. Build it if curating still feels like the gap.

**Would replace:** `+ save view` writing to `~/.jn` — a saved view is a page with one query block.

**Cost (unverified guess):** 1–2h for query blocks in `md()`; transclusion is extra. Web-only; `jn.py` untouched.
