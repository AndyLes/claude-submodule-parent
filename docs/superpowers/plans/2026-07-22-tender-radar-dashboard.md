# Tender-Radar Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A single-user, read-only Next.js dashboard over the existing Tender-Radar Supabase data — Overview, filterable Tenders table, and a Results/Competitors view.

**Architecture:** Next.js 15 App Router (TypeScript, Tailwind). Auth = Supabase magic-link gated to one owner email via `@supabase/ssr` middleware. Data = a server-only Supabase service-role client reading the collector's existing `tenders`/`bid_results`/`source_health` tables (no schema changes, no writes); small datasets are aggregated in TypeScript (unit-tested). Verified by `next build`, never by spawning `next dev` (Smart Film lesson: orphaned dev servers corrupt `.next`).

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, `@supabase/supabase-js`, `@supabase/ssr`, Vitest.

**Repo:** new `C:\SuperWork\projects\tender-radar-dashboard\` (separate git repo + Vercel project). Design spec: `docs/superpowers/specs/2026-07-22-tender-radar-dashboard-design.md`. Reads Supabase project ref `cofplvbfzuppwykxhqbr`.

---

### Task 1: Scaffold Next.js app + deps + Vitest

**Files:** Create the app skeleton via CLI, then config files.

- [ ] **Step 1: Scaffold** (non-interactive)

```powershell
cd C:\SuperWork\projects
npx create-next-app@latest tender-radar-dashboard --ts --tailwind --app --eslint --src-dir --import-alias "@/*" --no-turbopack --use-npm
cd tender-radar-dashboard
git init 2>$null
```

- [ ] **Step 2: Add deps**

```powershell
npm install @supabase/supabase-js @supabase/ssr
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react
```

- [ ] **Step 3: Add `vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
```

- [ ] **Step 4: Add test script** to `package.json` `"scripts"`: `"test": "vitest run"`.

- [ ] **Step 5: Write `.env.example`**

```
NEXT_PUBLIC_SUPABASE_URL=https://cofplvbfzuppwykxhqbr.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
OWNER_EMAIL=andriy.leso@gmail.com
```

Add `.env*.local` and `.env` to `.gitignore` (create-next-app already ignores `.env*`; confirm).

- [ ] **Step 6: Sanity test `src/lib/__tests__/smoke.test.ts`**

```ts
import { describe, it, expect } from "vitest";
describe("smoke", () => { it("runs", () => { expect(1 + 1).toBe(2); }); });
```

- [ ] **Step 7: Run** `npm test` → 1 passed. Then `npm run build` → succeeds (default create-next-app page).

- [ ] **Step 8: Commit**

```powershell
git add -A; git commit -m "chore: scaffold tender-radar-dashboard (next+ts+tailwind+vitest)"
```

---

### Task 2: Domain types + pure logic (filters, status, competitor stats) — TDD

**Files:**
- Create: `src/lib/types.ts`, `src/lib/logic.ts`
- Test: `src/lib/__tests__/logic.test.ts`

- [ ] **Step 1: Write the failing test `src/lib/__tests__/logic.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { isOpen, filterTenders, competitorStats, projectSpreads } from "@/lib/logic";
import type { Tender, BidResult } from "@/lib/types";

const now = new Date("2026-07-22T00:00:00Z");
function t(p: Partial<Tender>): Tender {
  return { id: 1, source: "ctsource", external_id: "1", title: "Window job", owner: "Town",
    state: "CT", trade_classes: null, est_value: null, bid_deadline: "2026-08-01T00:00:00Z",
    listing_url: "https://x", plans_url: null, status: "new",
    first_seen: "2026-07-01T00:00:00Z", last_seen: "2026-07-20T00:00:00Z", ...p };
}

describe("isOpen", () => {
  it("future deadline is open", () => expect(isOpen(t({}), now)).toBe(true));
  it("past deadline is closed", () => expect(isOpen(t({ bid_deadline: "2026-07-01T00:00:00Z" }), now)).toBe(false));
  it("null deadline counts as open", () => expect(isOpen(t({ bid_deadline: null }), now)).toBe(true));
  it("status closed is closed regardless", () => expect(isOpen(t({ status: "closed" }), now)).toBe(false));
});

