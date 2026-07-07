# OWC Sales Machine — Lead Intake Automation Plan (MVP Part 2)

> **For agentic workers:** implement task-by-task, TDD where noted. Checkbox (`- [ ]`) steps. Verify code with `npx tsc --noEmit` only — do NOT run `next build`/`next dev` while the user's dev server is up (shared `.next` corruption).

**Goal:** Turn the first station (Lead intake) `auto`/`assisted`: a public `/intake` form on the site creates a deal + flags it for review (auto-ack deferred); an authenticated "New lead" page structures pasted inbound text via Claude into an editable draft (assisted); contacts are deduped so the same person doesn't spawn duplicate deals.

**Architecture:** Public intake writes through a **service-role** Supabase client (the visitor has no session, and RLS is granted to `authenticated`), so the service key stays server-only in the route handler. Pure intake logic (contact normalization, row building) lives in `src/lib/deals/intake.ts` and is unit-tested. The AI parse runs server-side via `@anthropic-ai/sdk` (`claude-haiku-4-5`, structured outputs) behind an authenticated route.

**Tech Stack:** Next.js 15 route handlers + server components, `@supabase/supabase-js` (service role), `@anthropic-ai/sdk` + `zod` structured outputs, existing `src/lib/deals/*`.

**Decisions (locked):** auto-ack email = **deferred (stub)**; AI parse = **Anthropic, `claude-haiku-4-5`** (config constant `LEAD_MODEL`); intake surface = **public `/intake` page in this app**.

**Depends on:** Plan 1 (spine) + Plan 1.5 (auth) complete; migration `0001_spine.sql` applied; `.env.local` populated.

---

## File Structure

```
supabase/migrations/0002_intake.sql          # request_text, contact_norm, index
src/lib/deals/
  types.ts          # (edit) add request_text, contact_norm to Deal
  intake.ts         # normalizeContact, buildDealInsert (pure)
  intake.test.ts
  intakeRepo.ts     # intakeLead: dedupe + create (service role)
src/lib/supabase/
  service.ts        # getServiceSupabase() — server-only, service role
src/lib/ai/
  parseLead.ts      # Claude structured extraction
src/app/
  intake/page.tsx           # public lead form
  intake/thanks/page.tsx    # public thank-you
  api/intake/route.ts       # public POST → create deal
  api/leads/parse/route.ts  # authenticated POST → ParsedLead draft
  (app)/leads/new/page.tsx  # authenticated paste→review→create
src/lib/supabase/middleware.ts   # (edit) make /intake + /api/intake public
src/components/board/PhaseColumn.tsx  # (untouched)
src/app/(app)/layout.tsx              # (edit) add "New lead" nav link
```

---

## Task B1: Migration + Deal type

**Files:**
- Create: `supabase/migrations/0002_intake.sql`
- Modify: `src/lib/deals/types.ts`

- [ ] **Step 1: `supabase/migrations/0002_intake.sql`**

```sql
alter table public.deals add column request_text text;
alter table public.deals add column contact_norm text;

-- Dedupe lookups only ever target active deals by normalized contact.
create index deals_contact_norm_active_idx
  on public.deals (contact_norm)
  where status = 'active' and contact_norm is not null;
```

- [ ] **Step 2: Apply it** — Supabase Dashboard → SQL Editor → Run (same as 0001). Then `select column_name from information_schema.columns where table_name='deals' and column_name in ('request_text','contact_norm');` returns both.

- [ ] **Step 3: Add the fields to the `Deal` type**

In `src/lib/deals/types.ts`, add two fields to the `Deal` interface (after `amount`):

```ts
  amount: number | null;
  request_text: string | null;
  contact_norm: string | null;
  needs_review: boolean;
```

- [ ] **Step 4: Type-check + commit**

Run: `npx tsc --noEmit` → clean.
```bash
git add supabase/migrations/0002_intake.sql src/lib/deals/types.ts
git commit -m "feat(intake): db columns request_text + contact_norm; extend Deal type"
```

