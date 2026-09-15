# Smart Film Platform — MVP Slice 1: Foundation & Auth/RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a deployable Next.js + Supabase app with the full MVP database schema, seeded reference/test data, email-password auth, and DB-enforced (RLS) dealer/region order scoping — verified by tests.

**Architecture:** Next.js 14 (App Router, TS) modular monolith talking to Supabase (Postgres + Auth + Storage). Access control is **Postgres Row-Level Security**: a dealer sees only their own orders; staff/admin see all. Auth sessions via `@supabase/ssr` cookies + Next.js middleware. Schema and policies are versioned SQL migrations; everything runs locally via the Supabase CLI (Docker).

**Tech Stack:** Next.js 14, TypeScript, Tailwind + shadcn/ui, Supabase (supabase-js, @supabase/ssr), Vitest (unit/integration), Playwright (E2E), GitHub Actions (CI).

**Scope of THIS plan:** schema for the whole MVP (one-time, avoids churn) + RLS for the tables exercised now (profiles, dealers, user_roles, po_clients, orders, status_history, reference tables). RLS for order-child tables (panels, addons, attachments, qr_codes, shipments) lands with the slices that build those features. No order-entry UI yet — orders exist via seed, which is enough to prove the access model.

---

## Prerequisites (verify before Task 1)

- [ ] **Node 20+**: `node -v` → v20.x or later
- [ ] **Docker Desktop running**: `docker info` → no error (Supabase local needs it)
- [ ] **Supabase CLI**: `npx supabase --version` → prints a version (we pin via npx, no global install needed)
- [ ] **Git**: `git --version`
- [ ] You are on branch `docs/smartfilm-platform-plan` (or create a code branch — see Task 1).

---

## Task 1: Project scaffold (Next.js + TS + Tailwind + shadcn)