describe("filterTenders", () => {
  const rows = [t({ id: 1, state: "CT", source: "ctsource", title: "Curtain wall" }),
                t({ id: 2, state: "MA", source: "dcamm_bidexpress", title: "Metal Windows" })];
  it("filters by state", () => expect(filterTenders(rows, { state: "MA" }, now).map(r => r.id)).toEqual([2]));
  it("filters by source", () => expect(filterTenders(rows, { source: "ctsource" }, now).map(r => r.id)).toEqual([1]));
  it("text search matches title case-insensitively", () =>
    expect(filterTenders(rows, { q: "curtain" }, now).map(r => r.id)).toEqual([1]));
  it("open filter drops past-deadline", () =>
    expect(filterTenders([t({ id: 3, bid_deadline: "2026-07-01T00:00:00Z" })], { openOnly: true }, now)).toEqual([]));
});

describe("competitorStats", () => {
  const br: BidResult[] = [
    { id: 1, source: "ctsource", external_id: "X", project_title: "X", bidder_name: "A", amount: 100, is_winner: true, award_date: null, collected_at: "2026-07-20T00:00:00Z" },
    { id: 2, source: "ctsource", external_id: "X", project_title: "X", bidder_name: "B", amount: 150, is_winner: false, award_date: null, collected_at: "2026-07-20T00:00:00Z" },
    { id: 3, source: "ri_osp", external_id: "Y", project_title: "Y", bidder_name: "A", amount: null, is_winner: false, award_date: null, collected_at: "2026-07-20T00:00:00Z" },
  ];
  it("aggregates bids/wins", () => {
    const s = Object.fromEntries(competitorStats(br).map(x => [x.bidder, x]));
    expect(s["A"].bids).toBe(2); expect(s["A"].wins).toBe(1);
  });
  it("spread for priced project only", () => {
    const sp = Object.fromEntries(projectSpreads(br).map(x => [x.external_id, x]));
    expect(sp["X"].low).toBe(100); expect(sp["X"].high).toBe(150); expect(Math.round(sp["X"].spreadPct)).toBe(50);
    expect(sp["Y"]).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run** `npm test` → FAIL (module not found).

- [ ] **Step 3: Write `src/lib/types.ts`**

```ts
export type TenderStatus = "new" | "notified" | "closed" | "results_collected";

export interface Tender {
  id: number; source: string; external_id: string; title: string; owner: string | null;
  state: string; trade_classes: string | null; est_value: number | null;
  bid_deadline: string | null; listing_url: string; plans_url: string | null;
  status: TenderStatus; first_seen: string; last_seen: string;
}

export interface BidResult {
  id: number; source: string; external_id: string; project_title: string; bidder_name: string;
  amount: number | null; is_winner: boolean; award_date: string | null; collected_at: string;
}

export interface SourceHealth {
  source: string; last_success: string | null; last_error: string | null;
  last_error_at: string | null; consecutive_failures: number;
}

export interface TenderFilters { state?: string; source?: string; q?: string; openOnly?: boolean; }
```

- [ ] **Step 4: Write `src/lib/logic.ts`**

```ts
import type { Tender, BidResult, TenderFilters } from "@/lib/types";

export function isOpen(t: Tender, now: Date): boolean {
  if (t.status === "closed" || t.status === "results_collected") return false;
  if (!t.bid_deadline) return true;
  return new Date(t.bid_deadline).getTime() > now.getTime();
}

export function filterTenders(rows: Tender[], f: TenderFilters, now: Date): Tender[] {
  return rows.filter((r) => {
    if (f.state && r.state !== f.state) return false;
    if (f.source && r.source !== f.source) return false;
    if (f.openOnly && !isOpen(r, now)) return false;
    if (f.q && !r.title.toLowerCase().includes(f.q.toLowerCase())) return false;
    return true;
  });
}

export function competitorStats(rows: BidResult[]): { bidder: string; bids: number; wins: number; winRate: number }[] {
  const agg = new Map<string, { bids: number; wins: number }>();
  for (const r of rows) {
    const a = agg.get(r.bidder_name) ?? { bids: 0, wins: 0 };
    a.bids += 1; if (r.is_winner) a.wins += 1; agg.set(r.bidder_name, a);
  }
  return [...agg.entries()]
    .map(([bidder, a]) => ({ bidder, bids: a.bids, wins: a.wins, winRate: a.bids ? a.wins / a.bids : 0 }))
    .sort((x, y) => y.wins - x.wins || y.bids - x.bids);
}

export function projectSpreads(rows: BidResult[]): { source: string; external_id: string; project_title: string; low: number; high: number; nBidders: number; spreadPct: number }[] {
  const byProj = new Map<string, { title: string; source: string; ext: string; amounts: number[] }>();
  for (const r of rows) {
    const key = `${r.source}:${r.external_id}`;
    const p = byProj.get(key) ?? { title: r.project_title, source: r.source, ext: r.external_id, amounts: [] };
    if (r.amount != null) p.amounts.push(r.amount);
    byProj.set(key, p);
  }
  return [...byProj.values()]
    .filter((p) => p.amounts.length >= 2)
    .map((p) => {
      const low = Math.min(...p.amounts), high = Math.max(...p.amounts);
      return { source: p.source, external_id: p.ext, project_title: p.title, low, high,
        nBidders: p.amounts.length, spreadPct: low ? ((high - low) / low) * 100 : 0 };
    })
    .sort((a, b) => b.spreadPct - a.spreadPct);
}
```

- [ ] **Step 5: Run** `npm test` → all PASS. **Step 6: Commit** `git add -A; git commit -m "feat(logic): tender filters, status, competitor stats + tests"`.

---

### Task 3: Supabase server client + data queries

**Files:**
- Create: `src/lib/supabase-admin.ts`, `src/lib/data.ts`

- [ ] **Step 1: Write `src/lib/supabase-admin.ts`** (server-only service-role client — never import from a client component)

```ts
import "server-only";
import { createClient } from "@supabase/supabase-js";

export function supabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  return createClient(url, key, { auth: { persistSession: false } });
}
```

- [ ] **Step 2: Write `src/lib/data.ts`** (read functions; small volumes → fetch and let logic.ts aggregate)

```ts
import "server-only";
import { supabaseAdmin } from "@/lib/supabase-admin";
import type { Tender, BidResult, SourceHealth } from "@/lib/types";

export async function getTenders(): Promise<Tender[]> {
  const { data, error } = await supabaseAdmin()
    .from("tenders").select("*").order("bid_deadline", { ascending: true, nullsFirst: false });
  if (error) throw new Error(`tenders: ${error.message}`);
  return (data ?? []) as Tender[];
}

export async function getBidResults(): Promise<BidResult[]> {
  const { data, error } = await supabaseAdmin().from("bid_results").select("*");
  if (error) throw new Error(`bid_results: ${error.message}`);
  return (data ?? []) as BidResult[];
}

export async function getSourceHealth(): Promise<SourceHealth[]> {
  const { data, error } = await supabaseAdmin().from("source_health").select("*").order("source");
  if (error) throw new Error(`source_health: ${error.message}`);
  return (data ?? []) as SourceHealth[];
}
```

- [ ] **Step 3: Type-check** `npx tsc --noEmit` → no errors. (No unit test — these are thin IO wrappers; the aggregation logic they feed is tested in Task 2. A live check happens at deploy in Task 8.)

- [ ] **Step 4: Commit** `git add -A; git commit -m "feat(data): supabase service-role client + read queries"`.

**Setup note for Task 8 / deploy:** the `tenders`/`bid_results`/`source_health` tables were created by SQLAlchemy, not Supabase migrations. If PostgREST returns "relation does not exist in the schema cache", reload it once: Supabase Dashboard → Settings → API → "Reload schema", or run `NOTIFY pgrst, 'reload schema';` in the SQL editor. Verify with a live query in Task 8.

---

### Task 4: Auth — magic link gated to owner email

**Files:**
- Create: `src/lib/supabase-server.ts`, `src/middleware.ts`, `src/app/login/page.tsx`, `src/app/auth/confirm/route.ts`, `src/app/login/actions.ts`

- [ ] **Step 1: `src/lib/supabase-server.ts`** (SSR client bound to cookies)

```ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function supabaseServer() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (toSet) => toSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options)),
      },
    },
  );
}
```

- [ ] **Step 2: `src/middleware.ts`** — protect everything except `/login` and `/auth/*`; enforce owner email

```ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(req: NextRequest) {
  const res = NextResponse.next();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => req.cookies.getAll(),
        setAll: (toSet) => toSet.forEach(({ name, value, options }) => res.cookies.set(name, value, options)),
      },
    },
  );
  const { data: { user } } = await supabase.auth.getUser();
  const path = req.nextUrl.pathname;
  const isPublic = path.startsWith("/login") || path.startsWith("/auth");
  const owner = process.env.OWNER_EMAIL?.toLowerCase();
  const isOwner = !!user && user.email?.toLowerCase() === owner;
  if (!isPublic && !isOwner) return NextResponse.redirect(new URL("/login", req.url));
  if (path.startsWith("/login") && isOwner) return NextResponse.redirect(new URL("/", req.url));
  return res;
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
```

- [ ] **Step 3: `src/app/login/actions.ts`** (server action to send the magic link)

```ts
"use server";
import { supabaseServer } from "@/lib/supabase-server";

export async function sendMagicLink(_prev: unknown, formData: FormData) {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (email !== process.env.OWNER_EMAIL?.toLowerCase()) {
    return { ok: false, msg: "Not authorized." };
  }
  const supabase = await supabaseServer();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL ?? ""}/auth/confirm` },
  });
  return error ? { ok: false, msg: error.message } : { ok: true, msg: "Check your email for the sign-in link." };
}
```

- [ ] **Step 4: `src/app/login/page.tsx`**

```tsx
"use client";
import { useActionState } from "react";
import { sendMagicLink } from "./actions";