---

## Task B2: Pure intake logic

**Files:**
- Create: `src/lib/deals/intake.ts`
- Test: `src/lib/deals/intake.test.ts`

- [ ] **Step 1: Write the failing test**

`src/lib/deals/intake.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { normalizeContact, buildDealInsert } from "./intake";

describe("normalizeContact", () => {
  it("lowercases and trims emails", () => {
    expect(normalizeContact("  John@Example.COM ")).toBe("john@example.com");
  });
  it("strips non-digits from phones", () => {
    expect(normalizeContact("+49 160 90990001")).toBe("4916090990001");
    expect(normalizeContact("(160) 909-0001")).toBe("1609090001");
  });
  it("returns empty string for blank input", () => {
    expect(normalizeContact("")).toBe("");
    expect(normalizeContact("   ")).toBe("");
  });
});

describe("buildDealInsert", () => {
  it("builds a stage-1 review-flagged active row with normalized contact", () => {
    const row = buildDealInsert({
      client_name: "  Acme  ",
      client_contact: "Info@Acme.com",
      client_language: "it",
      message: "Serve un preventivo per 5 finestre",
      source: "site",
    });
    expect(row).toEqual({
      client_name: "Acme",
      client_language: "it",
      client_contact: "Info@Acme.com",
      contact_norm: "info@acme.com",
      source: "site",
      request_text: "Serve un preventivo per 5 finestre",
      stage: 1,
      status: "active",
      needs_review: true,
    });
  });
  it("defaults language to uk and nulls empty optionals", () => {
    const row = buildDealInsert({
      client_name: "X",
      client_contact: "",
      client_language: "",
      message: "",
      source: "messenger",
    });
    expect(row.client_language).toBe("uk");
    expect(row.client_contact).toBeNull();
    expect(row.request_text).toBeNull();
    expect(row.contact_norm).toBe("");
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

Run: `npx vitest run src/lib/deals/intake.test.ts` → FAIL (module not found).

- [ ] **Step 3: Implement**

`src/lib/deals/intake.ts`:
```ts
import type { Source } from "./types";

export interface IntakeInput {
  client_name: string;
  client_contact: string;
  client_language: string;
  message: string;
  source: Source;
}

export interface DealInsert {
  client_name: string;
  client_language: string;
  client_contact: string | null;
  contact_norm: string;
  source: Source;
  request_text: string | null;
  stage: number;
  status: "active";
  needs_review: boolean;
}

// Normalize a contact for dedupe: emails lowercased/trimmed; phones reduced to digits.
export function normalizeContact(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  if (trimmed.includes("@")) return trimmed.toLowerCase();
  return trimmed.replace(/\D/g, "");
}

export function buildDealInsert(input: IntakeInput): DealInsert {
  const contact = input.client_contact.trim();
  const message = input.message.trim();
  return {
    client_name: input.client_name.trim(),
    client_language: input.client_language.trim() || "uk",
    client_contact: contact || null,
    contact_norm: normalizeContact(contact),
    source: input.source,
    request_text: message || null,
    stage: 1,
    status: "active",
    needs_review: true,
  };
}
```

- [ ] **Step 4: Run to confirm it passes**

Run: `npx vitest run src/lib/deals/intake.test.ts` → PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/deals/intake.ts src/lib/deals/intake.test.ts
git commit -m "feat(intake): pure contact normalization + deal-insert builder"
```

---

## Task B3: Service-role client + intake repo

**Files:**
- Create: `src/lib/supabase/service.ts`
- Create: `src/lib/deals/intakeRepo.ts`

- [ ] **Step 1: Service-role client (server-only)**

`src/lib/supabase/service.ts`:
```ts
import { createClient } from "@supabase/supabase-js";

// SERVER-ONLY. Uses the service-role key to bypass RLS for public (unauthenticated)
// intake writes. Never import this into a Client Component.
export function getServiceSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Supabase service env not configured");
  return createClient(url, key, { auth: { persistSession: false } });
}
```