**Files:**
- Create: `package.json`, `next.config.mjs`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.mjs`, `app/globals.css`, `app/layout.tsx`, `app/page.tsx`, `.gitignore`, `components.json`

- [ ] **Step 1: Create the project in a new folder under `projects/`**

Run from `C:\SuperWork`:
```bash
npx create-next-app@14 projects/smartfilm --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack
```
Answer prompts with the flags above (non-interactive where possible). Expected: `projects/smartfilm/` created with `src/app/`.

- [ ] **Step 2: Initialize shadcn/ui**

Run from `C:\SuperWork\projects\smartfilm`:
```bash
npx shadcn@latest init -d
npx shadcn@latest add button input label card table badge sonner
```
Expected: `components.json` created; `src/components/ui/*` populated.

- [ ] **Step 3: Verify the dev server boots**

Run: `npm run dev` (in `projects/smartfilm`), open `http://localhost:3000`.
Expected: default Next.js page renders. Stop the server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git checkout -b feat/smartfilm-foundation
git add projects/smartfilm
git commit -m "feat(smartfilm): scaffold Next.js 14 + Tailwind + shadcn"
```

---

## Task 2: Supabase local stack + env + SSR clients

**Files:**
- Create: `projects/smartfilm/supabase/config.toml` (via init), `projects/smartfilm/.env.local`, `projects/smartfilm/.env.example`
- Create: `src/lib/supabase/server.ts`, `src/lib/supabase/client.ts`, `src/lib/supabase/middleware.ts`
- Modify: `projects/smartfilm/package.json` (add `@supabase/supabase-js`, `@supabase/ssr`)

- [ ] **Step 1: Init Supabase and start the local stack**

Run from `projects/smartfilm`:
```bash
npx supabase init
npx supabase start
```
Expected: `supabase start` prints local URLs and keys (`API URL: http://127.0.0.1:54321`, `anon key`, `service_role key`, `Studio`, `Inbucket`). Copy these for the next step.

- [ ] **Step 2: Install Supabase libraries**

Run: `npm install @supabase/supabase-js @supabase/ssr`
Expected: both appear in `package.json` dependencies.

- [ ] **Step 3: Create `.env.local` and `.env.example`**

`.env.local` (paste the values printed by `supabase start`):
```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key from supabase start>
SUPABASE_SERVICE_ROLE_KEY=<service_role key from supabase start>
```
`.env.example` (committed, no secrets):
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```
Confirm `.env.local` is in `.gitignore` (create-next-app adds `.env*` — verify).

- [ ] **Step 4: Create the SSR Supabase clients**

`src/lib/supabase/server.ts`:
```ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (toSet) => {
          try {
            toSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // called from a Server Component; middleware refreshes the session
          }
        },
      },
    },
  );
}
```

`src/lib/supabase/client.ts`:
```ts
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
```

`src/lib/supabase/middleware.ts`:
```ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (toSet) => {
          toSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          toSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );
  const { data: { user } } = await supabase.auth.getUser();
  return { response, user };
}
```

- [ ] **Step 5: Commit**

```bash
git add projects/smartfilm/supabase/config.toml projects/smartfilm/.env.example projects/smartfilm/src/lib/supabase projects/smartfilm/package.json projects/smartfilm/package-lock.json
git commit -m "feat(smartfilm): supabase local stack + SSR clients"
```

---

## Task 3: Full MVP database schema (migration 0001)

**Files:**
- Create: `projects/smartfilm/supabase/migrations/0001_init.sql`

- [ ] **Step 1: Write the schema migration**

`supabase/migrations/0001_init.sql`:
```sql
-- Roles ----------------------------------------------------------------
create type public.app_role as enum ('dealer', 'staff', 'admin');

create table public.dealers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  pricing_tier text not null default 'standard',
  created_at timestamptz not null default now()
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  email text not null,
  dealer_id uuid references public.dealers(id),
  region text,
  created_at timestamptz not null default now()
);

create table public.user_roles (
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.app_role not null,
  primary key (user_id, role)
);

create table public.po_clients (
  id uuid primary key default gen_random_uuid(),
  dealer_id uuid not null references public.dealers(id) on delete cascade,
  name text not null,
  po_number text,
  contact_name text,
  contact_phone text,
  created_at timestamptz not null default now()
);

-- Reference data -------------------------------------------------------
create table public.regions (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  active boolean not null default true
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  product_type text not null default 'pdlc_film',
  active boolean not null default true
);

create table public.busbar_types (
  id uuid primary key default gen_random_uuid(),
  code int not null unique check (code between 1 and 7),
  name text not null,
  description text,
  svg_key text not null,
  active boolean not null default true
);

create table public.addons (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  unit_price numeric(12,2) not null default 0,
  active boolean not null default true
);

create table public.price_lists (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  region_id uuid references public.regions(id),
  dealer_id uuid references public.dealers(id),
  price_per_sqft numeric(12,2) not null,
  effective_from date not null default current_date,
  created_at timestamptz not null default now()
);

-- Orders ---------------------------------------------------------------
create table public.orders (
  id uuid primary key default gen_random_uuid(),
  dealer_id uuid not null references public.dealers(id),
  po_client_id uuid references public.po_clients(id),
  product_id uuid not null references public.products(id),
  region_id uuid not null references public.regions(id),
  order_type text not null default 'new_order',
  shipping_method text,
  ship_name text,
  ship_phone text,
  ship_address jsonb,
  notes text,
  rush boolean not null default false,
  status text not null default 'draft',
  total_sqft numeric(12,2) not null default 0,
  total_amount numeric(12,2) not null default 0,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.order_panels (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  label text,
  width_mm int not null,
  height_mm int not null,
  sqft numeric(12,2) not null default 0,
  ratio numeric(6,2) not null default 0,
  busbar_type_id uuid references public.busbar_types(id),
  position int not null default 0
);

create table public.order_addons (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  addon_id uuid not null references public.addons(id),
  qty int not null default 1,
  unit_price numeric(12,2) not null default 0
);

create table public.attachments (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  panel_id uuid references public.order_panels(id) on delete cascade,
  storage_path text not null,
  file_name text not null,
  mime text,
  version int not null default 1,
  uploaded_by uuid references auth.users(id),
  uploaded_at timestamptz not null default now()
);

create table public.qr_codes (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  panel_id uuid references public.order_panels(id) on delete cascade,
  qr_id text not null,
  dpp_link text,
  created_at timestamptz not null default now()
);

create table public.shipments (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  method text,
  carrier text,
  tracking_number text,
  status text,
  created_at timestamptz not null default now()
);

create table public.status_history (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  from_status text,
  to_status text not null,
  by_user uuid references auth.users(id),
  comment text,
  created_at timestamptz not null default now()
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  order_id uuid references public.orders(id) on delete cascade,
  type text not null,
  recipient text,
  channel text not null default 'email',
  sent_at timestamptz,
  meta jsonb
);

create table public.audit_log (
  id uuid primary key default gen_random_uuid(),
  actor uuid references auth.users(id),
  action text not null,
  entity text not null,
  entity_id uuid,
  diff jsonb,
  created_at timestamptz not null default now()
);

create index on public.orders (dealer_id);
create index on public.order_panels (order_id);
create index on public.status_history (order_id);
```

- [ ] **Step 2: Apply the migration locally**

Run from `projects/smartfilm`: `npx supabase migration up`
Expected: `Applying migration 0001_init.sql...` with no errors.

- [ ] **Step 3: Verify tables exist**

Run: `npx supabase db diff` → expected: "No schema changes found" (migration matches DB).
Or open Studio (`http://127.0.0.1:54323`) → Table editor shows all tables.

- [ ] **Step 4: Generate TypeScript types**

Run: `npx supabase gen types typescript --local > src/lib/types/database.ts`
Expected: `src/lib/types/database.ts` created with a `Database` type.

- [ ] **Step 5: Commit**

```bash
git add projects/smartfilm/supabase/migrations/0001_init.sql projects/smartfilm/src/lib/types/database.ts
git commit -m "feat(smartfilm): full MVP schema + generated types"
```

---

## Task 4: RLS policies (migration 0002) + helper functions

**Files:**
- Create: `projects/smartfilm/supabase/migrations/0002_rls.sql`

- [ ] **Step 1: Write the RLS migration**

`supabase/migrations/0002_rls.sql`:
```sql
-- Helper functions (security definer so they bypass RLS while reading roles)
create or replace function public.has_role(p_role public.app_role)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.user_roles ur
    where ur.user_id = auth.uid() and ur.role = p_role
  );
$$;

create or replace function public.is_staff()
returns boolean language sql stable security definer set search_path = public as $$
  select public.has_role('staff') or public.has_role('admin');
$$;

create or replace function public.current_dealer_id()
returns uuid language sql stable security definer set search_path = public as $$
  select dealer_id from public.profiles where id = auth.uid();
$$;

-- Enable RLS on every table
alter table public.dealers        enable row level security;
alter table public.profiles       enable row level security;
alter table public.user_roles     enable row level security;
alter table public.po_clients     enable row level security;
alter table public.regions        enable row level security;
alter table public.products       enable row level security;
alter table public.busbar_types   enable row level security;
alter table public.addons         enable row level security;
alter table public.price_lists    enable row level security;
alter table public.orders         enable row level security;
alter table public.status_history enable row level security;
alter table public.notifications  enable row level security;
alter table public.audit_log      enable row level security;
-- order_panels/order_addons/attachments/qr_codes/shipments: RLS enabled in
-- their feature slices alongside their policies.

-- profiles: self-read; staff read all; self-update
create policy profiles_select on public.profiles for select
  using (id = auth.uid() or public.is_staff());
create policy profiles_update on public.profiles for update
  using (id = auth.uid()) with check (id = auth.uid());

-- user_roles: self-read; staff read all (writes via service role only)
create policy user_roles_select on public.user_roles for select
  using (user_id = auth.uid() or public.is_staff());

-- dealers: staff all; dealer reads own dealer row
create policy dealers_select on public.dealers for select
  using (public.is_staff() or id = public.current_dealer_id());
create policy dealers_write on public.dealers for all
  using (public.is_staff()) with check (public.is_staff());

-- po_clients: dealer sees own dealer's clients; staff all
create policy po_clients_select on public.po_clients for select
  using (public.is_staff() or dealer_id = public.current_dealer_id());
create policy po_clients_write on public.po_clients for all
  using (public.is_staff() or dealer_id = public.current_dealer_id())
  with check (public.is_staff() or dealer_id = public.current_dealer_id());

-- reference data: any authenticated user reads; staff writes
do $$
declare t text;
begin
  foreach t in array array['regions','products','busbar_types','addons','price_lists']
  loop
    execute format(
      'create policy %1$s_read on public.%1$s for select using (auth.uid() is not null);', t);
    execute format(
      'create policy %1$s_write on public.%1$s for all using (public.is_staff()) with check (public.is_staff());', t);
  end loop;
end $$;

-- orders: dealer scoped to own dealer_id; staff all
create policy orders_select on public.orders for select
  using (public.is_staff() or dealer_id = public.current_dealer_id());
create policy orders_insert on public.orders for insert
  with check (public.is_staff() or dealer_id = public.current_dealer_id());
create policy orders_update on public.orders for update
  using (public.is_staff() or dealer_id = public.current_dealer_id())
  with check (public.is_staff() or dealer_id = public.current_dealer_id());

-- status_history: visible if the parent order is visible; staff write
create policy status_history_select on public.status_history for select
  using (
    public.is_staff()
    or exists (
      select 1 from public.orders o
      where o.id = status_history.order_id
        and o.dealer_id = public.current_dealer_id()
    )
  );
create policy status_history_write on public.status_history for all
  using (public.is_staff()) with check (public.is_staff());

-- notifications + audit_log: staff/admin only
create policy notifications_staff on public.notifications for all
  using (public.is_staff()) with check (public.is_staff());
create policy audit_staff on public.audit_log for all
  using (public.is_staff()) with check (public.is_staff());
```

- [ ] **Step 2: Apply and verify it loads cleanly**

Run: `npx supabase migration up`
Expected: `Applying migration 0002_rls.sql...` with no errors. (Behavioral verification is Task 6's test.)

- [ ] **Step 3: Commit**

```bash
git add projects/smartfilm/supabase/migrations/0002_rls.sql
git commit -m "feat(smartfilm): RLS policies + role helper functions"
```

---

## Task 5: Seed reference data + dealers (migration-independent seed)

**Files:**
- Create: `projects/smartfilm/supabase/seed.sql`

- [ ] **Step 1: Write the seed (reference data + two dealers)**

`supabase/seed.sql` (auth users are created in Task 6's test setup via the admin API, not here):
```sql
insert into public.regions (id, name) values
  ('11111111-1111-1111-1111-111111111111', 'New York');

insert into public.products (id, name, product_type) values
  ('22222222-2222-2222-2222-222222222222', 'PDLC Film - White', 'pdlc_film'),
  ('22222222-2222-2222-2222-222222222223', 'PDLC Film - Grey', 'pdlc_film');

insert into public.busbar_types (code, name, svg_key) values
  (1, 'Double busbar on short side', 'bb1'),
  (2, 'Double busbar on long side', 'bb2'),
  (3, 'Single busbar on short sides', 'bb3'),
  (4, 'Double split on short side', 'bb4'),
  (5, 'Double split on long side', 'bb5'),
  (6, 'Double split on short sides', 'bb6'),
  (7, 'Double busbar on short sides (>3m)', 'bb7');

insert into public.addons (name, unit_price) values
  ('German Transformer 100W', 190.00),
  ('German Transformer 300W', 260.00),
  ('Transparent Wire 100m', 40.00),
  ('Power Hinges 4x4 Silver', 105.00);

insert into public.dealers (id, name, pricing_tier) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'Dealer A', 'standard'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'Dealer B', 'standard');

insert into public.price_lists (product_id, price_per_sqft) values
  ('22222222-2222-2222-2222-222222222222', 28.00),
  ('22222222-2222-2222-2222-222222222223', 28.00);
```

- [ ] **Step 2: Reset the DB so the seed runs**

Run: `npx supabase db reset`
Expected: migrations re-applied, then `Seeding data from supabase/seed.sql...`. No errors.

- [ ] **Step 3: Verify seed loaded**

Run: `npx supabase db reset` already prints success; confirm in Studio that `busbar_types` has 7 rows and `dealers` has 2.

- [ ] **Step 4: Commit**

```bash
git add projects/smartfilm/supabase/seed.sql
git commit -m "feat(smartfilm): seed reference data + two test dealers"
```

---

## Task 6: RLS behavior test (the security crux)

**Files:**
- Create: `projects/smartfilm/vitest.config.ts`, `projects/smartfilm/tests/rls.test.ts`, `projects/smartfilm/tests/helpers/admin.ts`
- Modify: `projects/smartfilm/package.json` (add `vitest`, `dotenv`, test script)

- [ ] **Step 1: Install test deps and add a script**

Run: `npm install -D vitest dotenv`
Add to `package.json` `"scripts"`: `"test": "vitest run"`.

- [ ] **Step 2: Create the admin/test helper**

`tests/helpers/admin.ts`:
```ts
import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const service = process.env.SUPABASE_SERVICE_ROLE_KEY!;

export const admin = createClient(url, service, {
  auth: { autoRefreshToken: false, persistSession: false },
});

export async function makeUser(opts: {
  email: string; dealerId: string | null; role: "dealer" | "staff" | "admin";
}) {
  const { data, error } = await admin.auth.admin.createUser({
    email: opts.email,
    password: "password123",
    email_confirm: true,
  });
  if (error) throw error;
  const id = data.user!.id;
  await admin.from("profiles").insert({
    id, email: opts.email, dealer_id: opts.dealerId,
  });
  await admin.from("user_roles").insert({ user_id: id, role: opts.role });
  return id;
}

export function userClient() {
  return createClient(url, anon, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
```

- [ ] **Step 3: Write the failing RLS test**

`tests/rls.test.ts`:
```ts
import "dotenv/config";
import { beforeAll, expect, test } from "vitest";
import { admin, makeUser, userClient } from "./helpers/admin";

const DEALER_A = "aaaaaaaa-0000-0000-0000-000000000001";
const DEALER_B = "aaaaaaaa-0000-0000-0000-000000000002";
const PRODUCT = "22222222-2222-2222-2222-222222222222";
const REGION = "11111111-1111-1111-1111-111111111111";

beforeAll(async () => {
  await makeUser({ email: "a@test.dev", dealerId: DEALER_A, role: "dealer" });
  await makeUser({ email: "b@test.dev", dealerId: DEALER_B, role: "dealer" });
  await makeUser({ email: "staff@test.dev", dealerId: null, role: "staff" });
  await admin.from("orders").insert([
    { dealer_id: DEALER_A, product_id: PRODUCT, region_id: REGION },
    { dealer_id: DEALER_B, product_id: PRODUCT, region_id: REGION },
  ]);
});

async function ordersAs(email: string) {
  const c = userClient();
  await c.auth.signInWithPassword({ email, password: "password123" });
  const { data } = await c.from("orders").select("id, dealer_id");
  return data ?? [];
}

test("dealer A sees only dealer A orders", async () => {
  const rows = await ordersAs("a@test.dev");
  expect(rows.length).toBe(1);
  expect(rows[0].dealer_id).toBe(DEALER_A);
});

test("staff sees all orders", async () => {
  const rows = await ordersAs("staff@test.dev");
  expect(rows.length).toBeGreaterThanOrEqual(2);
});
```

`vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "node" } });
```

- [ ] **Step 4: Reset DB then run the test — expect PASS**

Run: `npx supabase db reset` then `npm run test`
Expected: both tests PASS. If "dealer A sees only dealer A orders" returns 2 rows, RLS is misconfigured — stop and fix `0002_rls.sql` before continuing. (This test is the entire reason the slice exists; it must be green.)

- [ ] **Step 5: Commit**

```bash
git add projects/smartfilm/vitest.config.ts projects/smartfilm/tests projects/smartfilm/package.json projects/smartfilm/package-lock.json
git commit -m "test(smartfilm): RLS dealer-scoping integration test"
```

---

## Task 7: Auth flow + role-aware app shell + E2E smoke + CI

**Files:**
- Create: `src/middleware.ts`, `src/app/login/page.tsx`, `src/app/login/actions.ts`, `src/app/(app)/layout.tsx`, `src/app/(app)/dashboard/page.tsx`, `src/lib/auth/roles.ts`
- Create: `playwright.config.ts`, `e2e/auth.spec.ts`, `.github/workflows/ci.yml`
- Modify: `package.json` (add `@playwright/test`, scripts)

- [ ] **Step 1: Route-protection middleware**

`src/middleware.ts`:
```ts
import { type NextRequest, NextResponse } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  const { response, user } = await updateSession(request);
  const path = request.nextUrl.pathname;
  const isProtected = path.startsWith("/dashboard");
  if (isProtected && !user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 2: Role helper**

`src/lib/auth/roles.ts`:
```ts
import { createClient } from "@/lib/supabase/server";

export async function getRoles(): Promise<string[]> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { data } = await supabase
    .from("user_roles").select("role").eq("user_id", user.id);
  return (data ?? []).map((r) => r.role as string);
}

export function isStaff(roles: string[]) {
  return roles.includes("staff") || roles.includes("admin");
}
```

- [ ] **Step 3: Login page + server actions**

`src/app/login/actions.ts`:
```ts
"use server";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export async function login(formData: FormData) {
  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({
    email: String(formData.get("email")),
    password: String(formData.get("password")),
  });
  if (error) redirect("/login?error=1");
  redirect("/dashboard");
}

export async function logout() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
```

`src/app/login/page.tsx`:
```tsx
import { login } from "./actions";

export default function LoginPage({
  searchParams,
}: { searchParams: { error?: string } }) {
  return (
    <form action={login} className="mx-auto mt-24 flex max-w-sm flex-col gap-3">
      <h1 className="text-xl font-semibold">Sign in</h1>
      {searchParams.error && (
        <p className="text-sm text-red-600">Invalid credentials</p>
      )}
      <input name="email" type="email" placeholder="Email" required
        className="rounded border px-3 py-2" />
      <input name="password" type="password" placeholder="Password" required
        className="rounded border px-3 py-2" />
      <button className="rounded bg-black px-3 py-2 text-white">Sign in</button>
    </form>
  );
}
```

- [ ] **Step 4: Protected app shell + role-scoped dashboard**

`src/app/(app)/layout.tsx`:
```tsx
import { logout } from "@/app/login/actions";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <span className="font-semibold">Smart Film Platform</span>
        <form action={logout}><button className="text-sm underline">Sign out</button></form>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
```

`src/app/(app)/dashboard/page.tsx`:
```tsx
import { createClient } from "@/lib/supabase/server";
import { getRoles, isStaff } from "@/lib/auth/roles";

export default async function Dashboard() {
  const supabase = await createClient();
  const roles = await getRoles();
  // RLS automatically scopes this to the dealer's own orders (or all, for staff)
  const { count } = await supabase
    .from("orders").select("*", { count: "exact", head: true });
  return (
    <div>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-sm text-gray-600">
        Role: {roles.join(", ") || "none"} · {isStaff(roles) ? "all orders" : "your orders"}
      </p>
      <p className="mt-4">Visible orders: <strong>{count ?? 0}</strong></p>
    </div>
  );
}
```

- [ ] **Step 5: Manual verify**

Run `npm run dev`. Visit `/dashboard` → redirected to `/login`. Sign in as `a@test.dev` / `password123` → dashboard shows "Role: dealer · your orders · Visible orders: 1". Sign out, sign in as `staff@test.dev` → "all orders · Visible orders: 2+".

- [ ] **Step 6: Playwright E2E smoke**

Run: `npm install -D @playwright/test && npx playwright install chromium`
Add scripts to `package.json`: `"e2e": "playwright test"`.

`playwright.config.ts`:
```ts
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  webServer: { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: true },
  use: { baseURL: "http://localhost:3000" },
});
```

`e2e/auth.spec.ts`:
```ts
import { expect, test } from "@playwright/test";

test("unauthenticated dashboard redirects to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("dealer A logs in and sees only their orders", async ({ page }) => {
  await page.goto("/login");
  await page.fill('input[name="email"]', "a@test.dev");
  await page.fill('input[name="password"]', "password123");
  await page.click('button:has-text("Sign in")');
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.locator("text=Visible orders:")).toContainText("1");
});
```

- [ ] **Step 7: Run E2E — expect PASS**

Run (ensure `npx supabase db reset` + the Task 6 test users exist first): `npm run e2e`
Expected: both E2E tests PASS.

- [ ] **Step 8: CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: ci
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: projects/smartfilm } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: projects/smartfilm/package-lock.json }
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npm run lint
```
(Note: the RLS/E2E tests need a live Supabase and run locally for now; a CI Supabase service is added in a later hardening slice.)

- [ ] **Step 9: Commit**

```bash
git add projects/smartfilm/src projects/smartfilm/e2e projects/smartfilm/playwright.config.ts projects/smartfilm/package.json projects/smartfilm/package-lock.json .github/workflows/ci.yml
git commit -m "feat(smartfilm): auth flow, role-scoped dashboard, E2E smoke, CI"
```

---

## Self-Review (completed by author)

**Spec coverage (this slice's portion of §2–§4, §10):** stack §2 → Tasks 1–2, 6–7; data model §4 → Task 3; RLS/RBAC §3 → Tasks 4, 6; local-first dev §3 → Tasks 2, 5; security §10 (RLS, auth) → Tasks 4, 6, 7. Order form, busbar selector, pricing, PDF, attachments, DPP, status-machine UI, dashboard filters, email — **deferred to later slices by design** (stated in header scope).

**Placeholder scan:** no TBD/TODO; all code blocks are complete and runnable. The only deferred items are explicitly named future slices, not in-task gaps.

**Type consistency:** `app_role` enum values (`dealer`/`staff`/`admin`) match `user_roles.role`, the `makeUser` role param, and `getRoles`/`isStaff`. `current_dealer_id()`, `is_staff()`, `has_role()` referenced in policies are all defined in Task 4. Table/column names in seed, test, and policies match the Task 3 schema.

## Definition of done

- `npm run test` (RLS) and `npm run e2e` (auth) both green after `npx supabase db reset`.
- A dealer sees only their own orders; staff sees all — enforced by the DB, proven by tests.
- App deploys (Vercel preview or `npm run build`) without type/lint errors.

## Next slices (each its own spec-aligned plan)

2. Reference-data admin (CRUD + price history) · 3. Order form core + auto-calc · 4. Busbar SVG selector + >3m rule · 5. Add-ons + shipping/address · 6. Pricing engine · 7. Summary + PDF spec · 8. Attachments (Storage) · 9. DPP QR integration · 10. Status state-machine · 11. Internal dashboard + dealer cabinet · 12. Email notifications · 13. Hardening.

---

## Addendum 2026-06-29 — scope expansion from dealer order-form docs

Two dealer docs (a process overview + a filled "SGT ORDER" example) were folded into the design spec — see **spec §11–§13** for full detail (exact catalog, accessories + prices, packing math, dealer volume pricing, order-render format, glass tempering sub-form, and a reconciliation table vs. the current build).

**Build status (delivered this session, beyond Slice 1, on the live Supabase project):** order form (film) with dynamic panels + mm/inch toggle, busbar visual selector + panel preview, attachments (edit + new-order staging), submit flow, orders list + read-only order view, owner `/admin` (product groups, products, company managers, dealers + dealer-login edit), required order name, Phosphor icon actions. RLS dealer-scoping verified.

**Revised next slices (replace the list above; detail in spec §13):**
- **A. Catalog & reference seed** — full film products + product groups + accessories (with prices) + busbar names.
- **B. Order-form additions** — Film/Glass split ✓, accessories picker with qty ✓, ratio > 1:2.5 ⚠ warning ✓; remaining: order-type values (New / Replacement-product / Replacement-install), duplicate-panel + 1–30 guard. *(UL-labels dropped 2026-06-29 — not relevant.)*
- **C. Pricing engine** ✓ — per-dealer **monthly volume tiers** (admin config) + effective $/SF on the order total + dealer **progress bar**. *(done 2026-06-29; pricing computed on the fly, not persisted.)*
- **D. Packing calculator (film)** — drum/box bin-pack (≤ 100 SqFt per drum + panel width ≤ box − 6") → boxes on order/PDF.
- **E. Order view + PDF** — match the SGT layout (panels + accessories + shipping + packing + totals).
- **F. Email on submit** — Resend → Production@/office@/sales@smartglasstech.com.
- **G. Phase 3 — Smart-Glass** — glass catalog + glass-only fields (tempering/glass type) + crates + **auto tempering sub-form** (`tempering_jobs`, each panel → 2 glass panels).

Payment gating (paid → production) stays Phase 2; DPP QR, internal kanban, and hardening as previously specced.

**Decisions (locked 2026-06-29):**
1. **Glass is in scope now** — Film + Glass built together (the Phase-3 glass work is pulled forward).
2. **Volume tiers are per-dealer-configurable** (`dealer_volume_tiers`; no single shared tier).
3. **5 busbar types** (codes 1–5): double-on-short, double-on-long, single-each-short, single-each-long, double-each-short. *(Superseded the earlier "keep 7" — extras 6–7 deactivated 2026-06-29.)*
4. **Packing is computed on the fly** (not persisted per order).
5. **Build order: A (catalog seed) → B (form fields) → C (pricing).** Slice A done.
