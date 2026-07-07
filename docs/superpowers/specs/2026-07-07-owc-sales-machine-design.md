# OWC Sales Machine — Design Spec

**Date:** 2026-07-07
**Owner:** Andriy (OffWhite.City UG)
**Status:** Approved design → ready for implementation plan

## 1. Goal

Build a "windows-selling machine": a system that captures leads (website ads +
other channels) and **progressively automates** the full 15-stage deal
lifecycle, keeping a **human control point** at every transition. Start manual,
flip stations to automated one at a time — without re-architecting.

Today's gap: point-tools exist (`wincalc-to-sheet`, `offwhite-proposals`,
Google Sheets) but there is **no spine** — no single place where every request
becomes a deal and moves through stages, and no orchestration tying the tools
together.

## 2. Scope decisions (locked)

| Decision | Choice |
|----------|--------|
| Deliverable | Own web app (not a configured off-the-shelf CRM) |
| Spine stack | Next.js (App Router) + Supabase (Postgres/Auth/Storage/RLS) — same as smartfilm |
| Operators at start | Solo (Andriy). Minimal auth; RLS laid in from day one for future helpers |
| Build phasing | **A** — spine first, then automate top-of-funnel; wire tools station-by-station |
| First automated station | **Lead intake & qualification** (top-of-funnel leakage is the biggest pain) |
| Hosting | Vercel + Supabase cloud |

## 3. Architecture

### 3.1 Core abstraction — "stations"
Each of the 15 stages is a **station**. Every station has an automation mode:

- `manual` — human does the step; system only records status.
- `assisted` — system prepares a draft; human confirms.
- `auto` — system does it; human reviews at the control point.

"Progressive automation" = flipping a station `manual → assisted → auto` over
time **without changing the system**. At launch nearly everything is `manual`
except Lead intake.

### 3.2 Control points
Uniform mechanism for all 15 stations:
- `manual` station → human advances the deal (click/drag); event logged.
- `assisted`/`auto` station → system does NOT auto-advance. It sets
  `needs_review = true`, stores its output (draft) in documents, logs what it
  did. Human opens the deal → **Approve** (advance) or **Reject** (send
  back / edit). No automation ever slips past the human.

### 3.3 Tools as services
Existing Python tools are **not rewritten** — each is wrapped as an internal
endpoint the relevant station calls as a job. The app stays a thin orchestrator.
- `offwhite-proposals` → **Proposal** station service (PDF, +15%, rebrand).
- `wincalc-to-sheet` → **Take-off / Quote** station service (supplier PDF →
  window schedule).

### 3.4 Event log
Every stage change, automation run, and message is written to an activity log
per deal. Serves as audit trail and the source for funnel metrics (per-stage
conversion = the machine's "instruments").

### 3.5 Stage → phase grouping
15 stages grouped into 5 funnel phases so the board is not overloaded:

| Phase | Stages |
|-------|--------|
| **Lead** | 1. Запит → 2. Запит на прорахунок отримано |
| **Quote** | 3. Take-off → 4. RFQ постачальникам → 5. Прорахунок отримано |
| **Proposal** | 6. Пропозиція мовою клієнта → 7. Відправка → 8. Погодження |
| **Close** | 9. Кінцевий прорахунок → 10. Договір → 11. Оплата |
| **Fulfil** | 12. Виробництво → 13. Відправка → 14. Розтаможка → 15. Передача |

## 4. Data model (deliberately minimal)

- **`deals`** — the spine. `id`, client (name, language, contact), `source`
  (site / ads / other), `stage` (1–15), `phase`, `status` (active / won /
  lost), `amount`, `needs_review` (control-point flag), timestamps.
- **`stage_events`** — log. `deal_id`, `from_stage → to_stage`, `actor`
  (human / auto), `note`, `at`.
- **`documents`** — per-deal files. `deal_id`, `type` (request / take-off /
  quote / proposal / contract), `url` (Supabase Storage), `version`.

**Deferred (YAGNI):** `line_items` (window positions for take-off/quote) is
added only when the Take-off station is built. `suppliers` added with the RFQ
station.

## 5. MVP (first slice)

### 5.1 Spine (works for all 15 stations)
- Board: 5 phases / 15 stations, deal cards, manual move + drag.
- Deal page: client data, documents, activity log, **Approve / Reject** buttons
  (control-point mechanism).
- Solo login; Supabase Storage for files.
- At launch all stations `manual` except Lead intake.

### 5.2 Lead intake station — first `auto`
- **Website form** → auto-creates `deal` (source=site), sends fast
  auto-acknowledgement to client, sets `needs_review` for qualification.
- **Other channels (email/messenger)** → "New lead" button: paste the request
  text, AI structures it (client, language, ask) into a draft deal — `assisted`
  mode.
- **Dedupe**: same contact → link to existing deal instead of duplicating.

### 5.3 Explicitly OUT of MVP
Stations exist on the board but stay manual: take-off, supplier RFQ, proposal
generation, contract, payment, production, shipping, customs, handover.

## 6. Rollout order after MVP
Each is its own mini spec→plan→build cycle:
1. Lead intake (MVP) ✅
2. Proposal station (wire `offwhite-proposals`)
3. Take-off station (wire `wincalc-to-sheet`)
4. Supplier RFQ + quote collection
5. Close phase (final calc / contract / payment)
6. Fulfil phase (production / shipping / customs / handover)

## 7. Out of scope (this spec)
- Client-facing portal (future phase).
- Multi-user roles beyond solo (RLS ready, not built).
- Automated IMAP email ingestion (MVP uses website form + paste; auto-ingest
  is a later upgrade of the Lead station).
- Marketing/ad-spend attribution analytics beyond `source` tagging.
