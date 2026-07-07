# OWC Sales Machine — Spine Implementation Plan (MVP Part 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deal-pipeline "spine" — a usable Next.js + Supabase app where every deal lives as a record, is shown on a 5-phase / 15-station board, moves between stages, and honors the uniform control-point (Approve/Reject) mechanism. All stations manual at this stage.

**Architecture:** Thin Next.js App Router orchestrator over Supabase (Postgres/Auth/Storage/RLS). Pure domain logic (stages, transitions, control points) lives in `src/lib/deals/` and is fully unit-tested with Vitest; a thin repo layer applies those pure results to the database; server components render the board and deal pages; server actions perform stage moves.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, Supabase (`@supabase/ssr`, `@supabase/supabase-js`), Vitest, Tailwind + shadcn/ui, lucide-react, sonner. Mirrors the existing `projects/smartfilm` project.

**Spec:** `docs/superpowers/specs/2026-07-07-owc-sales-machine-design.md`

---

## File Structure

```
projects/owc-sales/
  package.json, tsconfig.json, next.config.mjs, tailwind.config.ts,
  postcss.config.mjs, vitest.config.ts, .env.local.example
  supabase/migrations/0001_spine.sql
  src/
    lib/
      deals/
        stages.ts        # 15 stages, 5 phases, lookups (pure)
        stages.test.ts
        transitions.ts   # advance / reject / flag-review (pure)
        transitions.test.ts
        board.ts         # group deals by phase for the board (pure)
        board.test.ts
        types.ts         # shared Deal / StageEvent / DB row types
        repo.ts          # Supabase reads/writes (applies pure results)
      supabase/
        server.ts        # server-side Supabase client (@supabase/ssr)
        client.ts        # browser Supabase client
    app/
      (app)/
        pipeline/page.tsx          # the board
        deals/[id]/page.tsx        # deal detail + control points
        deals/[id]/actions.ts      # server actions: advance / reject
      layout.tsx, globals.css
    components/
      board/PhaseColumn.tsx
      board/DealCard.tsx
      deals/ControlPoint.tsx
      deals/StageTimeline.tsx
```

---

## Task 1: Scaffold the project

**Files:**
- Create: `projects/owc-sales/package.json`
- Create: `projects/owc-sales/tsconfig.json`
- Create: `projects/owc-sales/next.config.mjs`
- Create: `projects/owc-sales/vitest.config.ts`
- Create: `projects/owc-sales/.env.local.example`
- Create: `projects/owc-sales/src/app/layout.tsx`
- Create: `projects/owc-sales/src/app/globals.css`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "owc-sales",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run"
  },
  "dependencies": {
    "@supabase/ssr": "^0.12.0",
    "@supabase/supabase-js": "^2.108.2",
    "clsx": "^2.1.1",
    "lucide-react": "^1.21.0",
    "next": "^15",
    "react": "^19.2.7",
    "react-dom": "^19.2.7",
    "sonner": "^2.0.7",
    "tailwind-merge": "^3.6.0",
    "zod": "^4.4.3"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "autoprefixer": "^10.4.20",
    "eslint": "^8",
    "eslint-config-next": "^15",
    "postcss": "^8",
    "tailwindcss": "^3.4.1",
    "typescript": "^5",
    "vitest": "^4.1.9"
  }
}
```

- [ ] **Step 2: Create `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `next.config.mjs`, `vitest.config.ts`, `.env.local.example`**

`next.config.mjs`:
```js
/** @type {import('next').NextConfig} */
const nextConfig = {};
export default nextConfig;
```

`vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts"] },
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
});
```

`.env.local.example`:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

- [ ] **Step 4: Create minimal `src/app/layout.tsx` and `src/app/globals.css`**

`src/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`src/app/layout.tsx`:
```tsx
import "./globals.css";
import { Toaster } from "sonner";

