# Kyiv Buy Radar — Multi-Market Extension Design Spec

**Date:** 2026-07-23
**Status:** Approved (brainstorm 2026-07-23)
**Type:** Extension of the existing `projects/wohnung-radar/` cloud service to support a second market.

## Purpose

Add a second, independent apartment monitor to the existing (live, cloud) wohnung-radar: **buying** a 2-room apartment in **Kyiv**, ≤ **$70 000**, **Obolon preferred**, with alerts to a **separate Telegram bot + channel**. Reuse the proven cloud engine (GitHub Actions cron → stateless `radar.cycle` → Supabase Postgres) rather than build anew.

## Chosen approach (from brainstorm)

- **Extend the existing repo** (one codebase, multi-market), NOT a separate repo. The Leipzig market must remain behavior-identical and live throughout.
- **Obolon preferred, not strict**: notify all Kyiv 2-room ≤ $70k; flag/prioritize Obolon (+ adjacent Podil, Minskyi masyv). Rationale: ≤$70k 2-room in Obolon is scarce, so a hard filter would starve the feed.
- **New separate Telegram bot + channel** for Kyiv (own token/chat via new env vars) — fully independent of the Leipzig bot.
- **Buy-mode = monitoring only**: no geo-to-school, no application drafts, no calendar, no Telethon. Just poll → filter → notify.

## Architecture: `--market` parameterization

`radar.cycle` gains a `--market {leipzig,kyiv}` argument (default `leipzig` for backward compatibility). Each market is a config bundle:
- its source set (which adapters run),
- its criteria (rooms/price/district etc.),
- its mode (`rent` for Leipzig, `buy` for Kyiv),
- its bot token + chat-id env-var names.

The cycle body is unchanged in shape (retry_pending → poll sources → drain updates → dispatch); every DB read/write is scoped to the active `market`.

## Data model (Supabase, one DB, partitioned by market)

Add `market TEXT NOT NULL DEFAULT 'leipzig'` to `listings`, `geocode_cache`, `pending_drafts`, `pending_appointments`, `bot_state`. All existing queries gain a `market = %s` predicate. The default preserves live Leipzig rows untouched. `bot_state` key becomes `(market, key)`. Cross-source dedup, status, counts, offset — all market-scoped.

`Listing` gains **`price: float | None`** and **`currency: str | None`** (buy-mode sale price; rent_warm/rent_cold stay for rent-mode). Buy listings set `price` (USD; UAH prices converted via a configurable rate); `rent_*` stay None.

## Market config

`config/markets/leipzig.yaml` (the current criteria + source keys + `mode: rent` + env-var names `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`) and `config/markets/kyiv.yaml`:

```yaml
mode: buy
bot_token_env: KYIV_TELEGRAM_BOT_TOKEN
chat_id_env: KYIV_TELEGRAM_CHAT_ID
max_price_usd: 70000
rooms: 2                      # exact
uah_per_usd: 41.5            # editable; UAH listings -> USD via this rate
preferred_districts: [Оболонь, Оболонський, Подільський, Поділ, Мінський масив]
sources:
  olx:      { enabled: true, interval_minutes: 30, url: "<recon>" }
  domria:   { enabled: true, interval_minutes: 30, url: "<recon>" }
  lun:      { enabled: true, interval_minutes: 30, url: "<recon>" }
  rieltor:  { enabled: true, interval_minutes: 30, url: "<recon>" }
  flatfy:   { enabled: true, interval_minutes: 30, url: "<recon>" }
```

Exact URLs, anti-bot behavior, and markup are established by empirical recon during planning (as with the Leipzig portals — several guessed domains there proved wrong). Any JS-only/blocked portal is documented and deferred.

## Filter (buy-mode)

For `mode: buy`: `rooms == 2` (exact); `price ≤ max_price_usd` (UAH converted first) → known-over = violation, missing price = unknown/flag; district in `preferred_districts` → flagged/prioritized in the card, absence is NOT a violation (soft preference). No warm/cold, no feature keywords, no geo. Reuses the existing violations-vs-unknown semantics (never silently drop on missing data).

## Bot / channel / card

New bot via @BotFather; a channel or private chat for alerts. Card reuses `build_card_text` adapted for buy-mode (shows `price $/currency`, rooms, district with an ⭐ when in preferred set, source, link). Keyboard: only «Пропустити» (no draft/appointment buttons in buy-mode). `dispatch_update` handles the Kyiv bot's getUpdates the same way, market-scoped offset.

## Deployment

New `.github/workflows/poll-kyiv.yml` (`*/30`, `python -m radar.cycle --market kyiv`) with the Kyiv secret set: `DATABASE_URL` (shared), `KYIV_TELEGRAM_BOT_TOKEN`, `KYIV_TELEGRAM_CHAT_ID`, and (if any adapter needs them) shared keys. The Leipzig `poll.yml`/`digest.yml` are untouched. A Kyiv digest is optional (deferred unless wanted).

## Testing & safety

- Every change is TDD'd; the full existing suite must stay green (Leipzig behavior unchanged — the `market` default and mode-gating guarantee it).
- Market-scoping is verified: Leipzig and Kyiv rows never cross-contaminate (dedup, offset, counts scoped).
- New Kyiv adapters get fixture-first parser tests (real captured HTML), like the Leipzig adapters.
- A local dry-run (`--market kyiv --dry-run`) fetches all Kyiv sources against an isolated schema before the first cloud run.

## Out of scope (YAGNI / deferred)

- Application drafts, Google Calendar, email, geo travel-time, Telethon — none apply to the buy radar.
- Historical data migration (fresh start for the Kyiv market).
- Kyiv digest (add later if wanted).
- Currency live-rate lookup (a configurable static `uah_per_usd` suffices; most Kyiv sale listings are USD-denominated anyway).