- [ ] **Step 2: Intake repo (dedupe + create)**

`src/lib/deals/intakeRepo.ts`:
```ts
import { getServiceSupabase } from "@/lib/supabase/service";
import { buildDealInsert, type IntakeInput } from "./intake";

export interface IntakeResult {
  status: "created" | "linked";
  dealId: string;
}

// Create a deal from an inbound lead, or link to an existing active deal with the
// same normalized contact instead of duplicating.
export async function intakeLead(input: IntakeInput): Promise<IntakeResult> {
  const supabase = getServiceSupabase();
  const row = buildDealInsert(input);

  if (row.contact_norm) {
    const { data: existing, error: findErr } = await supabase
      .from("deals")
      .select("id")
      .eq("status", "active")
      .eq("contact_norm", row.contact_norm)
      .limit(1)
      .maybeSingle();
    if (findErr) throw findErr;
    if (existing) {
      const { error: evErr } = await supabase.from("stage_events").insert({
        deal_id: existing.id,
        from_stage: 1,
        to_stage: 1,
        actor: "auto",
        note: `Повторний запит (${row.source})${row.request_text ? ": " + row.request_text.slice(0, 200) : ""}`,
      });
      if (evErr) throw evErr;
      return { status: "linked", dealId: existing.id };
    }
  }

  const { data: created, error: insErr } = await supabase
    .from("deals")
    .insert(row)
    .select("id")
    .single();
  if (insErr) throw insErr;

  const { error: evErr } = await supabase.from("stage_events").insert({
    deal_id: created.id,
    from_stage: null,
    to_stage: 1,
    actor: "auto",
    note: `Лід прийнято (${row.source})`,
  });
  if (evErr) throw evErr;

  return { status: "created", dealId: created.id };
}
```

- [ ] **Step 3: Type-check + commit**

Run: `npx tsc --noEmit` → clean.
```bash
git add src/lib/supabase/service.ts src/lib/deals/intakeRepo.ts
git commit -m "feat(intake): service-role client + intakeLead (dedupe or create)"
```

---

## Task B4: Public intake form + API + middleware

**Files:**
- Modify: `src/lib/supabase/middleware.ts`
- Create: `src/app/api/intake/route.ts`
- Create: `src/app/intake/page.tsx`
- Create: `src/app/intake/thanks/page.tsx`

- [ ] **Step 1: Make `/intake` (pages) and `/api/intake` (exact) public in middleware**

In `src/lib/supabase/middleware.ts`, replace the `PUBLIC_PATHS` constant and the `isPublic` line:

```ts
// Prefix-public paths (page + subpages). Exact-public paths (a single API route).
const PUBLIC_PREFIXES = ["/login", "/intake"];
const PUBLIC_EXACT = ["/api/intake"];
```

and:

```ts
  const path = request.nextUrl.pathname;
  const isPublic =
    PUBLIC_EXACT.includes(path) ||
    PUBLIC_PREFIXES.some((p) => path === p || path.startsWith(p + "/"));
```

(This keeps `/api/leads/parse` and `/leads/new` protected — `/intake` prefix does not match `/api/...`, and `/api/intake` is exact so `/api/intake/anything` is not public.)

- [ ] **Step 2: Public POST endpoint**