export const metadata = { title: "OWC Sales Machine" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uk">
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
```

Also create `tailwind.config.ts` and `postcss.config.mjs`:

`tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

`postcss.config.mjs`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 5: Install and verify build tooling**

Run: `cd projects/owc-sales && npm install && npx vitest run`
Expected: install succeeds; Vitest runs and reports "No test files found" (exit 0 with `--passWithNoTests` is not set, so instead create the first test in Task 2 before running). For now just confirm `npm install` completes.

- [ ] **Step 6: Commit**

```bash
cd projects/owc-sales && git init && git add -A
git commit -m "chore(owc-sales): scaffold Next.js + Supabase + Vitest project"
```

---

## Task 2: Stages & phases domain

**Files:**
- Create: `src/lib/deals/stages.ts`
- Test: `src/lib/deals/stages.test.ts`

- [ ] **Step 1: Write the failing test**

`src/lib/deals/stages.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import {
  STAGES, PHASES, getStage, phaseForStage, nextStageId, prevStageId, isLastStage,
} from "./stages";

describe("stages", () => {
  it("has 15 stages numbered 1..15 in order", () => {
    expect(STAGES).toHaveLength(15);
    expect(STAGES.map((s) => s.id)).toEqual(Array.from({ length: 15 }, (_, i) => i + 1));
  });

  it("groups stages into the 5 funnel phases", () => {
    expect(PHASES.map((p) => p.key)).toEqual(["lead", "quote", "proposal", "close", "fulfil"]);
    expect(phaseForStage(1)).toBe("lead");
    expect(phaseForStage(5)).toBe("quote");
    expect(phaseForStage(8)).toBe("proposal");
    expect(phaseForStage(11)).toBe("close");
    expect(phaseForStage(15)).toBe("fulfil");
  });

  it("looks up a stage by id", () => {
    expect(getStage(3).key).toBe("takeoff");
    expect(getStage(6).key).toBe("proposal");
  });

  it("computes next / prev stage ids", () => {
    expect(nextStageId(1)).toBe(2);
    expect(nextStageId(15)).toBeNull();
    expect(prevStageId(2)).toBe(1);
    expect(prevStageId(1)).toBeNull();
  });

  it("knows the last stage", () => {
    expect(isLastStage(15)).toBe(true);
    expect(isLastStage(14)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/deals/stages.test.ts`
Expected: FAIL — cannot find module `./stages`.

- [ ] **Step 3: Write minimal implementation**

`src/lib/deals/stages.ts`:
```ts
export type PhaseKey = "lead" | "quote" | "proposal" | "close" | "fulfil";

export interface StageDef {
  id: number;
  key: string;
  label: string; // Ukrainian
  phase: PhaseKey;
}

export interface PhaseDef {
  key: PhaseKey;
  label: string;
}

export const PHASES: PhaseDef[] = [
  { key: "lead", label: "Lead" },
  { key: "quote", label: "Quote" },
  { key: "proposal", label: "Proposal" },
  { key: "close", label: "Close" },
  { key: "fulfil", label: "Fulfil" },
];

export const STAGES: StageDef[] = [
  { id: 1, key: "request", label: "Запит", phase: "lead" },
  { id: 2, key: "quote_requested", label: "Запит на прорахунок отримано", phase: "lead" },
  { id: 3, key: "takeoff", label: "Take-off", phase: "quote" },
  { id: 4, key: "supplier_rfq", label: "RFQ постачальникам", phase: "quote" },
  { id: 5, key: "supplier_quote", label: "Прорахунок отримано", phase: "quote" },
  { id: 6, key: "proposal", label: "Пропозиція мовою клієнта", phase: "proposal" },
  { id: 7, key: "proposal_sent", label: "Відправка пропозиції", phase: "proposal" },
  { id: 8, key: "agreed", label: "Погодження замовлення", phase: "proposal" },
  { id: 9, key: "final_calc", label: "Кінцевий прорахунок", phase: "close" },
  { id: 10, key: "contract", label: "Договір", phase: "close" },
  { id: 11, key: "payment", label: "Оплата", phase: "close" },
  { id: 12, key: "production", label: "Виробництво", phase: "fulfil" },
  { id: 13, key: "shipping", label: "Відправка", phase: "fulfil" },
  { id: 14, key: "customs", label: "Розтаможка", phase: "fulfil" },
  { id: 15, key: "handover", label: "Передача клієнту", phase: "fulfil" },
];

export function getStage(id: number): StageDef {
  const s = STAGES.find((x) => x.id === id);
  if (!s) throw new Error(`Unknown stage id: ${id}`);
  return s;
}

export function phaseForStage(id: number): PhaseKey {
  return getStage(id).phase;
}

export function nextStageId(id: number): number | null {
  return id >= 1 && id < STAGES.length ? id + 1 : null;
}

export function prevStageId(id: number): number | null {
  return id > 1 && id <= STAGES.length ? id - 1 : null;
}

export function isLastStage(id: number): boolean {
  return id === STAGES.length;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/deals/stages.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/deals/stages.ts src/lib/deals/stages.test.ts
git commit -m "feat(deals): 15-stage / 5-phase model with lookups"
```

---

## Task 3: Deal transitions & control points

**Files:**
- Create: `src/lib/deals/types.ts`
- Create: `src/lib/deals/transitions.ts`
- Test: `src/lib/deals/transitions.test.ts`

- [ ] **Step 1: Write the shared types**

`src/lib/deals/types.ts`:
```ts
export type DealStatus = "active" | "won" | "lost";
export type Actor = "human" | "auto";
export type Source = "site" | "ads" | "email" | "messenger" | "other";

export interface Deal {
  id: string;
  client_name: string;
  client_language: string;
  client_contact: string | null;
  source: Source;
  stage: number;
  status: DealStatus;
  amount: number | null;
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface StageEvent {
  id: string;
  deal_id: string;
  from_stage: number | null;
  to_stage: number;
  actor: Actor;
  note: string | null;
  at: string;
}

// Result of a pure transition: the mutated deal fields + the event to log.
export interface NewStageEvent {
  from_stage: number | null;
  to_stage: number;
  actor: Actor;
  note: string | null;
}

export interface TransitionResult {
  deal: Pick<Deal, "stage" | "status" | "needs_review">;
  event: NewStageEvent;
}
```

- [ ] **Step 2: Write the failing test**

`src/lib/deals/transitions.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { advanceDeal, rejectDeal, flagForReview, markLost } from "./transitions";
import type { Deal } from "./types";

function make(overrides: Partial<Deal> = {}): Deal {
  return {
    id: "d1", client_name: "Acme", client_language: "uk", client_contact: null,
    source: "site", stage: 3, status: "active", amount: null,
    needs_review: false, created_at: "t", updated_at: "t", ...overrides,
  };
}

describe("advanceDeal", () => {
  it("moves to the next stage and clears needs_review", () => {
    const r = advanceDeal(make({ stage: 3, needs_review: true }), "human");
    expect(r.deal.stage).toBe(4);
    expect(r.deal.needs_review).toBe(false);
    expect(r.event).toEqual({ from_stage: 3, to_stage: 4, actor: "human", note: null });
  });

  it("marks the deal won when advancing past the last stage", () => {
    const r = advanceDeal(make({ stage: 15 }), "human", "delivered");
    expect(r.deal.stage).toBe(15);
    expect(r.deal.status).toBe("won");
    expect(r.event.note).toBe("delivered");
  });
});

describe("rejectDeal", () => {
  it("moves back one stage and clears needs_review", () => {
    const r = rejectDeal(make({ stage: 6, needs_review: true }), "wrong price");
    expect(r.deal.stage).toBe(5);
    expect(r.deal.needs_review).toBe(false);
    expect(r.event).toEqual({ from_stage: 6, to_stage: 5, actor: "human", note: "wrong price" });
  });

  it("throws when rejecting from the first stage", () => {
    expect(() => rejectDeal(make({ stage: 1 }))).toThrow();
  });
});

describe("flagForReview", () => {
  it("keeps the stage but sets needs_review and logs an auto event", () => {
    const r = flagForReview(make({ stage: 6 }), "draft proposal ready");
    expect(r.deal.stage).toBe(6);
    expect(r.deal.needs_review).toBe(true);
    expect(r.event).toEqual({ from_stage: 6, to_stage: 6, actor: "auto", note: "draft proposal ready" });
  });
});

describe("markLost", () => {
  it("sets status lost and clears needs_review", () => {
    const r = markLost(make({ stage: 7, needs_review: true }), "client silent");
    expect(r.deal.status).toBe("lost");
    expect(r.deal.needs_review).toBe(false);
    expect(r.event.note).toBe("client silent");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run src/lib/deals/transitions.test.ts`
Expected: FAIL — cannot find module `./transitions`.

- [ ] **Step 4: Write minimal implementation**

`src/lib/deals/transitions.ts`:
```ts
import { nextStageId, prevStageId, isLastStage } from "./stages";
import type { Actor, Deal, TransitionResult } from "./types";

export function advanceDeal(deal: Deal, actor: Actor, note?: string): TransitionResult {
  const note_ = note ?? null;
  if (isLastStage(deal.stage)) {
    return {
      deal: { stage: deal.stage, status: "won", needs_review: false },
      event: { from_stage: deal.stage, to_stage: deal.stage, actor, note: note_ },
    };
  }
  const to = nextStageId(deal.stage);
  if (to === null) throw new Error(`Cannot advance from stage ${deal.stage}`);
  return {
    deal: { stage: to, status: deal.status, needs_review: false },
    event: { from_stage: deal.stage, to_stage: to, actor, note: note_ },
  };
}

export function rejectDeal(deal: Deal, note?: string): TransitionResult {
  const to = prevStageId(deal.stage);
  if (to === null) throw new Error(`Cannot reject from stage ${deal.stage}`);
  return {
    deal: { stage: to, status: deal.status, needs_review: false },
    event: { from_stage: deal.stage, to_stage: to, actor: "human", note: note ?? null },
  };
}

export function flagForReview(deal: Deal, note: string): TransitionResult {
  return {
    deal: { stage: deal.stage, status: deal.status, needs_review: true },
    event: { from_stage: deal.stage, to_stage: deal.stage, actor: "auto", note },
  };
}

export function markLost(deal: Deal, note?: string): TransitionResult {
  return {
    deal: { stage: deal.stage, status: "lost", needs_review: false },
    event: { from_stage: deal.stage, to_stage: deal.stage, actor: "human", note: note ?? null },
  };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/lib/deals/transitions.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add src/lib/deals/types.ts src/lib/deals/transitions.ts src/lib/deals/transitions.test.ts
git commit -m "feat(deals): pure stage transitions + control-point flag"
```

---

## Task 4: Board grouping helper

**Files:**
- Create: `src/lib/deals/board.ts`
- Test: `src/lib/deals/board.test.ts`

- [ ] **Step 1: Write the failing test**

`src/lib/deals/board.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { groupDealsByPhase } from "./board";
import type { Deal } from "./types";

function make(id: string, stage: number): Deal {
  return {
    id, client_name: id, client_language: "uk", client_contact: null,
    source: "site", stage, status: "active", amount: null,
    needs_review: false, created_at: "t", updated_at: "t",
  };
}

describe("groupDealsByPhase", () => {
  it("buckets active deals under their phase, preserving phase order", () => {
    const grouped = groupDealsByPhase([make("a", 1), make("b", 4), make("c", 15)]);
    expect(grouped.map((g) => g.phase.key)).toEqual(["lead", "quote", "proposal", "close", "fulfil"]);
    expect(grouped[0].deals.map((d) => d.id)).toEqual(["a"]);
    expect(grouped[1].deals.map((d) => d.id)).toEqual(["b"]);
    expect(grouped[4].deals.map((d) => d.id)).toEqual(["c"]);
  });

  it("excludes won and lost deals", () => {
    const won = { ...make("w", 15), status: "won" as const };
    const grouped = groupDealsByPhase([make("a", 1), won]);
    expect(grouped.flatMap((g) => g.deals).map((d) => d.id)).toEqual(["a"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/deals/board.test.ts`
Expected: FAIL — cannot find module `./board`.

- [ ] **Step 3: Write minimal implementation**

`src/lib/deals/board.ts`:
```ts
import { PHASES, phaseForStage, type PhaseDef } from "./stages";
import type { Deal } from "./types";

export interface PhaseBucket {
  phase: PhaseDef;
  deals: Deal[];
}

export function groupDealsByPhase(deals: Deal[]): PhaseBucket[] {
  const active = deals.filter((d) => d.status === "active");
  return PHASES.map((phase) => ({
    phase,
    deals: active.filter((d) => phaseForStage(d.stage) === phase.key),
  }));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/deals/board.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/deals/board.ts src/lib/deals/board.test.ts
git commit -m "feat(deals): group active deals by funnel phase for the board"
```

---

## Task 5: Database migration (deals, stage_events, documents + RLS)

**Files:**
- Create: `supabase/migrations/0001_spine.sql`

- [ ] **Step 1: Write the migration**

`supabase/migrations/0001_spine.sql`:
```sql
create extension if not exists "pgcrypto";

create table public.deals (
  id uuid primary key default gen_random_uuid(),
  client_name text not null,
  client_language text not null default 'uk',
  client_contact text,
  source text not null default 'other'
    check (source in ('site','ads','email','messenger','other')),
  stage int not null default 1 check (stage between 1 and 15),
  status text not null default 'active'
    check (status in ('active','won','lost')),
  amount numeric,
  needs_review boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.stage_events (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references public.deals(id) on delete cascade,
  from_stage int,
  to_stage int not null,
  actor text not null check (actor in ('human','auto')),
  note text,
  at timestamptz not null default now()
);
create index stage_events_deal_id_idx on public.stage_events(deal_id);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references public.deals(id) on delete cascade,
  type text not null
    check (type in ('request','takeoff','quote','proposal','contract')),
  url text not null,
  version int not null default 1,
  created_at timestamptz not null default now()
);
create index documents_deal_id_idx on public.documents(deal_id);

-- RLS: solo operator — any authenticated user has full access.
alter table public.deals enable row level security;
alter table public.stage_events enable row level security;
alter table public.documents enable row level security;

create policy "authenticated full access - deals"
  on public.deals for all to authenticated using (true) with check (true);
create policy "authenticated full access - stage_events"
  on public.stage_events for all to authenticated using (true) with check (true);
create policy "authenticated full access - documents"
  on public.documents for all to authenticated using (true) with check (true);
```

- [ ] **Step 2: Apply the migration**

Run (against the project's Supabase — set `SUPABASE_DB_URL` to the connection string, or paste into the Supabase SQL editor):
`psql "$SUPABASE_DB_URL" -f supabase/migrations/0001_spine.sql`
Expected: `CREATE TABLE` / `CREATE POLICY` messages, no errors.

- [ ] **Step 3: Verify tables exist**

Run: `psql "$SUPABASE_DB_URL" -c "\dt public.*"`
Expected: `deals`, `stage_events`, `documents` listed.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0001_spine.sql
git commit -m "feat(db): spine schema (deals, stage_events, documents) + RLS"
```

---

## Task 6: Supabase clients + deal repo

**Files:**
- Create: `src/lib/supabase/server.ts`
- Create: `src/lib/supabase/client.ts`
- Create: `src/lib/deals/repo.ts`

- [ ] **Step 1: Create the Supabase server client**

`src/lib/supabase/server.ts`:
```ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function getServerSupabase() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (all) => {
          try {
            all.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // called from a Server Component — ignore; middleware refreshes.
          }
        },
      },
    },
  );
}
```

- [ ] **Step 2: Create the browser client**

`src/lib/supabase/client.ts`:
```ts
import { createBrowserClient } from "@supabase/ssr";