export default function Login() {
  const [state, action, pending] = useActionState(sendMagicLink, null as null | { ok: boolean; msg: string });
  return (
    <main className="min-h-screen grid place-items-center bg-slate-50">
      <form action={action} className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-800">Tender-Radar</h1>
        <p className="mt-1 text-sm text-slate-500">Sign in to continue.</p>
        <input name="email" type="email" required placeholder="you@example.com"
          className="mt-4 w-full rounded border border-slate-300 px-3 py-2 text-sm" />
        <button disabled={pending}
          className="mt-3 w-full rounded bg-slate-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
          {pending ? "Sending…" : "Send magic link"}
        </button>
        {state && <p className={`mt-3 text-sm ${state.ok ? "text-emerald-600" : "text-red-600"}`}>{state.msg}</p>}
      </form>
    </main>
  );
}
```

- [ ] **Step 5: `src/app/auth/confirm/route.ts`** (verify the OTP token from the email link)

```ts
import { type EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { supabaseServer } from "@/lib/supabase-server";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  if (token_hash && type) {
    const supabase = await supabaseServer();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) return NextResponse.redirect(new URL("/", req.url));
  }
  return NextResponse.redirect(new URL("/login", req.url));
}
```

- [ ] **Step 6: Type-check + build** `npx tsc --noEmit` then `npm run build` → succeed. **Commit** `git add -A; git commit -m "feat(auth): magic-link sign-in gated to owner email"`.

---

### Task 5: App shell (sidebar) + design tokens

**Files:**
- Modify: `src/app/layout.tsx`
- Create: `src/components/Sidebar.tsx`, `src/components/StatusBadge.tsx`

- [ ] **Step 1: `src/components/Sidebar.tsx`** (Smart Film language: left sidebar, slate/monochrome)

```tsx
import Link from "next/link";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/tenders", label: "Tenders" },
  { href: "/results", label: "Results" },
];

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r border-slate-200 bg-white">
      <div className="px-4 py-4 text-sm font-semibold text-slate-800">Tender-Radar</div>
      <nav className="px-2">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href}
            className="block rounded px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">{n.label}</Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: `src/components/StatusBadge.tsx`**