`src/app/api/intake/route.ts`:
```ts
import { NextResponse } from "next/server";
import { z } from "zod";
import { intakeLead } from "@/lib/deals/intakeRepo";

const SOURCES = ["site", "ads", "email", "messenger", "other"] as const;

const Body = z.object({
  client_name: z.string().trim().min(1).max(200),
  client_contact: z.string().trim().max(200).default(""),
  client_language: z.string().trim().max(10).default("uk"),
  message: z.string().trim().max(5000).default(""),
  source: z.enum(SOURCES).default("site"),
  // Honeypot: real users leave it empty; bots fill it.
  company_website: z.string().max(0).optional().default(""),
});

export async function POST(req: Request) {
  let json: unknown;
  try {
    json = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const parsed = Body.safeParse(json);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid input" }, { status: 400 });
  }
  const { company_website, ...input } = parsed.data;
  if (company_website) {
    // Honeypot tripped — pretend success, create nothing.
    return NextResponse.json({ status: "ok" });
  }
  try {
    const result = await intakeLead(input);
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ error: "intake failed" }, { status: 500 });
  }
}
```

- [ ] **Step 3: Public form page**

`src/app/intake/page.tsx`:
```tsx
"use client";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export default function IntakePage() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState("");

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const fd = new FormData(e.currentTarget);
    const payload = {
      client_name: String(fd.get("client_name") ?? ""),
      client_contact: String(fd.get("client_contact") ?? ""),
      message: String(fd.get("message") ?? ""),
      company_website: String(fd.get("company_website") ?? ""),
    };
    start(async () => {
      const res = await fetch("/api/intake", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        setError("Не вдалося надіслати запит. Спробуйте ще раз.");
        return;
      }
      router.push("/intake/thanks");
    });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-3 rounded-lg border bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Запит на прорахунок вікон</h1>
        <input name="client_name" required placeholder="Ім'я" className="w-full rounded border p-2 text-sm" />
        <input name="client_contact" required placeholder="Email або телефон" className="w-full rounded border p-2 text-sm" />
        <textarea name="message" rows={4} placeholder="Опишіть, що потрібно (розміри, кількість, місто)" className="w-full rounded border p-2 text-sm" />
        {/* Honeypot: hidden from users */}
        <input name="company_website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={pending} className="w-full rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
          {pending ? "Надсилаємо…" : "Надіслати запит"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 4: Thank-you page**

`src/app/intake/thanks/page.tsx`:
```tsx
export default function IntakeThanksPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="max-w-md rounded-lg border bg-white p-6 text-center shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Дякуємо!</h1>
        <p className="mt-2 text-sm text-slate-600">
          Ваш запит отримано. Ми звʼяжемося з вами найближчим часом.
        </p>
      </div>
    </main>
  );
}
```

- [ ] **Step 5: Type-check + commit**

Run: `npx tsc --noEmit` → clean.
```bash
git add src/lib/supabase/middleware.ts src/app/api/intake "src/app/intake"
git commit -m "feat(intake): public /intake form + POST /api/intake (service-role, honeypot)"
```

---

## Task B5: AI lead parsing

**Files:**
- Modify: `package.json` (+ `@anthropic-ai/sdk`), then `npm install`
- Modify: `.env.local.example` (+ `ANTHROPIC_API_KEY=`)
- Create: `src/lib/ai/parseLead.ts`
- Create: `src/app/api/leads/parse/route.ts`

- [ ] **Step 1: Add the dependency**

Run: `npm install @anthropic-ai/sdk`
Expected: `@anthropic-ai/sdk` added to `dependencies`.

- [ ] **Step 2: Add the key placeholder to the example env**

Append to `.env.local.example`:
```
ANTHROPIC_API_KEY=
```
(The real key goes in the gitignored `.env.local` — the user adds it.)

- [ ] **Step 3: `src/lib/ai/parseLead.ts`**

```ts
import Anthropic from "@anthropic-ai/sdk";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import { z } from "zod";

// Cheap structured extraction; swap here to change the model.
const LEAD_MODEL = "claude-haiku-4-5";

const LeadSchema = z.object({
  client_name: z.string().describe("Person or company name; empty string if not stated"),
  client_language: z.string().describe("ISO 639-1 code of the language the message is written in, e.g. uk, ru, it, de, en"),
  client_contact: z.string().describe("Email or phone number if present; empty string otherwise"),
  summary: z.string().describe("One-sentence summary of what the client wants, written in the client's language"),
});