export function getBrowserSupabase() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
```

- [ ] **Step 3: Create the deal repo**

`src/lib/deals/repo.ts`:
```ts
import { getServerSupabase } from "@/lib/supabase/server";
import { advanceDeal, rejectDeal } from "./transitions";
import type { Deal, StageEvent } from "./types";

export async function listActiveDeals(): Promise<Deal[]> {
  const supabase = await getServerSupabase();
  const { data, error } = await supabase
    .from("deals")
    .select("*")
    .eq("status", "active")
    .order("updated_at", { ascending: false });
  if (error) throw error;
  return data as Deal[];
}

export async function getDeal(id: string): Promise<Deal | null> {
  const supabase = await getServerSupabase();
  const { data, error } = await supabase.from("deals").select("*").eq("id", id).maybeSingle();
  if (error) throw error;
  return (data as Deal) ?? null;
}

export async function listEvents(dealId: string): Promise<StageEvent[]> {
  const supabase = await getServerSupabase();
  const { data, error } = await supabase
    .from("stage_events")
    .select("*")
    .eq("deal_id", dealId)
    .order("at", { ascending: true });
  if (error) throw error;
  return data as StageEvent[];
}

// Applies a pure transition result to the DB: updates the deal and logs the event.
async function applyTransition(deal: Deal, result: ReturnType<typeof advanceDeal>) {
  const supabase = await getServerSupabase();
  const { error: upErr } = await supabase
    .from("deals")
    .update({ ...result.deal, updated_at: new Date().toISOString() })
    .eq("id", deal.id);
  if (upErr) throw upErr;
  const { error: evErr } = await supabase
    .from("stage_events")
    .insert({ deal_id: deal.id, ...result.event });
  if (evErr) throw evErr;
}

