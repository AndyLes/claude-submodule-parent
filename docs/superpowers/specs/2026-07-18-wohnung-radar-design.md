# Wohnung-Radar — Leipzig Apartment Finder (Design Spec)

**Date:** 2026-07-18
**Status:** Approved (brainstorm 2026-07-18)
**Type:** Personal tool (single user), new repo at `projects/wohnung-radar/`

## Purpose

Find and win a rental apartment/house in Leipzig for the user's family. The system monitors listing sources 24/7, filters against fixed family criteria, notifies via Telegram, drafts viewing applications (sent only after explicit user approval), and books confirmed viewings into Google Calendar.

## Search Criteria (all editable in `criteria.yaml`, never hardcoded)

- City: Leipzig
- Rooms: ≥ 3 (3-Zimmer)
- Area: ≥ 60 m²
- Rent: ≤ €1000 **warm** (incl. heating/NK)
- Must have: kitchen (room/EBK), shower
- Location: prestigious, quiet area AND ≤ 15 min from school at **Könneritzstraße 47, 04229 Leipzig (Schleußig)** by foot OR public transit
  - Stage 1 (cheap prefilter): district whitelist (initial: Schleußig, Plagwitz, Lindenau, Südvorstadt, Waldstraßenviertel, Musikviertel, Zentrum-West/Süd; user-editable)
  - Stage 2 (exact): Google Routes API travel time (walking + transit), pass if either ≤ 15 min

## Architecture

Single Python 3.12 async service (APScheduler) + SQLite + Telegram bot (python-telegram-bot). Runs initially on the user's Windows PC as a service (NSSM/Task Scheduler); config-portable to a small VPS with no code changes. LLM usage (Claude Haiku) is point-wise only — parsing unstructured listing texts and drafting applications — never in the ordinary polling loop (token efficiency).

## Components

### 1. Source adapters (`sources/`)
Each adapter is isolated and returns a normalized `Listing` (source, source_id, url, title, address/district, rooms, area_m2, rent_warm, rent_cold, features_text, photos, posted_at):

- **Portals:** Kleinanzeigen, Immowelt, ImmobilienScout24 (*best-effort — anti-bot; parsers adapted from open-source Flathunter*)
- **Leipzig cooperatives:** LWB, Lipsia, UNITAS, Kontakt, VLW, Wogetra, BGL — simple sites, custom HTML parsers
- **Telegram channels:** public UA channels (configurable list) read via Telethon user session
- **WhatsApp school chat:** no API — user forwards messages to the bot; forwarded text is parsed as a listing candidate (rule-based first, LLM fallback)

Polling: portals every 5–10 min (staggered), cooperatives hourly; intervals configurable.

### 2. Normalizer
Rule-based field extraction first; LLM (Haiku) fallback only when required fields are missing.

### 3. Filter engine
Applies `criteria.yaml`. Geocoding via Nominatim; two-stage geo check as above.

### 4. Deduplication
Cross-source fuzzy match on address + area + rent.

### 5. Telegram bot UI
- New-match card: photo, price, m², district, travel time to school, link + buttons **[Send application] [Skip] [Details]**
- Commands: `/status` (pipeline summary), `/criteria` (view/edit criteria)
- Inbound forwards are classified as: listing candidate (WhatsApp/TG) or landlord reply (→ appointment flow)

### 6. Application sender
Tenant profile (family composition, employment, documents — configurable) + listing details → personalized German draft → preview card in bot → on approval, sent by email from the user's Gmail (SMTP/app password). Portals that only accept contact forms: bot returns ready text + deep link for manual paste. **No application is ever sent without explicit per-listing user approval.**

### 7. Appointment flow
User forwards landlord reply → extract date/time/address (LLM) → confirmation card → Google Calendar API event (one-time OAuth) with listing link and reminder.

### 8. State tracker
SQLite states: `new → notified → applied → reply_received → viewing_scheduled → rejected/won`. Daily digest message.

## Error handling

- Adapter failures isolated; one source down never stops the rest
- Source failing N consecutive cycles → bot alert
- IS24 blocked → degrade to "check manually" notification with search-page link
- Geocoding failure → card still delivered, flagged "address unresolved", not silently dropped

## Secrets / external services

`.env`: Telegram bot token, Telethon session, Gmail app password, Google OAuth (Calendar), Google Routes API key, Anthropic API key. Free tiers sufficient at this volume.

## Testing

- Parser unit tests on saved HTML fixtures per source
- Filter-engine unit tests (boundary values: 60 m², €1000, 15 min)
- Dry-run mode: full pipeline, no outbound sends

## Out of scope (YAGNI)

- Multi-user support, auth, billing
- Automatic (unapproved) application sending
- Gmail inbox monitoring (appointment info arrives via manual forward)
- Web dashboard / Notion integration
