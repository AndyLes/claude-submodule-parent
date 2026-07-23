# Wohnung-Radar Cloud Migration — Design Spec

**Date:** 2026-07-23
**Status:** Approved (brainstorm 2026-07-23)
**Type:** Re-architecture of existing personal tool (`projects/wohnung-radar/`) from a local always-on daemon to a serverless scheduled cycle.

## Purpose

Move the Leipzig apartment-finder off the user's local PC (it was stopped 2026-07-23 due to thermal load) onto **free** cloud infrastructure that runs 24/7 without depending on the PC being on:

- **Compute:** GitHub Actions scheduled workflows (private repo, ~30-min cycle → stays under the 2000-min/month free tier).
- **Database:** Supabase Postgres (replaces local SQLite).
- **Bot:** stateless `getUpdates` polling inside each cycle (replaces the persistent PTB long-polling Application).

## Key decisions (from brainstorm)

- Private GitHub repo, poll every 30 min (48 runs/day × ~1 min ≈ 1440 min/month, safely under 2000). Digest is a separate daily workflow.
- Supabase Postgres via the connection pooler (Supavisor, transaction mode) — appropriate for short-lived serverless connections.
- Telethon TG-group reader is **dropped** in the cloud build (needs a persistent process; was never configured anyway). Deferred to a future always-on host if ever wanted.
- Google Calendar / Gmail / Routes / Anthropic all keep working (plain HTTP from the cycle). Calendar OAuth `token.json` moves from a file to a GitHub Secret / Supabase row.

## Architecture: the stateless cycle

New entrypoint `python -m radar.cycle` runs ONE pass then exits (no APScheduler, no PTB updater loop):

1. **Poll:** for each enabled source → fetch → normalize → filter → geo → cross-source dedupe (against Supabase) → for each new passing listing, send a Telegram card via a direct `bot.send_message` (with the existing inline keyboard). Persist listing rows + versioned draft state in Supabase.
2. **Drain bot updates:** `bot.get_updates(offset=stored_offset+1, timeout=0)` (short poll, returns buffered updates immediately) → for each update dispatch to the existing handler LOGIC (button callbacks: skip/draft/applied/send_email/cal/callisting; forwarded text: appointment-or-listing intake; `/status`) → answer → store the new max `update_id` back to Supabase.
3. **Digest** runs only in the separate daily workflow: build digest text, send if non-empty.

GitHub Actions:
- `.github/workflows/poll.yml` — `schedule: cron "*/30 * * * *"` → checkout, setup Python, install, `python -m radar.cycle`.
- `.github/workflows/digest.yml` — daily at 18:00 UTC (≈20:00 Europe/Berlin, DST-approximate; acceptable) → `python -m radar.cycle --digest`.

## What changes vs. what stays

**Rewritten:**
- `db.py` → Postgres via `psycopg` (v3). Same public function signatures (`connect`, `insert_if_new`, `set_status`, `recent_listings`, `get_listing`, `listings_by_status`, `status_counts`, `recent_notified`, `pending_listings`, `listing_from_row`, `DbCache`). SQL dialect port: `datetime('now')`→`now()` (timestamptz), `AUTOINCREMENT`→`BIGSERIAL`, `INSERT … ON CONFLICT (source, source_id) DO NOTHING RETURNING id` (None on conflict), `datetime('now','-N hours')`→`now() - make_interval(hours => N)`, `PRAGMA`-migration dropped for `CREATE TABLE IF NOT EXISTS` + `ADD COLUMN IF NOT EXISTS`. Rows via `psycopg.rows.dict_row` so `row["col"]` access is preserved.
- In-memory `pending_drafts` / `pending_appointments` (were in `bot_data`) → Supabase tables. New `bot_state` table holds the single `last_update_id` offset.
- Bot layer: the PTB `Application`+handlers+`updater.start_polling()` wiring in `main.py` → a `dispatch_update(update, deps)` function that switches on `update.callback_query` / `update.message`, reuses the existing handler functions (which already take explicit `conn/profile/notifier/mailer/calendar` args from the Plan-3 refactor), and enforces the owner guard via the update's chat id. A thin `telegram.Bot` (not `Application`) is used for send + get_updates.

**Unchanged (pure logic, all existing tests keep passing):**
- `sources/*` (all 5 adapters + registry + common), `filters.py`, `geo.py`, `draft.py`, `appointment.py`, `calendar_api.py`, `contact.py`, `mailer.py`, `msgparse.py`, `report.py`, `notify.py` (card text + keyboards), `config.py`, `profile.py`, `models.py`.

## Data model (Supabase)

Existing tables ported: `listings`, `geocode_cache`. New tables:
- `pending_drafts(listing_id BIGINT PRIMARY KEY, version TEXT, draft_text TEXT, email TEXT, created_at TIMESTAMPTZ DEFAULT now())`
- `pending_appointments(token TEXT PRIMARY KEY, appointment_json JSONB, orig_text TEXT, created_at TIMESTAMPTZ DEFAULT now())`
- `bot_state(key TEXT PRIMARY KEY, value TEXT)` — row `('last_update_id', '<n>')`.

Pending rows older than N days are swept opportunistically each cycle (they're re-tappable state, not critical).

## Secrets (GitHub repo → Settings → Secrets → Actions)

`DATABASE_URL` (Supabase pooler URI), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_ROUTES_API_KEY`, `ANTHROPIC_API_KEY`, optional `GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD`, optional `GOOGLE_CALENDAR_TOKEN` (the token.json contents as a secret) + `GOOGLE_CLIENT_SECRET`. Same graceful-off behavior when optional ones are absent. `profile.yaml` stays gitignored; the cloud reads the tenant profile from a `PROFILE_YAML` secret (or a committed non-PII default) — decided in the plan.

## Testing & migration approach

- The DB rewrite is TDD'd against a **real Postgres** (a local Docker postgres or a Supabase test schema) using the same test contracts the SQLite `db.py` had — the existing `test_db.py` / `test_dedup.py` / `test_status_digest.py` behaviors must hold on Postgres. `psycopg` connection is seam-injected so tests point at the test database.
- `dispatch_update` is unit-tested with fake update objects (no Telegram network), reusing the Plan-3 handler tests' fakes.
- One-shot `radar.cycle` is integration-verified with a dry-run flag (no sends) against the real sources + test DB before the first live GitHub Actions run.
- Cutover: create Supabase project + schema, push repo to private GitHub, set Secrets, enable the workflows, watch the first few runs. Local `radar.db` data is NOT migrated (fresh start — the listing history is disposable; only forward from cutover matters).

## Out of scope (YAGNI / deferred)

- Migrating historical `radar.db` rows.
- Telethon TG-group reading (needs persistent host).
- Real-time bot interactivity (webhook) — the 30-min cycle latency is accepted.
- Multi-user, auth, any web UI.