export type ParsedLead = z.infer<typeof LeadSchema>;

export async function parseLead(text: string): Promise<ParsedLead> {
  const client = new Anthropic(); // reads ANTHROPIC_API_KEY from env
  const response = await client.messages.parse({
    model: LEAD_MODEL,
    max_tokens: 1024,
    system:
      "You extract structured lead information from an inbound windows-sales inquiry. " +
      "Detect the language the message is written in and report it as an ISO 639-1 code. " +
      "Never invent contact details — use an empty string if none are present.",
    messages: [{ role: "user", content: text }],
    output_config: { format: zodOutputFormat(LeadSchema) },
  });
  if (!response.parsed_output) throw new Error("Lead parse returned no structured output");
  return response.parsed_output;
}
```

- [ ] **Step 4: Authenticated parse route**

`src/app/api/leads/parse/route.ts`:
```ts
import { NextResponse } from "next/server";
import { z } from "zod";
import { getServerSupabase } from "@/lib/supabase/server";
import { parseLead } from "@/lib/ai/parseLead";

const Body = z.object({ text: z.string().trim().min(1).max(5000) });

export async function POST(req: Request) {
  // Operator-only: require an authenticated session (middleware also gates this route).
  const supabase = await getServerSupabase();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "invalid input" }, { status: 400 });

  try {
    const lead = await parseLead(parsed.data.text);
    return NextResponse.json(lead);
  } catch {
    return NextResponse.json({ error: "parse failed" }, { status: 502 });
  }
}
```

- [ ] **Step 5: Type-check + commit**

Run: `npx tsc --noEmit` → clean.
```bash
git add package.json package-lock.json .env.local.example src/lib/ai/parseLead.ts src/app/api/leads/parse/route.ts
git commit -m "feat(intake): Claude structured lead parsing + authenticated parse route"
```

---

## Task B6: "New lead" page (paste → review → create) + nav

**Files:**
- Create: `src/app/(app)/leads/new/page.tsx`
- Modify: `src/app/(app)/layout.tsx` (add nav link)

- [ ] **Step 1: The New-lead page**

`src/app/(app)/leads/new/page.tsx`:
```tsx
"use client";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

const SOURCES = ["email", "messenger", "ads", "other"] as const;