export async function advanceDealById(id: string, note?: string): Promise<void> {
  const deal = await getDeal(id);
  if (!deal) throw new Error("Deal not found");
  await applyTransition(deal, advanceDeal(deal, "human", note));
}

export async function rejectDealById(id: string, note?: string): Promise<void> {
  const deal = await getDeal(id);
  if (!deal) throw new Error("Deal not found");
  await applyTransition(deal, rejectDeal(deal, note));
}
```

- [ ] **Step 4: Type-check**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add src/lib/supabase src/lib/deals/repo.ts
git commit -m "feat(deals): supabase clients + deal repo (list/get/advance/reject)"
```

---

## Task 7: Pipeline board page

**Files:**
- Create: `src/components/board/DealCard.tsx`
- Create: `src/components/board/PhaseColumn.tsx`
- Create: `src/app/(app)/pipeline/page.tsx`

- [ ] **Step 1: Create `DealCard`**

`src/components/board/DealCard.tsx`:
```tsx
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { getStage } from "@/lib/deals/stages";
import type { Deal } from "@/lib/deals/types";

export function DealCard({ deal }: { deal: Deal }) {
  return (
    <Link
      href={`/deals/${deal.id}`}
      className="block rounded-md border bg-white p-3 text-sm shadow-sm hover:border-slate-400"
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-slate-800">{deal.client_name}</span>
        {deal.needs_review && <AlertTriangle className="h-4 w-4 text-amber-500" />}
      </div>
      <div className="mt-1 text-xs text-slate-500">{getStage(deal.stage).label}</div>
    </Link>
  );
}
```