```tsx
const STYLES: Record<string, string> = {
  open: "bg-emerald-100 text-emerald-700",
  closed: "bg-slate-200 text-slate-600",
  results_collected: "bg-indigo-100 text-indigo-700",
};
export function StatusBadge({ label }: { label: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${STYLES[label] ?? "bg-slate-100 text-slate-600"}`}>{label}</span>;
}
```

- [ ] **Step 3: Replace `src/app/layout.tsx`** body with the shell

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = { title: "Tender-Radar" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-800">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
```

(Note: `/login` renders its own full-screen `<main>` — that's fine; the shell wraps it too but the login page is standalone-styled. If the sidebar-on-login is undesirable, move the shell into a `(app)` route group in a later refinement — out of scope for v1.)

- [ ] **Step 4: Build** `npm run build` → succeeds. **Commit** `git add -A; git commit -m "feat(ui): sidebar shell + status badge (smartfilm design language)"`.

---

### Task 6: Tenders page (primary) — filters + detail

**Files:**
- Create: `src/app/tenders/page.tsx`, `src/components/TendersTable.tsx`

- [ ] **Step 1: `src/components/TendersTable.tsx`** (client component: client-side filtering of the server-fetched rows)

```tsx
"use client";
import { useMemo, useState } from "react";
import type { Tender } from "@/lib/types";
import { filterTenders, isOpen } from "@/lib/logic";
import { StatusBadge } from "@/components/StatusBadge";

export function TendersTable({ rows }: { rows: Tender[] }) {
  const now = useMemo(() => new Date(), []);
  const [state, setState] = useState(""); const [source, setSource] = useState("");
  const [q, setQ] = useState(""); const [openOnly, setOpenOnly] = useState(true);
  const filtered = useMemo(
    () => filterTenders(rows, { state: state || undefined, source: source || undefined, q: q || undefined, openOnly }, now),
    [rows, state, source, q, openOnly, now]);
  const states = [...new Set(rows.map((r) => r.state))].sort();
  const sources = [...new Set(rows.map((r) => r.source))].sort();
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <input placeholder="Search title…" value={q} onChange={(e) => setQ(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-sm" />
        <select value={state} onChange={(e) => setState(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
          <option value="">All states</option>{states.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
          <option value="">All sources</option>{sources.map((s) => <option key={s}>{s}</option>)}
        </select>
        <label className="flex items-center gap-1 text-sm text-slate-600">
          <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} /> Open only
        </label>
        <span className="ml-auto self-center text-sm text-slate-500">{filtered.length} of {rows.length}</span>
      </div>
      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-left text-slate-600">
            <tr><th className="p-2">Title</th><th className="p-2">Owner</th><th className="p-2">State</th>
              <th className="p-2">Source</th><th className="p-2">Deadline</th><th className="p-2">Status</th></tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="p-2"><a href={r.listing_url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">{r.title}</a></td>
                <td className="p-2 text-slate-600">{r.owner ?? "—"}</td>
                <td className="p-2">{r.state}</td>
                <td className="p-2 text-slate-500">{r.source}</td>
                <td className="p-2">{r.bid_deadline ? new Date(r.bid_deadline).toLocaleDateString() : "—"}</td>
                <td className="p-2"><StatusBadge label={isOpen(r, now) ? "open" : (r.status === "results_collected" ? "results_collected" : "closed")} /></td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-400">No tenders match.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `src/app/tenders/page.tsx`** (server component fetches, passes to the client table)

```tsx
import { getTenders } from "@/lib/data";
import { TendersTable } from "@/components/TendersTable";

export const dynamic = "force-dynamic";

export default async function TendersPage() {
  let rows; try { rows = await getTenders(); } catch (e) {
    return <p className="text-red-600">Could not load tenders: {(e as Error).message}</p>;
  }
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Tenders</h1>
      <TendersTable rows={rows} />
    </div>
  );
}
```

- [ ] **Step 3: Build** `npm run build` → succeeds. **Commit** `git add -A; git commit -m "feat(ui): tenders page with filters"`.

---

### Task 7: Overview + Results pages

**Files:**
- Create: `src/app/page.tsx` (replace default), `src/app/results/page.tsx`

- [ ] **Step 1: `src/app/page.tsx`** (Overview: counters + source health)

```tsx
import { getTenders, getSourceHealth } from "@/lib/data";
import { isOpen } from "@/lib/logic";

