# Smart Film / Smart Glass Platform — Design Spec

**Date:** 2026-06-27
**Status:** Draft for review
**Source TZ:** `TZ_SmartFilm_SmartGlass_Platform.md` v1.1 (baseline 2026-06-26)
**Interface language:** English (US market) · **Currency:** USD · **Units:** mm/inch + m²/SqFt

## Locked decisions (this session)

1. **Execution:** solo build, operator-driven with Claude Code.
2. **Stack:** Supabase-centric (managed for now; portable to self-host later — it's OSS + standard Postgres).
3. **MVP:** lean — **Smart-Film orders only**. Invoicing, Smart-glass, subcontractor, client portal, analytics all deferred.
4. **QR / product page:** **not hosted here.** Platform calls the **DPP API** to obtain a QR link per product/panel and prints it on the spec. DPP owns the product page.

---

## 1. Purpose & scope

The platform standardizes and tracks the full order lifecycle for switchable-privacy glazing products: data entry → calculation → (later) payment → production → delivery → after-sales. It replaces the current form/email workflow, reduces spec errors, and gives dealers/clients status transparency.

This spec defines the **platform architecture** plus the **MVP (Phase 1)** in detail. Phases 2–5 are summarized in the roadmap (§7) and get their own spec→plan cycle when reached.

## 2. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | **Next.js 14 (App Router) + TypeScript** | Full-stack (Server Actions + Route Handlers); single deploy. |
| UI | **Tailwind + shadcn/ui**, React Hook Form, **Zod** | Zod schemas shared by form + server validation. |
| DB | **Supabase Postgres** | Managed now; local via Supabase CLI. Standard Postgres — portable. |
| Auth | **Supabase Auth** | Email/password; sessions via `@supabase/ssr`. |
| RBAC | **Postgres Row-Level Security (RLS)** | Dealer/region visibility enforced at the DB, not in app code. |
| Data access | **supabase-js** + generated TS types; SQL migrations via Supabase CLI | Drizzle optional later for typed complex server queries. |
| Files | **Supabase Storage** | DXF/DWG/PDF/PNG/JPG; RLS on buckets; per-order/panel; versioned. |
| PDF | **@react-pdf/renderer** | No headless-Chrome dependency. |
| QR | **`qrcode`** lib + **DPP API client** | Link comes from DPP; encode/print only. |
| Email | **Resend + React Email** | App notifications; Supabase Auth emails separate. |
| Jobs (later) | **pg_cron / pg-boss** | For SLA timers & reminders (Phase 5). Not in MVP. |
| App hosting | **Vercel** (simplest) or self-hosted Docker/Coolify | DB/Auth/Storage stay on Supabase either way. |
| CI | GitHub Actions (typecheck/lint/test/build) | |
| Backups | **Supabase managed** (+ PITR on plan) | Optional periodic logical export. |
| Tests | **Vitest** (unit) + **Playwright** (E2E) | Coverage focused on RBAC, pricing, state-machine. |

## 3. Architecture

**Modular monolith** — one Next.js app, foldered by domain: `auth`, `orders`, `panels`, `busbars`, `addons`, `pricing`, `attachments`, `qr` (DPP), `status`, `notifications`, `dealers`, `admin`.

Key cross-cutting modules:

- **RBAC = Supabase Auth (identity) + RLS policies (visibility) + role checks (UI/actions).** A `profiles` table links each auth user to role(s) + `dealer_id`/`region`. RLS policies scope every `orders`/`order_panels`/`attachments` read-write so a dealer sees only their own orders. This replaces a hand-rolled scoping layer and removes the TZ's biggest risk block.
- **Status state-machine** — an isolated, typed module: a transition map (which role may move which status → which) backed by an append-only `status_history`. Small surface, heavily unit-tested.
- **DPP integration** — a thin client: given a product/panel, request a QR link from the DPP API, persist the `qr_id ↔ panel` mapping, embed the QR on the PDF spec. Specced against a clean interface; real endpoint slotted in later (§9).
- **Reference data is DB-driven** — products, regions, busbar types, add-ons, price lists are all editable via admin with price history. No hardcoding.

**Public surfaces in MVP:** none required (no product page; client portal is Phase 4). All MVP surfaces are authenticated.

**Local-first dev:** `supabase start` (Docker) runs Postgres + Auth + Storage + Studio + Inbucket (local mail) on the machine; Next.js `next dev`; react-pdf/QR are local libs; Vitest + Playwright run against local Supabase. Only externals are the **DPP API** (mock locally / staging endpoint for integration) and **real email** (Resend test key or log-to-console). Cloud needed only for staging URL / production.

## 4. Data model — MVP entities

Subset of TZ §11.1. (Deferred entities listed after.)

- `profiles` — auth user → role(s), `dealer_id`, `region`. (Supabase `auth.users` holds credentials.)
- `dealers` — dealer org; pricing tier.
- `po_clients` — dealer's end customers (address book).
- `products`, `regions`, `busbar_types`, `addons`, `price_lists` — reference data + price history.
- `orders` — header: dealer, po_client, product, order_type, area, shipping method, address (structured), notes, rush flag, status, computed totals.
- `order_panels` — per panel: label, width_mm, height_mm, sqft (calc), ratio (calc), busbar_type.
- `order_addons` — add-on line items with qty.
- `attachments` — Supabase Storage refs, FK `order_id`/`panel_id`, version, uploader, uploaded_at.
- `qr_codes` — `qr_id`, FK `panel_id`/`order_id`, `dpp_link`.
- `shipments` (light) — method, carrier, tracking_number, status (manual entry in MVP; courier API is Phase 4).
- `status_history` — append-only: order_id, from, to, by_user, at, comment.
- `audit_log`, `notifications` (log).

**Roles in MVP:** implement a proper role system (role enum + `user_roles` many-to-many, multi-role supported per TZ), but only use **Dealer / Staff (internal) / Admin** initially. Phases 2–4 split Staff into Production / Logistics / Finance / Subcontractor without rework.

**Deferred entities** (later phases): `production_jobs`, `tempering_jobs`, `subcontractors`, `invoices`, `payments`, `bank_statements`, `dealer_credit`.

## 5. MVP scope

**In:** order header (TZ 4.1) · dynamic N-panel blocks (4.2) · auto-calc SqFt + ratio (4.4) · 7-type busbar SVG selector with >3 m→type 7 recommendation (4.3) · add-ons (4.5) · shipping method + structured address + notes + rush flag (4.6) · summary screen + **PDF spec** (4.7) · **attachments** to Storage, per order/panel, versioned (4.8) · **DPP QR link** fetch + embed (4.9 via DPP API) · roles Dealer/Staff/Admin · full **status lifecycle** for film + history · internal dashboard (table/kanban + filters) · **dealer cabinet** (list, draft, copy/re-order, documents, PO address book) · pricing engine · core **email** triggers · manual shipment tracking entry.

**Out (deferred):** invoicing & payments (Ph 2) · auto bank-reconciliation (2.5) · Smart-glass form + subcontractor/tempering portal (3) · client/PO portal + public tracking + courier API (4) · analytics + SLA timers + price-mgmt polish + SMS/CRM (5).

## 6. Key logic

- **Auto-calc:** `SqFt = (W_mm × H_mm) / 92903`; `Ratio = max(W,H)/min(W,H)` formatted `X.X : 1`; order `Total SF` = Σ panel SqFt.
- **Busbar rule:** if `max(W,H) > 3000 mm` → recommend/limit to type 7; otherwise all 7 selectable. Each type is an SVG schematic; selection previews on a panel sketch with polarity (blue +, red −).
- **Pricing:** `Total SF × price(product, region, dealer) + add-ons + shipping − discounts + sales tax`. Rounding per price-list rule. (Sales-tax rules per state are an open item §9.)
- **PDF spec:** panels table (label, dims, SqFt, ratio, busbar) + add-ons + shipping/address/notes + totals + QR(s). Generated for dealer/client/production.
- **Status lifecycle (film):** Draft → Submitted → Under Review (Rejected/Needs Changes branch) → Approved → Awaiting Payment → Paid → In Production (Cutting → Busbar → QC → QR) → Ready to Ship → Shipped → Delivered → Completed. Side branches: On Hold, Cancelled, Replacement/Warranty. (In MVP without payments, Awaiting Payment→Paid can be a manual staff toggle; full gating lands in Phase 2.)
- **Notifications (MVP triggers):** submitted/received; approved/rejected; in production; ready/shipped (tracking); delivered. **MVP recipients: dealer + internal staff only** (client-facing emails arrive with the Phase 4 client portal).

## 7. Roadmap (TZ §16.16 AI-assisted hours)

| Phase | Content | Hrs |
|---|---|---|
| **1 — MVP** | Smart-Film orders, roles, statuses, PDF/QR(DPP)/attachments, email, dealer cabinet | 290–430 |
| 2 | Invoicing (PDF, bank ref) + manual payment confirm + credit limits/Net terms | 90–135 |
| 2.5 | Auto bank-statement reconciliation (CSV/MT940/CAMT) | 50–80 |
| 3 | Smart-glass form + subcontractor (tempering) portal + routing | 115–170 |
| 4 | Client (PO) portal + public tracking + courier integration | 85–130 |
| 5 | Analytics/dashboards + SLA timers + price mgmt + opt. SMS/CRM | 85–130 |

Note: dropping the in-platform product page (now DPP) trims a few hours from Phase 1's QR block.

## 8. MVP build steps (ordered; dependencies top-down)

1. **Foundation** — Next.js+TS+Tailwind+shadcn; **Supabase CLI local stack** (Docker); env; deploy skeleton (Vercel or Coolify); CI.
2. **Data model** — Supabase SQL migrations for MVP entities + seed reference data; generate TS types.
3. **Auth + RBAC** *(risk block — early, tested hard)* — Supabase Auth + `@supabase/ssr`; role system; **RLS policies** (dealer/region visibility).
4. **Reference-data admin** — CRUD for products/regions/busbars/add-ons/price-lists + price history.
5. **Order form core** — header + dynamic panel blocks + auto-calc (SqFt/ratio) + Zod validation.
6. **Busbar selector** — 7 SVG schematics + preview overlay + >3 m→type 7 rule.
7. **Add-ons + shipping/address + notes + rush flag.**
8. **Pricing engine** — Total SF × price + add-ons + shipping − discounts + tax.
9. **Summary screen + PDF spec** (react-pdf).
10. **Attachments** — Supabase Storage presigned upload, per order/panel, versions.
11. **DPP integration** — fetch QR link via API, store mapping, embed in spec.
12. **Status state-machine** + `status_history` + role-gated transitions.
13. **Internal dashboard** (table/kanban + filters) + **dealer cabinet** (list, draft, copy/re-order, docs, PO address book).
14. **Email notifications** — Resend templates + triggers.
15. **Hardening** — audit log, security pass (XSS/CSRF/injection, RLS review), Supabase backup config, E2E tests on critical flows.

## 9. Open items

- **DPP API contract** (step 11): endpoint, auth, request payload, response shape (hosted QR image vs URL-to-encode vs `qr_id`). Specced against a clean interface until provided.
- **TZ §15 open questions affecting MVP:** full product/region list; pricing rules (fixed vs dealer-specific discounts); **sales-tax rules per state**; whether public self-service client ordering is ever needed (currently dealer-only). Items on payments/subcontractors/courier affect later phases only.

## 10. Non-functional

- **Security:** HTTPS, RLS-enforced access, Supabase-managed password hashing, PII protection (addresses/phones), audit log, XSS/CSRF/injection defenses.
- **Performance:** core operations < 1.5 s typical load.
- **Availability:** target ≥ 99.5%.
- **Backups:** Supabase managed + PITR; ≤ 24 h recovery point.
- **Responsive:** desktop + mobile (form is filled on phones).
- **i18n:** US English now; architecture allows adding languages.
