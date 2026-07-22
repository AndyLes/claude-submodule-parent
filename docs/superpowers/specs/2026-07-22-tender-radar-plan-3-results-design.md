# Tender-Radar Plan 3 — Results Collector + Competitor/Price Intelligence — Design

**Date:** 2026-07-22
**Status:** Approved by user (design conversation, 2026-07-22)
**Builds on:** Plan 1 (foundation) + Plan 2 (5 httpx sources live in cloud). Extends the modular monolith `projects/tender-radar/`.

## Purpose

Collect bid results (bidders, amounts, winner) from closed/awarded window-glazing solicitations, build a competitor & bid-spread intelligence base, and deliver a weekly Telegram report. This is the "who competes and at what price level" picture the user asked for — NOT $/window unit prices (those need window counts from a future takeoff module; out of scope).

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Target of "price analysis" | **Competitors + bid spreads** (per-project bid amounts, bidders, winner, low-high spread, win-rate) | User choice; buildable from available bid-result data. $/window needs takeoff (deferred). |
| v1 result sources | **CTsource (priced tabs, has $) + RI OSP (vendors+winner+PO, no $)** | Only sources with accessible INLINE results (`bidAwardPublish[].customReport`); reuse the existing WebProcure client + SSL fix. |
| Deferred sources | NYC awards (separate City Record query — later), DCAMM (login-walled), COMMBUYS (detail-only, prices non-public) | Access cost / not publicly available. |
| Collection modes | **Backfill (awarded window jobs) + Follow-up (our closed tenders)** | Backfill gives immediate historical value; follow-up completes the lifecycle of tracked tenders. |
| Deliverable | **Collect + weekly Telegram report** | User choice. |
| competitors table | Computed on the fly in analytics (no stored table v1) | Keep lean; aggregates are cheap. |

## Data availability (from recon)

- **CTsource** (`research/recon/ctsource.md` §3): `bidAwardPublish[].customReport` HTML, two flavors — (1) **priced tabulation** `<table>` for DAS construction (vendor | base | supplemental | total $), the spread-bearing case; (2) **vendor list** for towns (names, no $). ~38 awarded window jobs. Fixture: `research/recon/fixtures/ctsource_bidtab.html`.
- **RI OSP** (`research/recon/ri_osp.md` §3): `bidAwardPublish[]` — Bid Opening / Tentative Selection / Final Award reports with **vendors + winner + PO number, NO dollar amounts**. Fixture: `research/recon/fixtures/ri_osp_bidopening.html`.
- Both fetched via the same WebProcure API (`search/sols` with `f=ps=Awarded`, and per-record `soldetail/{bidid}`), same client (with the committed intermediate-CA SSL fix from Plan 2).

## Architecture (modular monolith extension)

New module `results/`, plus `analytics/` functions, plus a weekly report path. Modules talk to the DB only via `storage` repositories (the established seam).

```
results/
  parse.py               # customReport HTML → list[ParsedBid] (priced-table + vendor-list flavors)
  webprocure_results.py  # fetch awarded records (backfill f=ps=Awarded; follow-up soldetail/{bidid}) via WebProcure client
  collector.py           # orchestrate: fetch → parse → upsert bid_results → update tender status
analytics/
  competitors.py         # aggregates: bids/wins/win-rate per bidder; spreads per project
  report.py              # weekly markdown report from bid_results
```

### storage additions
- **`bid_results`** table (deferred from Plan 1, now created):
  - `id` PK; `source` (ctsource/ri_osp); `external_id` (bidid); `project_title`; `bidder_name`; `amount` (Float, nullable — RI has none); `is_winner` (bool); `award_date` (AwareDateTime, nullable); `collected_at` (AwareDateTime).
  - Unique `(source, external_id, bidder_name)`.
  - Stands alone (backfilled awards need not exist in `tenders`); opportunistically joined to `tenders` by `(source, external_id)`.
