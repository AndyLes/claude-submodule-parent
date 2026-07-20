# Tender-Radar v1 — Design

**Date:** 2026-07-20
**Status:** Approved by user (design conversation, 2026-07-20)

## Purpose

Monitoring of public construction tenders in MA/NY/CT/RI/NH relevant to a Massachusetts window company (filed sub-bid classes "Metal Windows" / "Glass and Glazing" in MA; GC-quoting elsewhere), plus collection of bid results to build a market/price intelligence base. Open sources only in v1.

Research grounding: `projects/tender-radar/research/01-public-portals.md`, `02-plan-rooms.md`, `03-takeoff-automation.md` (04/05 market+price scans in progress).

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| v1 scope | Monitoring (stage 1) + bid results (stage 7) + analytics (stage 8) | User: "спочатку аналізуємо ринок тендерів, ціни"; takeoff/RFQ deferred |
| Architecture | **Modular monolith** (user-confirmed after microservices discussion) | No load/team/deploy driver for microservices; module boundaries allow later extraction |
| Stack | Python 3.12 + PostgreSQL + SQLAlchemy + APScheduler | Scraping/PDF/LLM ecosystem; wohnung-radar pattern proven |
| Runtime | Local Windows machine; long-running process via Task Scheduler (at logon); PG in a single Docker container or native install (implementation-time choice) | User choice; no VPS in v1 |
| Interface | Telegram digests + generated markdown/CSV reports; no web UI in v1 | Fastest path; dashboard later |
| 50+ windows filter | **Not in v1** — metadata-level relevance filter only | Window counts require plan parsing = future takeoff module |
| Inter-module comms | Only via `storage` repositories | Clean seams for future service extraction |

## Repository

Separate git repo `C:\SuperWork\projects\tender-radar\` with mandatory `docs/` (ARCHITECTURE.md, DATA-MODEL.md, DECISIONS.md; API.md when API appears).

```
tender-radar/
  ingest/        # source adapters, relevance filter, dedup
  results/       # bid tabulation / award collection
  analytics/     # price normalization, competitor stats, reports
  notify/        # Telegram digests
  storage/       # SQLAlchemy models + repositories (the only inter-module seam)
  main.py        # APScheduler wiring, env guard, clean shutdown
  tests/         # pytest; HTML/JSON fixtures per source
```

## Modules

### storage
SQLAlchemy models + repository classes. Tables:
- `tenders` — source, external_id (unique per source), title, owner/agency, state, trade classes, UNSPSC codes, est. value, bid deadline, plans URL, listing URL, status (`new → notified → closed → results_collected`), first_seen/last_seen.
- `bid_results` — tender FK, bidder name, amount, is_winner, opened_at, source URL.
- `price_points` — bid_result FK, window type (aluminum/vinyl/curtain wall/storefront/glazing/other), unit ($/window, $/SF, lump sum), value, derivation note.
- `competitors` — canonical bidder names (simple normalization), aggregates computed in analytics.
- `source_health` — per source: last success, last error, consecutive failures.
- `digest_log` — what was sent when (dedup for notifications).

### ingest
- Interface: `BaseSource.fetch() -> list[RawTender]`; one adapter file per source.
- v1 adapters (from report 01): `ma_dcamm` (Bid Express listing page — scrapeable, shows filed sub-bid classes), `ma_commbuys`, `nyscr` (parameterized search URLs), `ctsource`, `ri_osp`, `nyc_socrata` (Socrata API — the only true API), `nh_das` (playwright; 403 to plain HTTP).
- Relevance filter on metadata: filed sub-bid classes "metal windows" / "glass and glazing"; UNSPSC categories; keywords (window, glazing, curtain wall, storefront, fenestration). Tunable per source; filter params in config/DB, not hardcoded (per user preference).
- Dedup by `(source, external_id)`; update `last_seen` on re-encounter.

### results
- For tenders past deadline: poll the source-specific results channel — CTsource bid tabs (~24h after opening), RI OSP Bid Opening Report + award, DCAMM/Bid Express results, NYC City Record awards (Socrata).
- Parse bidder/amount rows into `bid_results`. PDF tabs → pdfplumber first, LLM fallback for messy layouts.
- Stop polling a tender after results collected or N weeks past deadline (configurable).

### analytics
- Derive `price_points` where scope allows normalization (e.g., replacement projects stating window counts → $/window; curtain wall SF → $/SF); keep lump sums otherwise.
- Competitor stats: bids/wins per bidder, price spreads (low vs high on same tab).
- Weekly market report: markdown + CSV to `reports/` — new tenders, upcoming deadlines, fresh results, benchmark table, competitor movements.

### notify
- Telegram bot. Daily digest: new relevant tenders (state, owner, deadline, est. value, link) — only unseen items (via `digest_log`). Weekly: analytics report summary + file.
- Source failures (3+ consecutive days silent) appear as an alert line in the daily digest.

## Data flow

`ingest` (daily) → new `tenders` → daily Telegram digest → deadline passes → `results` (daily over closed tenders) → `bid_results` → `analytics` (weekly) → report → Telegram + `reports/`.

## Error handling

- Per-adapter isolation: one source failing never aborts the run (try/except per source, wohnung-radar pattern).
- Retries with backoff inside adapters; failures recorded in `source_health`.
- Scheduler job-level guard: overlapping runs prevented (max_instances=1); clean shutdown on SIGTERM.

## Testing

- pytest; each adapter tested against stored HTML/JSON fixtures of real portal pages (no network in tests).
- Unit tests: relevance filter, dedup, price normalization arithmetic.
- E2E: full pipeline run over fixtures for all sources → digest content assertion.

## Out of scope (v1)

- Takeoff (window schedule extraction), RFQ packages, proposals, bid submission — future modules over the same storage seams.
- Paid sources (ConstructConnect, Dodge, MA Central Register subscription), web dashboard, VPS deploy.
- Automatic "50+ windows" detection.

## Future extraction path

Any module → standalone service mechanically (its repository interface becomes an API), if/when the project becomes multi-user/SaaS. Not before.
