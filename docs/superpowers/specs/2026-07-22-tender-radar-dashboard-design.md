# Tender-Radar Dashboard — Design

**Date:** 2026-07-22
**Status:** Approved by user (design conversation, 2026-07-22)
**Relation:** Read-only web viewing layer over the existing Tender-Radar Supabase data. The Python collector (`projects/tender-radar/`) is unchanged; this is a separate frontend app.

## Purpose

A single-user web dashboard to browse the tenders and bid-results Tender-Radar collects, complementing (not replacing) the Telegram digests. Tenders-first: the primary job is scanning active tenders with filters; competitor/results data is a secondary view.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Stack | **Next.js (App Router) + Supabase + Vercel** | Matches the user's Smart Film stack; reads the same Supabase Postgres. |
| Repo | New separate repo `projects/tender-radar-dashboard/` + its own Vercel project | Frontend concern, separate from the Python collector; independent deploy. |
| Auth | Supabase Auth **magic-link, allowlisted to the owner's email** (single user) | User choice: "тільки я". Simplest secure gate. |
| Data access | **Server-side reads** (Next server components) via a Supabase client using the service-role key (server-only, never shipped to the browser), behind the auth gate | Read-only + single-user → no RLS policy work needed; service key stays server-side. |
| Mutability | **Read-only v1** | User choice; no editing tenders. Notes/"interested" is a future extension. |
| Design language | Reuse Smart Film's: left sidebar shell, slate/monochrome, white content, status badges, color only for meaning | Consistency with the user's existing products. |

## Data source

Reads the existing Supabase project (ref `cofplvbfzuppwykxhqbr`) tables the collector already populates — **no schema changes, no writes**:
- `tenders` — source, external_id, title, owner, state, trade_classes, est_value, bid_deadline, listing_url, status (new/notified/closed/results_collected), first_seen, last_seen.
- `bid_results` — source, external_id, project_title, bidder_name, amount (nullable), is_winner, award_date, collected_at.
- `source_health` — source, last_success, last_error, last_error_at, consecutive_failures.

## Pages (v1)

1. **Overview** (`/`) — top-line counters (active tenders by state, total, closed, results_collected); the 5-source health panel (last success, consecutive failures, an alert if a source is silent ≥3 runs); a "recently seen" list (newest tenders by first_seen).
2. **Tenders** (`/tenders`) — the primary view. A filterable, sortable table:
   - Filters: state (NY/MA/CT/RI), source (5), status (open/closed via bid_deadline vs now + status), deadline range, free-text title search.
   - Columns: title, owner, state, source, deadline, est_value, status badge.
   - Sort: by deadline (soonest first) default.
   - Row → detail panel/page: full title, owner, trade_classes, est_value, deadline, status, and a **link out to `listing_url`** (opens the portal).
3. **Results / Competitors** (`/results`) — secondary view over `bid_results`:
   - Competitor table: bidder, # bids, # wins, win-rate (from analytics logic mirrored client/server-side).
   - Recent results by project: project, source, winner, bidder count, spread (low→high, % ) where amounts exist.
   - Honest empty/thin-data states (amounts are currently sparse — see the collector's `$`-capture limitation).

## Architecture

- Next.js App Router. Server components fetch from Supabase (service-role client, server-only) and render tables; light client interactivity for filters (URL search params drive server-side filtering, or client-side filtering of a server-fetched page for v1 volumes).
- Auth: `@supabase/ssr` middleware protects all routes; magic-link sign-in; a server-side check rejects any email not equal to the configured owner email.
- Secrets (Vercel env, user-provided at deploy — like the collector's DSN): `NEXT_PUBLIC_SUPABASE_URL` (https://cofplvbfzuppwykxhqbr.supabase.co), `NEXT_PUBLIC_SUPABASE_ANON_KEY` (for auth), `SUPABASE_SERVICE_ROLE_KEY` (server reads), `OWNER_EMAIL` (allowlist).
- Data volumes are small (tens–hundreds of tenders, ~hundreds of bid_results) → no pagination complexity needed in v1; simple server fetch + in-page filtering is fine.

## Error handling
- If Supabase is unreachable, pages render a clear error state, not a crash.
- Empty states for every table (no tenders match filters; no results yet).
- Auth failure → redirect to sign-in; non-owner email → explicit "not authorized".

## Testing / verification
- Component/unit tests where logic exists (filter predicates, competitor aggregation, status derivation) via the framework's test runner.
- **Build verification, NOT dev-server spawning:** per the user's Smart Film lesson, do NOT spawn `next dev` from tools/subagents (orphaned servers corrupt the shared `.next` → chunk 404s / no hydration). Verify via `next build` (must succeed) and, for runtime, authenticated checks against a deployed/preview URL — never assert on a logged-out 307 redirect.

## Out of scope (v1)
- Any writes/actions (notes, mark-interested, status changes).
- Multi-user / roles.
- Commercial-source data (flows in automatically once commercial sources are added to the collector).
- $/SF charts (appear once `$` + area data exist).
- Realtime/live updates (daily cadence → refresh-on-load is enough).

## Future
- Notes / "interested" flags per tender (adds writes → RLS).
- $/SF and spread charts once pricing data lands.
- Commercial-project views as those sources come online.
- Multi-user (team/partners) with roles.