- Repository `BidResultRepo` (upsert-dedup by the unique key), plus a query for "results collected since <date>" (weekly report) and competitor/spread aggregates.
- `Tender.status` → `results_collected` for tracked tenders whose results are found (the last lifecycle state).

### collector flow
1. **Backfill** (incremental): for each WebProcure source (CT, RI), query `f=ps=Awarded` + relevance q-terms (dedupe by bidid); for each awarded record with `bidAwardPublish`, parse the newest priced/vendor report → upsert `bid_results`. Bound by a recency window (e.g. award pubDate within N days) so daily runs only process fresh awards; a one-shot initial backfill covers history.
2. **Follow-up**: for our `tenders` with `status="closed"` and source in {ctsource, ri_osp}, fetch `soldetail/{external_id}`; if `bidAwardPublish` present, parse → upsert `bid_results`, set tender `status="results_collected"`. (Closed tenders with no results yet stay "closed" and are retried next run.)
Both paths share `parse.py`. Per-source isolation (try/except per source) like the ingest runner.

### parse.py
- Input: a `customReport` HTML string. Output: `list[ParsedBid(bidder_name, amount|None, is_winner)]` + award_date.
- Priced-table flavor: parse `<table>`, last `$` column per row = vendor total; `$` regex `\$\s*[\d,]+\.\d{2}` after stripping nbsp/U+FFFD mojibake (recon gotcha). Winner = the awarded vendor (from the Final Award report's "Awarded Vendors" section, or the lowest total on a low-bid construction job — but prefer the explicit award report; store is_winner from the "Awarded Vendors" list).
- Vendor-list flavor: parse "Awarded Vendors" / "Responded Vendors" lists → bidders (amount None), winner flagged.

### analytics + weekly report
- `competitors.py`: from `bid_results`, compute per-bidder bids/wins/win-rate; per-project low/high/spread (where amounts exist, i.e. CT priced jobs).
- `report.py`: weekly markdown — new results this week (project, winner, bidder count, spread if priced), top competitors by wins, notable spreads. Delivered via the existing Telegram client as a SEPARATE weekly message (not the daily tender digest).

### scheduling
- `run_once.py` / `main.job_ingest_and_digest` gains a results step after ingest+digest: run the collector (follow-up + incremental backfill) daily.
- Weekly report: a weekly cadence — simplest is a check inside the daily run ("if today is the configured weekday, send the weekly report") using the passed `now`, avoiding a second cron. (A dedicated weekly GH Actions cron is an alternative; the in-run weekday check is simpler and reuses the same entrypoint.)

## Error handling
- Per-source isolation in the collector (one source failing never aborts the others), mirroring `ingest/runner.py`.
- WebProcure per-term/per-request resilience already exists in the client pattern; reuse.
- Parser: a malformed `customReport` for one record logs + skips that record, never aborts the source.

## Testing
- `parse.py`: unit tests on the real fixtures (`ctsource_bidtab.html` → priced bids with amounts + winner; `ri_osp_bidopening.html` → vendor list + winner, amounts None). Edge cases: mojibake `$`, missing award section.
- `collector.py`: MockTransport WebProcure responses (awarded record with bidAwardPublish) → asserts bid_results upserted + tender status transition; dedup on re-run.
- `analytics`: unit tests on synthetic bid_results (win-rate, spread arithmetic).
- `report.py`: assert weekly report content from seeded bid_results; empty-week path.
- Full suite stays green; results collection tested offline (no live network in tests).

## Out of scope (v1)
- NYC/DCAMM/COMMBUYS results collection (later plans / not accessible).
- $/window or $/SF unit normalization (needs takeoff module).
- Stored `competitors`/`price_points` tables (aggregates computed on the fly; price_points deferred until takeoff exists).
- A web dashboard.

## Future
- NYC City Record award notices (separate Socrata query, has $) — richest deferred extension.
- Takeoff module → window counts → true $/window from bid_results.
- competitors/price_points materialized tables if aggregate volume grows.