- [ ] **Step 2: Create `PhaseColumn`**

`src/components/board/PhaseColumn.tsx`:
```tsx
import { DealCard } from "./DealCard";
import type { PhaseBucket } from "@/lib/deals/board";

export function PhaseColumn({ bucket }: { bucket: PhaseBucket }) {
  return (
    <div className="flex min-w-[220px] flex-1 flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold text-slate-700">{bucket.phase.label}</h2>
        <span className="text-xs text-slate-400">{bucket.deals.length}</span>
      </div>
      <div className="flex flex-col gap-2 rounded-lg bg-slate-50 p-2">
        {bucket.deals.map((d) => <DealCard key={d.id} deal={d} />)}
        {bucket.deals.length === 0 && (
          <p className="px-1 py-4 text-center text-xs text-slate-400">—</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create the board page**

`src/app/(app)/pipeline/page.tsx`:
```tsx
import { listActiveDeals } from "@/lib/deals/repo";
import { groupDealsByPhase } from "@/lib/deals/board";
import { PhaseColumn } from "@/components/board/PhaseColumn";

export const dynamic = "force-dynamic";

export default async function PipelinePage() {
  const deals = await listActiveDeals();
  const buckets = groupDealsByPhase(deals);
  return (
    <main className="p-6">
      <h1 className="mb-4 text-xl font-semibold text-slate-900">Воронка продажів</h1>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {buckets.map((b) => <PhaseColumn key={b.phase.key} bucket={b} />)}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Verify it renders**

Run: `npm run dev`, open `http://localhost:3000/pipeline`.
Expected: 5 phase columns render. With no deals, each shows "—". (Insert a test row via SQL editor to see a card:
`insert into deals (client_name, source, stage) values ('Тест', 'site', 4);`)

- [ ] **Step 5: Commit**

```bash
git add src/components/board src/app/(app)/pipeline
git commit -m "feat(pipeline): 5-phase board with deal cards"
```

---

## Task 8: Deal detail page + control points

**Files:**
- Create: `src/components/deals/StageTimeline.tsx`
- Create: `src/components/deals/ControlPoint.tsx`
- Create: `src/app/(app)/deals/[id]/actions.ts`
- Create: `src/app/(app)/deals/[id]/page.tsx`

- [ ] **Step 1: Create the server actions**

`src/app/(app)/deals/[id]/actions.ts`:
```ts
"use server";
import { revalidatePath } from "next/cache";
import { advanceDealById, rejectDealById } from "@/lib/deals/repo";

export async function approveAction(id: string, note?: string) {
  await advanceDealById(id, note);
  revalidatePath(`/deals/${id}`);
  revalidatePath("/pipeline");
}

export async function rejectAction(id: string, note?: string) {
  await rejectDealById(id, note);
  revalidatePath(`/deals/${id}`);
  revalidatePath("/pipeline");
}
```

- [ ] **Step 2: Create `ControlPoint` (client component)**

`src/components/deals/ControlPoint.tsx`:
```tsx
"use client";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { approveAction, rejectAction } from "@/app/(app)/deals/[id]/actions";

export function ControlPoint({ dealId, needsReview }: { dealId: string; needsReview: boolean }) {
  const [note, setNote] = useState("");
  const [pending, start] = useTransition();

  function run(fn: (id: string, note?: string) => Promise<void>, ok: string) {
    start(async () => {
      try {
        await fn(dealId, note || undefined);
        toast.success(ok);
        setNote("");
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Помилка");
      }
    });
  }

  return (
    <div className="rounded-lg border p-4">
      {needsReview && (
        <p className="mb-2 text-sm font-medium text-amber-600">⚠ Потребує перегляду</p>
      )}
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Коментар (необовʼязково)"
        className="mb-2 w-full rounded border p-2 text-sm"
        rows={2}
      />
      <div className="flex gap-2">
        <button
          disabled={pending}
          onClick={() => run(approveAction, "Просунуто далі")}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Підтвердити →
        </button>
        <button
          disabled={pending}
          onClick={() => run(rejectAction, "Повернуто назад")}
          className="rounded border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          ← Відхилити
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `StageTimeline`**

`src/components/deals/StageTimeline.tsx`:
```tsx
import { getStage } from "@/lib/deals/stages";
import type { StageEvent } from "@/lib/deals/types";

export function StageTimeline({ events }: { events: StageEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-slate-400">Подій ще немає.</p>;
  return (
    <ol className="space-y-2">
      {events.map((e) => (
        <li key={e.id} className="text-sm text-slate-600">
          <span className="text-slate-400">{new Date(e.at).toLocaleString("uk-UA")}</span>{" "}
          <span className="font-medium">
            {e.from_stage && e.from_stage !== e.to_stage
              ? `${getStage(e.from_stage).label} → ${getStage(e.to_stage).label}`
              : getStage(e.to_stage).label}
          </span>{" "}
          <span className="text-xs text-slate-400">({e.actor})</span>
          {e.note && <span className="text-slate-500"> — {e.note}</span>}
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 4: Create the deal detail page**

`src/app/(app)/deals/[id]/page.tsx`:
```tsx
import { notFound } from "next/navigation";
import { getDeal, listEvents } from "@/lib/deals/repo";
import { getStage } from "@/lib/deals/stages";
import { ControlPoint } from "@/components/deals/ControlPoint";
import { StageTimeline } from "@/components/deals/StageTimeline";

export const dynamic = "force-dynamic";

export default async function DealPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const deal = await getDeal(id);
  if (!deal) notFound();
  const events = await listEvents(id);

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">{deal.client_name}</h1>
        <p className="text-sm text-slate-500">
          {getStage(deal.stage).label} · {deal.source} · {deal.client_language}
        </p>
      </header>

      <ControlPoint dealId={deal.id} needsReview={deal.needs_review} />

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Історія</h2>
        <StageTimeline events={events} />
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Verify the control loop end-to-end**

Run: `npm run dev`, open a deal at `/deals/<id>` (use the id of the row inserted in Task 7).
- Click **Підтвердити →**: stage advances, a timeline entry appears, `/pipeline` shows the card in the next phase when it crosses a boundary.
- Click **← Відхилити**: stage moves back one; from stage 1 the toast shows the error message ("Cannot reject from stage 1").
Expected: both actions work; timeline logs each move with actor `human`.

- [ ] **Step 6: Commit**

```bash
git add src/components/deals "src/app/(app)/deals"
git commit -m "feat(deals): detail page with control-point approve/reject + timeline"
```

---

## Self-Review Notes (completed)

- **Spec coverage:** deal spine (Task 5,6), 15 stations / 5 phases (Task 2), control-point Approve/Reject mechanism (Task 3,8), board (Task 7), deal page + activity log (Task 8), documents table created (Task 5; UI to attach files arrives with the automation plans that produce documents). Lead-intake automation is intentionally out — it is Plan 2. `line_items`/`suppliers` correctly deferred per spec.
- **Placeholder scan:** none — every code step contains complete code.
- **Type consistency:** `Deal`, `StageEvent`, `NewStageEvent`, `TransitionResult` defined in Task 3 `types.ts`; `advanceDeal`/`rejectDeal`/`flagForReview`/`markLost` names match across `transitions.ts`, tests, and `repo.ts`. `groupDealsByPhase`/`PhaseBucket` consistent between Task 4 and Task 7. Repo functions `advanceDealById`/`rejectDealById` match the server actions in Task 8.

---

## Next plan

**Plan 2 — Lead intake automation** (the first `auto` station): website form → `POST /api/intake` creating a deal + fast auto-acknowledgement; "New lead" paste → `@anthropic-ai/sdk` structuring into a draft (`assisted`); contact dedupe. Written as its own spec-aligned plan once the spine is running.