export default function NewLeadPage() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [raw, setRaw] = useState("");
  const [draft, setDraft] = useState<null | {
    client_name: string; client_contact: string; client_language: string; message: string; source: string;
  }>(null);

  function onParse() {
    start(async () => {
      const res = await fetch("/api/leads/parse", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: raw }),
      });
      if (!res.ok) { toast.error("Не вдалося розпізнати текст"); return; }
      const lead = await res.json();
      setDraft({
        client_name: lead.client_name ?? "",
        client_contact: lead.client_contact ?? "",
        client_language: lead.client_language || "uk",
        message: lead.summary ?? raw,
        source: "other",
      });
    });
  }

  function onCreate() {
    if (!draft) return;
    start(async () => {
      const res = await fetch("/api/intake", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!res.ok) { toast.error("Не вдалося створити угоду"); return; }
      const { dealId, status } = await res.json();
      toast.success(status === "linked" ? "Прилінковано до наявної угоди" : "Угоду створено");
      router.push(`/deals/${dealId}`);
    });
  }

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-6">
      <h1 className="text-xl font-semibold text-slate-900">Новий лід</h1>

      {!draft && (
        <>
          <textarea
            value={raw} onChange={(e) => setRaw(e.target.value)} rows={8}
            placeholder="Встав текст запиту з email / месенджера…"
            className="w-full rounded border p-2 text-sm"
          />
          <button onClick={onParse} disabled={pending || !raw.trim()}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            {pending ? "Розпізнаємо…" : "Розпізнати (AI)"}
          </button>
        </>
      )}

      {draft && (
        <div className="space-y-3 rounded-lg border p-4">
          <label className="block text-sm">Ім'я
            <input value={draft.client_name} onChange={(e) => setDraft({ ...draft, client_name: e.target.value })}
              className="mt-1 w-full rounded border p-2 text-sm" />
          </label>
          <label className="block text-sm">Контакт
            <input value={draft.client_contact} onChange={(e) => setDraft({ ...draft, client_contact: e.target.value })}
              className="mt-1 w-full rounded border p-2 text-sm" />
          </label>
          <div className="flex gap-3">
            <label className="block text-sm flex-1">Мова
              <input value={draft.client_language} onChange={(e) => setDraft({ ...draft, client_language: e.target.value })}
                className="mt-1 w-full rounded border p-2 text-sm" />
            </label>
            <label className="block text-sm flex-1">Канал
              <select value={draft.source} onChange={(e) => setDraft({ ...draft, source: e.target.value })}
                className="mt-1 w-full rounded border p-2 text-sm">
                {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <label className="block text-sm">Запит
            <textarea value={draft.message} onChange={(e) => setDraft({ ...draft, message: e.target.value })} rows={3}
              className="mt-1 w-full rounded border p-2 text-sm" />
          </label>
          <div className="flex gap-2">
            <button onClick={onCreate} disabled={pending || !draft.client_name.trim()}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              {pending ? "Створюємо…" : "Створити угоду"}
            </button>
            <button onClick={() => setDraft(null)} disabled={pending}
              className="rounded border px-3 py-2 text-sm disabled:opacity-50">Назад</button>
          </div>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Add a nav link in the app header**

In `src/app/(app)/layout.tsx`, add a "New lead" link before the sign-out button. Replace the `<header>` block with:

```tsx
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <Link href="/pipeline" className="text-sm font-semibold text-slate-900">
          OWC Sales Machine
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/leads/new" className="text-sm text-slate-600 hover:text-slate-900">
            + Новий лід
          </Link>
          <SignOutButton />
        </div>
      </header>
```

- [ ] **Step 3: Type-check + commit**

Run: `npx tsc --noEmit` → clean.
```bash
git add "src/app/(app)/leads" "src/app/(app)/layout.tsx"
git commit -m "feat(intake): New-lead page (paste→AI parse→review→create) + nav link"
```

---

## Verification (controller, live — no dev server)

After implementation, the controller runs one node smoke test (created, run, deleted) against the live DB + the parse route logic:
1. `intakeLead` with a new contact → `created`; a second call with the same contact → `linked` (no duplicate). Clean up both.
2. `parseLead("Здравствуйте, нужен расчёт на 3 окна, тел 0501112233")` → returns `client_language` ≈ `ru`, a non-empty `client_contact`, a summary. (Requires `ANTHROPIC_API_KEY` in `.env.local`.)

Browser checks (the user runs these): visit `/intake` logged-out → submit → see `/intake/thanks` and a new card in the Lead phase; `/leads/new` logged-in → paste text → review → create → lands on the deal.

## Self-review checklist
- Public write path uses the **service-role** client (RLS is `to authenticated`; a visitor has no session). Service key is only in `service.ts` (server) — never in a Client Component.
- `/api/intake` is exact-public; `/api/leads/parse` and `/leads/new` stay authenticated (middleware + in-route `getUser()` check).
- Dedupe targets **active** deals by `contact_norm`; empty contact skips dedupe (always creates).
- Honeypot + length caps bound public-endpoint abuse (rate-limiting noted as future hardening).
- `claude-haiku-4-5` via `LEAD_MODEL` constant; structured output validated by zod schema.
- Single-row inserts only (avoids the PostgREST NULL-on-omitted-NOT-NULL batch pitfall).

## Next
Plan 3 — Proposal station: wire `offwhite-proposals` as a service the Proposal station calls (assisted → generates the client PDF at +15% for review).