export const dynamic = "force-dynamic";

export default async function Overview() {
  let tenders, health;
  try { [tenders, health] = await Promise.all([getTenders(), getSourceHealth()]); }
  catch (e) { return <p className="text-red-600">Could not load: {(e as Error).message}</p>; }
  const now = new Date();
  const open = tenders.filter((t) => isOpen(t, now));
  const byState = [...new Set(open.map((t) => t.state))].sort()
    .map((s) => ({ s, n: open.filter((t) => t.state === s).length }));
  const card = "rounded-lg border border-slate-200 bg-white p-4";
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Overview</h1>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}><div className="text-2xl font-semibold">{open.length}</div><div className="text-sm text-slate-500">Open tenders</div></div>
        <div className={card}><div className="text-2xl font-semibold">{tenders.length}</div><div className="text-sm text-slate-500">Total tracked</div></div>
        <div className={card}><div className="text-2xl font-semibold">{tenders.filter((t) => t.status === "closed").length}</div><div className="text-sm text-slate-500">Closed</div></div>
        <div className={card}><div className="text-2xl font-semibold">{tenders.filter((t) => t.status === "results_collected").length}</div><div className="text-sm text-slate-500">Results in</div></div>
      </div>

      <h2 className="mt-6 mb-2 text-sm font-semibold text-slate-600">Open by state</h2>
      <div className="flex flex-wrap gap-2">
        {byState.map((b) => <span key={b.s} className="rounded bg-white border border-slate-200 px-3 py-1 text-sm">{b.s}: {b.n}</span>)}
      </div>

      <h2 className="mt-6 mb-2 text-sm font-semibold text-slate-600">Source health</h2>
      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-left text-slate-600"><tr><th className="p-2">Source</th><th className="p-2">Last success</th><th className="p-2">Fails</th></tr></thead>
          <tbody>
            {health.map((h) => (
              <tr key={h.source} className="border-t border-slate-100">
                <td className="p-2">{h.source}</td>
                <td className="p-2 text-slate-500">{h.last_success ? new Date(h.last_success).toLocaleString() : "—"}</td>
                <td className={`p-2 ${h.consecutive_failures >= 3 ? "text-red-600 font-medium" : "text-slate-500"}`}>{h.consecutive_failures}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `src/app/results/page.tsx`** (competitors + spreads)

```tsx
import { getBidResults } from "@/lib/data";
import { competitorStats, projectSpreads } from "@/lib/logic";

export const dynamic = "force-dynamic";

export default async function Results() {
  let rows; try { rows = await getBidResults(); } catch (e) {
    return <p className="text-red-600">Could not load results: {(e as Error).message}</p>;
  }
  const comps = competitorStats(rows).slice(0, 25);
  const spreads = projectSpreads(rows).slice(0, 25);
  const card = "overflow-x-auto rounded border border-slate-200 bg-white";
  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Results &amp; Competitors</h1>
      <p className="mb-4 text-sm text-slate-500">{rows.length} bid records collected. Dollar amounts are sparse today (see collector notes).</p>

      <h2 className="mb-2 text-sm font-semibold text-slate-600">Top competitors</h2>
      <div className={card}>
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-left text-slate-600"><tr><th className="p-2">Bidder</th><th className="p-2">Bids</th><th className="p-2">Wins</th><th className="p-2">Win rate</th></tr></thead>
          <tbody>
            {comps.map((c) => <tr key={c.bidder} className="border-t border-slate-100"><td className="p-2">{c.bidder}</td><td className="p-2">{c.bids}</td><td className="p-2">{c.wins}</td><td className="p-2">{Math.round(c.winRate * 100)}%</td></tr>)}
            {comps.length === 0 && <tr><td colSpan={4} className="p-6 text-center text-slate-400">No results yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <h2 className="mt-6 mb-2 text-sm font-semibold text-slate-600">Bid spreads (priced projects)</h2>
      <div className={card}>
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-left text-slate-600"><tr><th className="p-2">Project</th><th className="p-2">Low</th><th className="p-2">High</th><th className="p-2">Spread</th><th className="p-2">Bidders</th></tr></thead>
          <tbody>
            {spreads.map((s) => <tr key={`${s.source}:${s.external_id}`} className="border-t border-slate-100"><td className="p-2">{s.project_title}</td><td className="p-2">${s.low.toLocaleString()}</td><td className="p-2">${s.high.toLocaleString()}</td><td className="p-2">+{Math.round(s.spreadPct)}%</td><td className="p-2">{s.nBidders}</td></tr>)}
            {spreads.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-slate-400">No priced spreads yet ($ data sparse).</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Build** `npm run build` → succeeds. **Commit** `git add -A; git commit -m "feat(ui): overview + results pages"`.

---

### Task 8: Deploy prep — README + build gate

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Tender-Radar Dashboard

Single-user read-only dashboard over the Tender-Radar Supabase data (Next.js + Supabase + Vercel).

## Env (Vercel project settings)
- `NEXT_PUBLIC_SUPABASE_URL` = https://cofplvbfzuppwykxhqbr.supabase.co
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` = (Supabase → Settings → API → anon public)
- `SUPABASE_SERVICE_ROLE_KEY` = (Supabase → Settings → API → service_role — server-only)
- `OWNER_EMAIL` = andriy.leso@gmail.com
- `NEXT_PUBLIC_SITE_URL` = the deployed URL (for magic-link redirect)

## Supabase setup
- Add `${NEXT_PUBLIC_SITE_URL}/auth/confirm` to Supabase → Auth → URL Configuration → Redirect URLs.
- If the API can't see the collector's tables: Supabase → Settings → API → Reload schema (or `NOTIFY pgrst, 'reload schema';`).

## Local: `npm install`, copy `.env.example` → `.env.local`, `npm run build`. (Do NOT rely on `next dev` in automation.)
```

- [ ] **Step 2: Final full build + tests** `npm test` (green) and `npm run build` (succeeds).

- [ ] **Step 3: Commit** `git add -A; git commit -m "docs: dashboard README + deploy env"`.

---

## Post-plan (controller handles, needs user input)
- Create the private GitHub repo + push (`gh repo create`), like the collector's Phase B.
- User provides the Supabase anon + service_role keys (from Supabase dashboard); controller sets Vercel env vars, adds the redirect URL, deploys, and verifies the live authenticated dashboard shows real tenders (build-based verification + one authenticated load — never a logged-out 307).

## Out of scope (this plan)
- Writes/notes, multi-user, commercial data views, $/SF charts, realtime (per spec).

## Self-review notes
- Spec coverage: single-user magic-link auth (T4), server-side service-role reads (T3), Overview (T7), Tenders filters+detail (T6), Results/competitors (T7), Smart Film shell (T5), build-not-devserver verification (T6-T8). All spec sections mapped.
- Testable logic (filters, status, competitor/spread aggregation) is TDD-unit-tested (T2); IO wrappers + UI verified via `npx tsc --noEmit` + `npm run build`.
- Types consistent: `Tender`/`BidResult`/`SourceHealth`/`TenderFilters` defined once (T2), consumed by data (T3), logic (T2), and pages (T6/T7). `isOpen`/`filterTenders`/`competitorStats`/`projectSpreads` signatures stable across tasks.
- No placeholders; every step has runnable code/commands.
