# MorningGlow Database Schema — Implementation Plan (Etappe 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Supabase schema — every field of the concept model, RLS on every table, and typed repositories — with no user interface.

**Architecture:** Numbered SQL migrations under `supabase/migrations/`. Health data lives in its own tables so it can be deleted without deleting the account. Every table carries RLS; tests prove the policies by impersonating two users and asserting that neither can reach the other's rows. Repositories in `src/data/` are the only code that knows Supabase exists.

**Tech Stack:** Supabase (Postgres 15, EU region), `@supabase/supabase-js`, `pg` for policy tests, vitest.

**Spec:** `docs/superpowers/specs/2026-08-29-morningglow-design.md`

**Depends on:** Etappe 1 (`docs/superpowers/plans/2026-08-29-morningglow-core-engine.md`) — repositories return the types `src/core` defines. Etappe 2 can start in parallel; only Task 11 onward needs core merged.

---

## Two decisions that shape everything below

**The day is the user's, not the server's.** This is a morning app: people use it at 06:00 local time. A `timestamptz` converted to a UTC date puts a woman in UTC+13 on the wrong day, and her streak breaks for a reason she cannot see. Every daily table therefore stores a `local_date date` supplied by the client alongside the `timestamptz` of the actual event. The date is what the app groups by; the timestamp is for audit.

**Health data is separately deletable.** Art. 9 GDPR consent can be withdrawn without closing the account. So `health_profile`, `symptom_assessments`, `daily_checkins` and `exercise_feedback` cascade from `auth.users`, but can also be dropped on their own by a single function that leaves `profiles` intact.

---

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/0001_profiles.sql` | Account-level profile + `updated_at` trigger helper |
| `supabase/migrations/0002_consents.sql` | Consent records, general and health separately |
| `supabase/migrations/0003_health_profile.sql` | The Art. 9 table: full concept model |
| `supabase/migrations/0004_symptom_assessments.sql` | Assessment history |
| `supabase/migrations/0005_daily.sql` | `daily_checkins`, `ritual_completions`, `routine_overrides` |
| `supabase/migrations/0006_exercise_feedback.sql` | Completion signal for v2 learning |
| `supabase/migrations/0007_content.sql` | `articles`, `exercises` — service-role write, authenticated read |
| `supabase/migrations/0008_erase_health_data.sql` | Function to erase health data without the account |
| `src/data/client.ts` | The single Supabase client |
| `src/data/profileRepo.ts` | Profile + health profile read/write |
| `src/data/dailyRepo.ts` | Check-ins, completions, overrides |
| `src/data/contentRepo.ts` | Articles and exercises |
| `src/core/streak.ts` | Soft-streak computation (pure, belongs to core) |
| `tests/db/rls.test.ts` | Policy tests against a real Postgres |

---

## Task 1: Supabase project and test connection

**Files:**
- Create: `supabase/config.toml`
- Create: `.env.example`
- Modify: `package.json`
- Test: `tests/db/connection.test.ts`

- [ ] **Step 1: Create the Supabase project**

In the Supabase dashboard create a project in an **EU region** (Frankfurt). Health data must not leave the EU. Note the project ref, the database connection string and the service-role key.

- [ ] **Step 2: Add dependencies**

```bash
npm install @supabase/supabase-js pg
npm install -D @types/pg dotenv
```

- [ ] **Step 3: Write `.env.example`**

```
# Supabase project (EU region)
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=
# Server-side only. Never bundled into the app.
SUPABASE_SERVICE_ROLE_KEY=
# Direct Postgres connection, used by the RLS tests only.
SUPABASE_TEST_DB_URL=postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres
```

- [ ] **Step 4: Add `.env` to `.gitignore`**

Confirm `.env*` is already listed from Etappe 1 Task 1. If not, add it.

- [ ] **Step 5: Add the migration and db-test scripts to `package.json`**

```json
{
  "scripts": {
    "test": "vitest run --exclude tests/db",
    "test:db": "vitest run tests/db",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit",
    "db:push": "supabase db push"
  }
}
```

Database tests are excluded from `npm test` on purpose: they need a live connection, and the core suite must stay runnable offline.

- [ ] **Step 5b: Widen the vitest include so `tests/` is discoverable**

Etappe 1 set `include: ['src/**/*.test.ts']`, which would make `npm run test:db` match nothing. Update `vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
  },
});
```

- [ ] **Step 6: Write the connection test**

`tests/db/connection.test.ts`:

```ts
import { describe, it, expect, beforeAll } from 'vitest';
import { Client } from 'pg';
import 'dotenv/config';

describe('database connection', () => {
  let client: Client;

  beforeAll(async () => {
    const url = process.env.SUPABASE_TEST_DB_URL;
    if (!url) throw new Error('SUPABASE_TEST_DB_URL is not set');
    client = new Client({ connectionString: url });
    await client.connect();
  });

  it('reaches a Postgres 15 or newer', async () => {
    const { rows } = await client.query('show server_version_num');
    expect(Number(rows[0].server_version_num)).toBeGreaterThanOrEqual(150000);
  });

  it('has the Supabase auth schema', async () => {
    const { rows } = await client.query(
      `select 1 from information_schema.tables
       where table_schema = 'auth' and table_name = 'users'`,
    );
    expect(rows).toHaveLength(1);
  });
});
```

- [ ] **Step 7: Run it**

```bash
npm run test:db -- connection
```

Expected: 2 tests pass.

- [ ] **Step 8: Commit**

```bash
git add .env.example .gitignore package.json tests/db/connection.test.ts supabase/
git commit -m "chore(db): Supabase project wiring and connection test"
```

---

## Task 2: Profiles and the shared `updated_at` trigger

**Files:**
- Create: `supabase/migrations/0001_profiles.sql`
- Test: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0001_profiles.sql — account-level profile. No health data here.

create extension if not exists "pgcrypto";

-- Shared trigger function: every table with updated_at reuses this one.
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.profiles (
  id                    uuid primary key references auth.users(id) on delete cascade,
  display_name          text,
  locale                text not null default 'de',
  onboarding_completed_at timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create trigger profiles_touch_updated_at
  before update on public.profiles
  for each row execute function public.touch_updated_at();

alter table public.profiles enable row level security;

create policy profiles_select_own on public.profiles
  for select using (auth.uid() = id);

create policy profiles_insert_own on public.profiles
  for insert with check (auth.uid() = id);

create policy profiles_update_own on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

create policy profiles_delete_own on public.profiles
  for delete using (auth.uid() = id);
```

- [ ] **Step 2: Write the RLS test harness and the first policy test**

`tests/db/rls.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { Client } from 'pg';
import { randomUUID } from 'node:crypto';
import 'dotenv/config';

const ALICE = randomUUID();
const BOB = randomUUID();

let db: Client;

/**
 * Runs a query as an authenticated user, exactly the way PostgREST does:
 * the role plus a JWT claim carrying the user id. Wrapped in a transaction
 * that is always rolled back, so tests leave no rows behind.
 */
export async function asUser<T>(
  userId: string,
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  await db.query('begin');
  try {
    await db.query(`set local role authenticated`);
    await db.query(`set local request.jwt.claims = $1`, [
      JSON.stringify({ sub: userId, role: 'authenticated' }),
    ]);
    const { rows } = await db.query(sql, params);
    return rows as T[];
  } finally {
    await db.query('rollback');
  }
}

beforeAll(async () => {
  db = new Client({ connectionString: process.env.SUPABASE_TEST_DB_URL });
  await db.connect();
  // Seed two auth users as the service role.
  //
  // If this INSERT fails on a NOT NULL column, the Supabase release in use has
  // a wider auth.users than the columns listed here. Do not start guessing
  // columns — create the users through the Admin API instead:
  //   const admin = createClient(URL, SERVICE_ROLE_KEY);
  //   await admin.auth.admin.createUser({ email, password, email_confirm: true });
  // and keep the returned ids in ALICE / BOB.
  for (const id of [ALICE, BOB]) {
    await db.query(
      `insert into auth.users (id, email, instance_id, aud, role)
       values ($1, $2, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated')
       on conflict (id) do nothing`,
      [id, `${id}@test.local`],
    );
    await db.query(
      `insert into public.profiles (id) values ($1) on conflict (id) do nothing`,
      [id],
    );
  }
});

afterAll(async () => {
  await db.query(`delete from auth.users where id = any($1)`, [[ALICE, BOB]]);
  await db.end();
});

describe('profiles RLS', () => {
  it('lets a user read her own profile', async () => {
    const rows = await asUser(ALICE, `select id from public.profiles where id = $1`, [ALICE]);
    expect(rows).toHaveLength(1);
  });

  it('hides another user profile', async () => {
    const rows = await asUser(ALICE, `select id from public.profiles where id = $1`, [BOB]);
    expect(rows).toHaveLength(0);
  });

  it('refuses to insert a profile under another user id', async () => {
    await expect(
      asUser(ALICE, `insert into public.profiles (id) values ($1)`, [randomUUID()]),
    ).rejects.toThrow(/row-level security/i);
  });
});
```

- [ ] **Step 3: Apply the migration and run the test**

```bash
npx supabase db push
npm run test:db -- rls
```

Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0001_profiles.sql tests/db/rls.test.ts
git commit -m "feat(db): profiles table with RLS and a policy test harness"
```

---

## Task 3: Consents

Two consents, recorded separately. The health consent is the legal basis for everything in Task 4 onward; withdrawing it must be a distinct, recorded act.

**Files:**
- Create: `supabase/migrations/0002_consents.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0002_consents.sql — consent records. Health consent (Art. 9 GDPR) is
-- recorded separately from the general terms, and can be withdrawn alone.

create type public.consent_kind as enum ('terms', 'privacy', 'health_data');

create table public.consents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  kind        public.consent_kind not null,
  -- Which text version was agreed to. A new version needs a new consent.
  version     text not null,
  granted_at  timestamptz not null default now(),
  revoked_at  timestamptz
);

-- One live consent per kind and version; revoked rows stay for the audit trail.
create unique index consents_one_live_per_kind
  on public.consents (user_id, kind)
  where revoked_at is null;

create index consents_user_idx on public.consents (user_id);

alter table public.consents enable row level security;

create policy consents_select_own on public.consents
  for select using (auth.uid() = user_id);

create policy consents_insert_own on public.consents
  for insert with check (auth.uid() = user_id);

-- Update is allowed only to set revoked_at: a granted consent is a record of
-- fact and must not be rewritten.
create policy consents_revoke_own on public.consents
  for update using (auth.uid() = user_id and revoked_at is null)
  with check (auth.uid() = user_id);

create or replace function public.has_health_consent(u uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.consents
    where user_id = u and kind = 'health_data' and revoked_at is null
  );
$$;
```

- [ ] **Step 2: Add the tests to `tests/db/rls.test.ts`**

```ts
describe('consents', () => {
  it('records a health consent separately from the terms', async () => {
    const rows = await asUser(ALICE, `
      insert into public.consents (user_id, kind, version)
      values ($1, 'terms', 'v1'), ($1, 'health_data', 'v1')
      returning kind
    `, [ALICE]);
    expect(rows.map((r: { kind: string }) => r.kind).sort()).toEqual(['health_data', 'terms']);
  });

  it('allows only one live consent per kind', async () => {
    await expect(asUser(ALICE, `
      insert into public.consents (user_id, kind, version)
      values ($1, 'health_data', 'v1'), ($1, 'health_data', 'v2')
    `, [ALICE])).rejects.toThrow(/consents_one_live_per_kind/);
  });

  it('hides another user consents', async () => {
    const rows = await asUser(BOB, `select id from public.consents where user_id = $1`, [ALICE]);
    expect(rows).toHaveLength(0);
  });
});
```

- [ ] **Step 3: Apply and run**

```bash
npx supabase db push && npm run test:db -- rls
```

Expected: 6 tests pass.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0002_consents.sql tests/db/rls.test.ts
git commit -m "feat(db): consent records with health consent separated"
```

---

## Task 4: Health profile — the full concept model

Every field of the concept model is created now, including the ones no screen writes until v2. Adding a column later is a migration against live data; adding it now is free.

**Files:**
- Create: `supabase/migrations/0003_health_profile.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0003_health_profile.sql — Art. 9 GDPR data. Separate table so it can be
-- erased without closing the account.

create type public.menopause_phase as enum ('earlyPeri', 'peri', 'meno', 'post', 'unsure');
create type public.hrt_status      as enum ('no', 'recent', 'long', 'excluded');
create type public.fitness_level   as enum ('gentle', 'moderate', 'active');
create type public.restriction     as enum ('back', 'knees', 'shoulders', 'balance');
create type public.preference      as enum (
  'breathing', 'meditation', 'movement', 'journaling',
  'gratitude', 'knowledge', 'nutrition', 'open'
);
-- v2 fields, typed now so the columns never need altering later.
create type public.sleep_pattern   as enum (
  'sleeps_through', 'wakes_falls_back', 'wakes_stays_awake',
  'hard_to_fall_asleep', 'unrefreshed'
);
create type public.day_structure   as enum ('full_time', 'part_time', 'transition', 'retired');
create type public.routine_history as enum ('new', 'tried_stopped', 'has_one');

create table public.health_profile (
  user_id        uuid primary key references auth.users(id) on delete cascade,

  -- v1
  phase          public.menopause_phase,
  hrt_status     public.hrt_status,
  fitness_level  public.fitness_level,
  budget_min     smallint check (budget_min in (5, 10, 15, 20, 30)),
  wake_window    text,
  preferences    public.preference[] not null default '{}',
  -- NULL means not asked yet; '{}' means asked and nothing applies.
  restrictions   public.restriction[],

  -- v2, collected by progressive profiling
  motivation     text[] not null default '{}',
  sleep_pattern  public.sleep_pattern,
  day_structure  public.day_structure,
  routine_history public.routine_history,
  weekend_differs boolean,

  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  constraint preferences_max_three check (cardinality(preferences) <= 3)
);

create trigger health_profile_touch_updated_at
  before update on public.health_profile
  for each row execute function public.touch_updated_at();

alter table public.health_profile enable row level security;

-- Writing health data requires a live health consent. The check lives in the
-- policy rather than in application code so it cannot be bypassed.
create policy health_profile_select_own on public.health_profile
  for select using (auth.uid() = user_id);

create policy health_profile_insert_own on public.health_profile
  for insert with check (auth.uid() = user_id and public.has_health_consent(auth.uid()));

create policy health_profile_update_own on public.health_profile
  for update using (auth.uid() = user_id and public.has_health_consent(auth.uid()))
  with check (auth.uid() = user_id);

create policy health_profile_delete_own on public.health_profile
  for delete using (auth.uid() = user_id);
```

- [ ] **Step 2: Add the tests**

```ts
describe('health_profile', () => {
  const grant = `insert into public.consents (user_id, kind, version)
                 values ($1, 'health_data', 'v1')`;

  it('accepts a full v1 profile once health consent exists', async () => {
    const rows = await asUser(ALICE, `
      ${grant};
      insert into public.health_profile
        (user_id, phase, hrt_status, fitness_level, budget_min, preferences, restrictions)
      values ($1, 'peri', 'no', 'gentle', 15, '{breathing,movement}', '{}')
      returning budget_min
    `, [ALICE]);
    expect(rows[0]).toEqual({ budget_min: 15 });
  });

  it('refuses health data without a health consent', async () => {
    await expect(asUser(BOB, `
      insert into public.health_profile (user_id, phase) values ($1, 'peri')
    `, [BOB])).rejects.toThrow(/row-level security/i);
  });

  it('rejects a budget outside the offered options', async () => {
    await expect(asUser(ALICE, `
      ${grant};
      insert into public.health_profile (user_id, budget_min) values ($1, 7)
    `, [ALICE])).rejects.toThrow(/budget_min/);
  });

  it('rejects more than three preferences', async () => {
    await expect(asUser(ALICE, `
      ${grant};
      insert into public.health_profile (user_id, preferences)
      values ($1, '{breathing,movement,journaling,gratitude}')
    `, [ALICE])).rejects.toThrow(/preferences_max_three/);
  });

  it('distinguishes restrictions not asked from restrictions none', async () => {
    const rows = await asUser(ALICE, `
      ${grant};
      insert into public.health_profile (user_id) values ($1);
      select restrictions is null as not_asked from public.health_profile where user_id = $1
    `, [ALICE]);
    expect(rows[0]).toEqual({ not_asked: true });
  });
});
```

- [ ] **Step 3: Apply and run**

```bash
npx supabase db push && npm run test:db -- rls
```

Expected: 11 tests pass.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0003_health_profile.sql tests/db/rls.test.ts
git commit -m "feat(db): health profile, consent-gated by policy"
```

---

## Task 5: Symptom assessments

**Files:**
- Create: `supabase/migrations/0004_symptom_assessments.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0004_symptom_assessments.sql — history of the 0-4 severity ratings.
-- One row per assessment, never updated: the trend line is the point.

-- Postgres forbids a subquery inside CHECK, so the per-key validation lives in
-- an IMMUTABLE function the constraint calls.
create or replace function public.scores_within_scale(scores jsonb)
returns boolean
language sql
immutable
as $$
  select coalesce(bool_and(
    jsonb_typeof(value) = 'number' and (value::numeric) between 0 and 4
  ), true)
  from jsonb_each(scores);
$$;

create table public.symptom_assessments (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  assessed_at timestamptz not null default now(),
  local_date  date not null,
  -- { "sleep": 3, "fatigue": 2 } — keys are symptom ids, values 0-4.
  scores      jsonb not null,

  constraint scores_is_object check (jsonb_typeof(scores) = 'object'),
  constraint scores_within_scale check (public.scores_within_scale(scores))
);

create index symptom_assessments_user_date_idx
  on public.symptom_assessments (user_id, local_date desc);

alter table public.symptom_assessments enable row level security;

create policy symptom_assessments_select_own on public.symptom_assessments
  for select using (auth.uid() = user_id);

create policy symptom_assessments_insert_own on public.symptom_assessments
  for insert with check (auth.uid() = user_id and public.has_health_consent(auth.uid()));

create policy symptom_assessments_delete_own on public.symptom_assessments
  for delete using (auth.uid() = user_id);
```

There is deliberately no update policy: an assessment is a record of how she felt on a day. Correcting it means recording a new one.

- [ ] **Step 2: Add the tests**

```ts
describe('symptom_assessments', () => {
  const grant = `insert into public.consents (user_id, kind, version)
                 values ($1, 'health_data', 'v1')`;

  it('stores a severity map', async () => {
    const rows = await asUser(ALICE, `
      ${grant};
      insert into public.symptom_assessments (user_id, local_date, scores)
      values ($1, '2026-08-29', '{"sleep": 3, "fatigue": 2}')
      returning scores
    `, [ALICE]);
    expect(rows[0].scores).toEqual({ sleep: 3, fatigue: 2 });
  });

  it('rejects a severity above the scale', async () => {
    await expect(asUser(ALICE, `
      ${grant};
      insert into public.symptom_assessments (user_id, local_date, scores)
      values ($1, '2026-08-29', '{"sleep": 9}')
    `, [ALICE])).rejects.toThrow(/scores_within_scale/);
  });

  it('rejects a non-numeric severity', async () => {
    await expect(asUser(ALICE, `
      ${grant};
      insert into public.symptom_assessments (user_id, local_date, scores)
      values ($1, '2026-08-29', '{"sleep": "viel"}')
    `, [ALICE])).rejects.toThrow(/scores_within_scale/);
  });

  it('has no update path', async () => {
    const rows = await asUser(ALICE, `
      select count(*)::int as n from pg_policies
      where tablename = 'symptom_assessments' and cmd = 'UPDATE'
    `);
    expect(rows[0]).toEqual({ n: 0 });
  });
});
```

- [ ] **Step 3: Apply and run**

```bash
npx supabase db push && npm run test:db -- rls
```

Expected: 15 tests pass.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0004_symptom_assessments.sql tests/db/rls.test.ts
git commit -m "feat(db): symptom assessment history, insert-only"
```

---

## Task 6: The daily tables

**Files:**
- Create: `supabase/migrations/0005_daily.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0005_daily.sql — check-ins, completions and manual routine overrides.
-- All keyed by local_date: the day belongs to the user, not to the server.

create table public.daily_checkins (
  user_id      uuid not null references auth.users(id) on delete cascade,
  local_date   date not null,
  recorded_at  timestamptz not null default now(),
  mood         smallint check (mood between 1 and 5),
  energy       smallint check (energy between 1 and 5),
  hot_flashes  smallint check (hot_flashes between 0 and 4),
  sleep_quality smallint check (sleep_quality between 1 and 5),
  primary key (user_id, local_date)
);

create table public.ritual_completions (
  user_id        uuid not null references auth.users(id) on delete cascade,
  local_date     date not null,
  completed_at   timestamptz not null default now(),
  -- ["water","light","breath","ex:catcow"] — the steps actually finished.
  completed_steps jsonb not null default '[]',
  duration_sec   integer check (duration_sec >= 0),
  primary key (user_id, local_date),

  constraint completed_steps_is_array check (jsonb_typeof(completed_steps) = 'array')
);

create table public.routine_overrides (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  excluded_steps text[] not null default '{}',
  added_steps    text[] not null default '{}',
  updated_at    timestamptz not null default now()
);

create trigger routine_overrides_touch_updated_at
  before update on public.routine_overrides
  for each row execute function public.touch_updated_at();

alter table public.daily_checkins     enable row level security;
alter table public.ritual_completions enable row level security;
alter table public.routine_overrides  enable row level security;

do $$
declare t text;
begin
  foreach t in array array['daily_checkins', 'ritual_completions', 'routine_overrides']
  loop
    execute format(
      'create policy %1$s_select_own on public.%1$I for select using (auth.uid() = user_id)', t);
    execute format(
      'create policy %1$s_insert_own on public.%1$I for insert with check (auth.uid() = user_id)', t);
    execute format(
      'create policy %1$s_update_own on public.%1$I for update using (auth.uid() = user_id) with check (auth.uid() = user_id)', t);
    execute format(
      'create policy %1$s_delete_own on public.%1$I for delete using (auth.uid() = user_id)', t);
  end loop;
end $$;
```

`ritual_completions` and `daily_checkins` are keyed on `(user_id, local_date)` so a repeated sync upserts rather than duplicating — the primary defence against the streak drifting.

- [ ] **Step 2: Add the tests**

```ts
describe('daily tables', () => {
  it('keeps one completion per user and day, upserting on repeat', async () => {
    const rows = await asUser(ALICE, `
      insert into public.ritual_completions (user_id, local_date, duration_sec)
      values ($1, '2026-08-29', 600)
      on conflict (user_id, local_date) do update set duration_sec = excluded.duration_sec;
      insert into public.ritual_completions (user_id, local_date, duration_sec)
      values ($1, '2026-08-29', 900)
      on conflict (user_id, local_date) do update set duration_sec = excluded.duration_sec;
      select count(*)::int as n, max(duration_sec) as secs
      from public.ritual_completions where user_id = $1
    `, [ALICE]);
    expect(rows[0]).toEqual({ n: 1, secs: 900 });
  });

  it('rejects a mood outside 1-5', async () => {
    await expect(asUser(ALICE, `
      insert into public.daily_checkins (user_id, local_date, mood)
      values ($1, '2026-08-29', 9)
    `, [ALICE])).rejects.toThrow(/mood/);
  });

  it('hides another user check-ins', async () => {
    const rows = await asUser(BOB, `
      select local_date from public.daily_checkins where user_id = $1
    `, [ALICE]);
    expect(rows).toHaveLength(0);
  });
});
```

- [ ] **Step 3: Apply and run**

```bash
npx supabase db push && npm run test:db -- rls
```

Expected: 18 tests pass.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0005_daily.sql tests/db/rls.test.ts
git commit -m "feat(db): daily check-ins, completions and overrides keyed by local date"
```

---

## Task 7: Exercise feedback

**Files:**
- Create: `supabase/migrations/0006_exercise_feedback.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0006_exercise_feedback.sql — the signal v2 learns from. Written in v1,
-- read by nobody yet: the model needs weeks of history before it is useful.

create type public.step_outcome as enum ('completed', 'aborted', 'skipped');

create table public.exercise_feedback (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  local_date date not null,
  -- Module id ('breath') or exercise id prefixed 'ex:' ('ex:catcow').
  step_id    text not null,
  outcome    public.step_outcome not null,
  recorded_at timestamptz not null default now()
);

create index exercise_feedback_user_step_idx
  on public.exercise_feedback (user_id, step_id, local_date desc);

alter table public.exercise_feedback enable row level security;

create policy exercise_feedback_select_own on public.exercise_feedback
  for select using (auth.uid() = user_id);

create policy exercise_feedback_insert_own on public.exercise_feedback
  for insert with check (auth.uid() = user_id);

create policy exercise_feedback_delete_own on public.exercise_feedback
  for delete using (auth.uid() = user_id);
```

- [ ] **Step 2: Add the test**

```ts
describe('exercise_feedback', () => {
  it('records the three outcomes the concept distinguishes', async () => {
    const rows = await asUser(ALICE, `
      insert into public.exercise_feedback (user_id, local_date, step_id, outcome)
      values ($1, '2026-08-29', 'breath', 'completed'),
             ($1, '2026-08-29', 'ex:tree', 'aborted'),
             ($1, '2026-08-29', 'gratitude', 'skipped')
      returning outcome
    `, [ALICE]);
    expect(rows.map((r: { outcome: string }) => r.outcome).sort())
      .toEqual(['aborted', 'completed', 'skipped']);
  });
});
```

- [ ] **Step 3: Apply, run and commit**

```bash
npx supabase db push && npm run test:db -- rls
git add supabase/migrations/0006_exercise_feedback.sql tests/db/rls.test.ts
git commit -m "feat(db): exercise feedback signal for v2 learning"
```

Expected: 19 tests pass.

---

## Task 8: Content tables

**Files:**
- Create: `supabase/migrations/0007_content.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0007_content.sql — articles and exercises live in the database so content
-- ships without an app release. The module catalog does NOT: it is fused with
-- the engine and stays in code.

create table public.articles (
  id           uuid primary key default gen_random_uuid(),
  slug         text not null,
  locale       text not null default 'de',
  category     text not null,
  title        text not null,
  subtitle     text,
  read_min     smallint not null check (read_min > 0),
  -- Array of blocks: strings, or objects like {"kind":"checklist",...}
  body         jsonb not null,
  published_at timestamptz,
  -- Medical review is a release gate. Unreviewed articles never publish.
  reviewed_by  text,
  reviewed_at  timestamptz,

  unique (slug, locale),
  constraint body_is_array check (jsonb_typeof(body) = 'array'),
  constraint published_needs_review check (
    published_at is null or (reviewed_by is not null and reviewed_at is not null)
  )
);

create table public.exercises (
  id                text primary key,
  level             public.fitness_level not null,
  name              text not null,
  dose              text not null,
  description       text not null,
  duration_sec      smallint not null check (duration_sec > 0),
  video_path        text,
  photo_path        text,
  contraindications public.restriction[] not null default '{}',
  -- Physiotherapist sign-off on the contraindications, same gate as articles.
  reviewed_by       text,
  reviewed_at       timestamptz
);

alter table public.articles  enable row level security;
alter table public.exercises enable row level security;

-- Read for everyone signed in; writes only via the service role, which
-- bypasses RLS. No write policy exists, so no client can write content.
create policy articles_read on public.articles
  for select to authenticated using (published_at is not null);

create policy exercises_read on public.exercises
  for select to authenticated using (true);
```

- [ ] **Step 2: Add the tests**

```ts
describe('content', () => {
  it('refuses to publish an article that no one reviewed', async () => {
    await expect(db.query(`
      insert into public.articles (slug, category, title, read_min, body, published_at)
      values ('unreviewed', 'Hormone', 'Test', 3, '[]', now())
    `)).rejects.toThrow(/published_needs_review/);
  });

  it('accepts a reviewed, published article', async () => {
    const { rows } = await db.query(`
      insert into public.articles
        (slug, category, title, read_min, body, published_at, reviewed_by, reviewed_at)
      values ('reviewed', 'Hormone', 'Test', 3, '[]', now(), 'Dr. Muster', now())
      returning slug
    `);
    expect(rows[0].slug).toBe('reviewed');
    await db.query(`delete from public.articles where slug in ('reviewed','unreviewed')`);
  });

  it('hides unpublished articles from clients', async () => {
    await db.query(`
      insert into public.articles (slug, category, title, read_min, body)
      values ('draft', 'Hormone', 'Entwurf', 3, '[]')
    `);
    const rows = await asUser(ALICE, `select slug from public.articles where slug = 'draft'`);
    expect(rows).toHaveLength(0);
    await db.query(`delete from public.articles where slug = 'draft'`);
  });

  it('gives clients no way to write content', async () => {
    const rows = await asUser(ALICE, `
      select count(*)::int as n from pg_policies
      where tablename in ('articles','exercises') and cmd <> 'SELECT'
    `);
    expect(rows[0]).toEqual({ n: 0 });
  });
});
```

- [ ] **Step 3: Apply, run and commit**

```bash
npx supabase db push && npm run test:db -- rls
git add supabase/migrations/0007_content.sql tests/db/rls.test.ts
git commit -m "feat(db): content tables with medical review as a publish gate"
```

Expected: 23 tests pass.

---

## Task 9: Erase health data without deleting the account

**Files:**
- Create: `supabase/migrations/0008_erase_health_data.sql`
- Modify: `tests/db/rls.test.ts`

- [ ] **Step 1: Write the migration**

```sql
-- 0008_erase_health_data.sql — withdrawing the Art. 9 consent must remove the
-- health data and nothing else. The account, the locale and the terms consent
-- survive.

create or replace function public.erase_health_data()
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
  u uuid := auth.uid();
begin
  if u is null then
    raise exception 'not authenticated';
  end if;

  delete from public.exercise_feedback    where user_id = u;
  delete from public.daily_checkins       where user_id = u;
  delete from public.symptom_assessments  where user_id = u;
  delete from public.routine_overrides    where user_id = u;
  delete from public.ritual_completions   where user_id = u;
  delete from public.health_profile       where user_id = u;

  update public.consents
     set revoked_at = now()
   where user_id = u and kind = 'health_data' and revoked_at is null;
end;
$$;

grant execute on function public.erase_health_data() to authenticated;
```

`security invoker` is deliberate: the deletes run under the caller's own RLS policies, so the function cannot be turned into a way to erase somebody else's data.

- [ ] **Step 2: Add the test**

```ts
describe('erase_health_data', () => {
  it('removes health data but keeps the account and the terms consent', async () => {
    const rows = await asUser(ALICE, `
      insert into public.consents (user_id, kind, version)
        values ($1, 'terms', 'v1'), ($1, 'health_data', 'v1');
      insert into public.health_profile (user_id, phase) values ($1, 'peri');
      insert into public.daily_checkins (user_id, local_date, mood)
        values ($1, '2026-08-29', 4);

      select public.erase_health_data();

      select
        (select count(*)::int from public.health_profile where user_id = $1) as health,
        (select count(*)::int from public.daily_checkins where user_id = $1) as checkins,
        (select count(*)::int from public.profiles where id = $1) as account,
        (select count(*)::int from public.consents
          where user_id = $1 and kind = 'terms' and revoked_at is null) as terms,
        (select count(*)::int from public.consents
          where user_id = $1 and kind = 'health_data' and revoked_at is null) as health_consent
    `, [ALICE]);
    expect(rows[0]).toEqual({
      health: 0, checkins: 0, account: 1, terms: 1, health_consent: 0,
    });
  });
});
```

- [ ] **Step 3: Apply, run and commit**

```bash
npx supabase db push && npm run test:db -- rls
git add supabase/migrations/0008_erase_health_data.sql tests/db/rls.test.ts
git commit -m "feat(db): erase health data without closing the account"
```

Expected: 24 tests pass.

---

## Task 10: Soft streak

Pure logic, so it belongs in `src/core` and follows core's rules: no clock, no I/O.

**Files:**
- Create: `src/core/streak.ts`
- Modify: `src/core/index.ts`
- Test: `src/core/__tests__/streak.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { computeStreak } from '../streak';

const today = '2026-08-29';

describe('computeStreak', () => {
  it('is zero with no completions', () => {
    expect(computeStreak([], today)).toBe(0);
  });

  it('counts an unbroken run ending today', () => {
    expect(computeStreak(['2026-08-27', '2026-08-28', '2026-08-29'], today)).toBe(3);
  });

  it('survives a single missed day', () => {
    // 26th missed, 25/27/28/29 done
    expect(computeStreak(
      ['2026-08-25', '2026-08-27', '2026-08-28', '2026-08-29'], today,
    )).toBe(4);
  });

  it('ends at a gap of two days or more', () => {
    // 26th and 27th both missed
    expect(computeStreak(
      ['2026-08-24', '2026-08-25', '2026-08-28', '2026-08-29'], today,
    )).toBe(2);
  });

  it('stays alive when yesterday was missed but today is done', () => {
    expect(computeStreak(['2026-08-27', '2026-08-29'], today)).toBe(2);
  });

  it('stays alive on a day not yet completed, if yesterday was', () => {
    expect(computeStreak(['2026-08-27', '2026-08-28'], today)).toBe(2);
  });

  it('is zero when the last completion is long past', () => {
    expect(computeStreak(['2026-08-01'], today)).toBe(0);
  });

  it('ignores duplicates and unsorted input', () => {
    expect(computeStreak(
      ['2026-08-29', '2026-08-27', '2026-08-28', '2026-08-28'], today,
    )).toBe(3);
  });
});
```

The sixth test is the one that carries the product decision: at 07:00, before she has done anything, she must still see her streak. Zeroing it the moment a new day starts would punish her for waking up.

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- streak
```

Expected: FAIL — cannot resolve `../streak`.

- [ ] **Step 3: Write `src/core/streak.ts`**

```ts
const MS_PER_DAY = 86_400_000;

function toDayNumber(isoDate: string): number {
  return Math.floor(Date.parse(`${isoDate}T00:00:00Z`) / MS_PER_DAY);
}

/** A gap larger than this many days ends the streak. */
const FORGIVEN_GAP = 1;

/**
 * Counts completed days back from today, tolerating one missed day at a time.
 *
 * "Sanft statt streng" applied to the number the user sees most often: a single
 * missed morning must not erase weeks of effort, because the thing that keeps a
 * habit alive is how easy it is to come back, not how unbroken the chain looks.
 *
 * Dates are plain local ISO dates (YYYY-MM-DD) and `today` is passed in, never
 * read from a clock — the day belongs to the user's timezone, not the server's.
 */
export function computeStreak(
  completedDates: readonly string[],
  today: string,
): number {
  if (completedDates.length === 0) return 0;

  const days = [...new Set(completedDates)]
    .map(toDayNumber)
    .sort((a, b) => b - a);

  const todayNum = toDayNumber(today);

  // Today not yet done is not a break; more than one day of silence is.
  if (todayNum - days[0]! > FORGIVEN_GAP + 1) return 0;

  let streak = 1;
  for (let i = 1; i < days.length; i++) {
    const gap = days[i - 1]! - days[i]!;
    if (gap > FORGIVEN_GAP + 1) break;
    streak++;
  }
  return streak;
}
```

- [ ] **Step 4: Export it and run**

Add `export * from './streak';` to `src/core/index.ts`, then:

```bash
npm test -- streak && npm run typecheck
```

Expected: 8 tests pass, typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add src/core/streak.ts src/core/index.ts src/core/__tests__/streak.test.ts
git commit -m "feat(core): soft streak that forgives a single missed day"
```

---

## Task 11: Supabase client

**Files:**
- Create: `src/data/client.ts`
- Test: `src/data/__tests__/client.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { createMorningGlowClient } from '../client';

describe('createMorningGlowClient', () => {
  it('refuses to build without a URL', () => {
    expect(() => createMorningGlowClient({ url: '', anonKey: 'k' }))
      .toThrow(/SUPABASE_URL/);
  });

  it('refuses to build without an anon key', () => {
    expect(() => createMorningGlowClient({ url: 'https://x.supabase.co', anonKey: '' }))
      .toThrow(/SUPABASE_ANON_KEY/);
  });

  it('refuses a service-role key on the client', () => {
    expect(() => createMorningGlowClient({
      url: 'https://x.supabase.co',
      anonKey: 'eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.x',
    })).toThrow(/service_role/);
  });

  it('builds with a valid URL and anon key', () => {
    const client = createMorningGlowClient({
      url: 'https://x.supabase.co',
      anonKey: 'eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.x',
    });
    expect(client.auth).toBeDefined();
  });
});
```

The third test exists because a service-role key shipped in a mobile bundle hands every user's health data to anyone who unzips the app. A runtime guard costs nothing.

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- client
```

Expected: FAIL — cannot resolve `../client`.

- [ ] **Step 3: Write `src/data/client.ts`**

```ts
import { createClient } from '@supabase/supabase-js';
import type { SupabaseClient } from '@supabase/supabase-js';

export interface ClientConfig {
  readonly url: string;
  readonly anonKey: string;
}

function decodeRole(jwt: string): string | null {
  const payload = jwt.split('.')[1];
  if (!payload) return null;
  try {
    // atob, not Buffer: this module ships inside the React Native bundle, where
    // Node globals do not exist.
    const decode = globalThis.atob;
    if (typeof decode !== 'function') return null;
    const json = JSON.parse(decode(payload.replace(/-/g, '+').replace(/_/g, '/')));
    return typeof json.role === 'string' ? json.role : null;
  } catch {
    return null;
  }
}

export function createMorningGlowClient(config: ClientConfig): SupabaseClient {
  if (!config.url) throw new Error('SUPABASE_URL is missing');
  if (!config.anonKey) throw new Error('SUPABASE_ANON_KEY is missing');

  // A service_role key bypasses RLS. In a mobile bundle that is a full
  // disclosure of every user's health data, so refuse it outright.
  if (decodeRole(config.anonKey) === 'service_role') {
    throw new Error('Refusing to start: a service_role key must never reach the client');
  }

  return createClient(config.url, config.anonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });
}
```

- [ ] **Step 4: Run and commit**

```bash
npm test -- client && npm run typecheck
git add src/data/client.ts src/data/__tests__/client.test.ts
git commit -m "feat(data): Supabase client with a service-role guard"
```

Expected: 4 tests pass.

---

## Task 12: Profile repository

**Files:**
- Create: `src/data/profileRepo.ts`
- Test: `tests/db/profileRepo.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { Client } from 'pg';
import { randomUUID } from 'node:crypto';
import { rowToHealthProfile, healthProfileToRow } from '../../src/data/profileRepo';
import { EMPTY_PROFILE } from '../../src/core/index';
import 'dotenv/config';

let db: Client;
const USER = randomUUID();

beforeAll(async () => {
  db = new Client({ connectionString: process.env.SUPABASE_TEST_DB_URL });
  await db.connect();
  await db.query(
    `insert into auth.users (id, email, instance_id, aud, role)
     values ($1, $2, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated')`,
    [USER, `${USER}@test.local`],
  );
  await db.query(`insert into public.profiles (id) values ($1)`, [USER]);
  await db.query(
    `insert into public.consents (user_id, kind, version) values ($1, 'health_data', 'v1')`,
    [USER],
  );
});

afterAll(async () => {
  await db.query(`delete from auth.users where id = $1`, [USER]);
  await db.end();
});

describe('profile row mapping', () => {
  it('round-trips a full profile through the database', async () => {
    const profile = {
      ...EMPTY_PROFILE,
      onboardingComplete: true,
      phase: 'peri' as const,
      hrtStatus: 'no' as const,
      fitnessLevel: 'gentle' as const,
      budgetMin: 15 as const,
      wakeWindow: '06:00 – 07:00',
      preferences: ['breathing', 'movement'] as const,
      restrictions: ['knees'] as const,
      symptoms: { sleep: 3 as const },
    };

    const row = healthProfileToRow(USER, profile);
    const cols = Object.keys(row);
    await db.query(
      `insert into public.health_profile (${cols.join(',')})
       values (${cols.map((_, i) => `$${i + 1}`).join(',')})`,
      Object.values(row),
    );

    const { rows } = await db.query(
      `select * from public.health_profile where user_id = $1`, [USER],
    );
    const back = rowToHealthProfile(rows[0]);

    expect(back.phase).toBe('peri');
    expect(back.budgetMin).toBe(15);
    expect(back.preferences).toEqual(['breathing', 'movement']);
    expect(back.restrictions).toEqual(['knees']);
  });

  it('keeps "not asked" distinct from "nothing applies"', async () => {
    expect(rowToHealthProfile({ restrictions: null }).restrictions).toBeNull();
    expect(rowToHealthProfile({ restrictions: [] }).restrictions).toEqual([]);
  });

  it('does not put symptoms on the health_profile row', () => {
    // Symptoms are history and live in symptom_assessments, not here.
    expect(Object.keys(healthProfileToRow(USER, EMPTY_PROFILE))).not.toContain('symptoms');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm run test:db -- profileRepo
```

Expected: FAIL — cannot resolve `profileRepo`.

- [ ] **Step 3: Write `src/data/profileRepo.ts`**

```ts
import type { SupabaseClient } from '@supabase/supabase-js';
import { EMPTY_PROFILE } from '../core/index';
import type { HealthProfile } from '../core/index';

/** Shape of a `public.health_profile` row. */
export interface HealthProfileRow {
  user_id?: string;
  phase?: string | null;
  hrt_status?: string | null;
  fitness_level?: string | null;
  budget_min?: number | null;
  wake_window?: string | null;
  preferences?: string[] | null;
  restrictions?: string[] | null;
}

export function healthProfileToRow(
  userId: string,
  profile: HealthProfile,
): Required<Pick<HealthProfileRow, 'user_id'>> & HealthProfileRow {
  return {
    user_id: userId,
    phase: profile.phase,
    hrt_status: profile.hrtStatus,
    fitness_level: profile.fitnessLevel,
    budget_min: profile.budgetMin,
    wake_window: profile.wakeWindow,
    preferences: [...profile.preferences],
    // null and [] mean different things and must survive the round trip.
    restrictions: profile.restrictions === null ? null : [...profile.restrictions],
  };
}

export function rowToHealthProfile(row: HealthProfileRow): HealthProfile {
  return {
    ...EMPTY_PROFILE,
    phase: (row.phase ?? null) as HealthProfile['phase'],
    hrtStatus: (row.hrt_status ?? null) as HealthProfile['hrtStatus'],
    fitnessLevel: (row.fitness_level ?? null) as HealthProfile['fitnessLevel'],
    budgetMin: (row.budget_min ?? null) as HealthProfile['budgetMin'],
    wakeWindow: row.wake_window ?? null,
    preferences: (row.preferences ?? []) as HealthProfile['preferences'],
    restrictions: (row.restrictions ?? null) as HealthProfile['restrictions'],
  };
}

export async function loadHealthProfile(
  client: SupabaseClient,
  userId: string,
): Promise<HealthProfile | null> {
  const { data, error } = await client
    .from('health_profile')
    .select('*')
    .eq('user_id', userId)
    .maybeSingle();

  if (error) throw error;
  return data ? rowToHealthProfile(data) : null;
}

export async function saveHealthProfile(
  client: SupabaseClient,
  userId: string,
  profile: HealthProfile,
): Promise<void> {
  const { error } = await client
    .from('health_profile')
    .upsert(healthProfileToRow(userId, profile), { onConflict: 'user_id' });

  if (error) throw error;
}
```

Note what is absent: `onboardingComplete` is not a health field. It lives on `profiles.onboarding_completed_at`, so the routing decision survives a health-data erasure.

- [ ] **Step 4: Run and commit**

```bash
npm run test:db -- profileRepo && npm run typecheck
git add src/data/profileRepo.ts tests/db/profileRepo.test.ts
git commit -m "feat(data): health profile repository with lossless round trip"
```

Expected: 3 tests pass.

---

## Task 13: Daily repository

**Files:**
- Create: `src/data/dailyRepo.ts`
- Test: `tests/db/dailyRepo.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { localDateOf, completionsToStreakInput } from '../../src/data/dailyRepo';

describe('localDateOf', () => {
  it('formats a date as YYYY-MM-DD in the given zone', () => {
    // 06:00 in Berlin on 29 Aug is 04:00 UTC — still the 29th.
    expect(localDateOf(new Date('2026-08-29T04:00:00Z'), 'Europe/Berlin')).toBe('2026-08-29');
  });

  it('assigns an early morning to the local day, not the UTC one', () => {
    // 00:30 on 30 Aug in Berlin is 22:30 on the 29th UTC.
    expect(localDateOf(new Date('2026-08-29T22:30:00Z'), 'Europe/Berlin')).toBe('2026-08-30');
  });

  it('handles a zone ahead of UTC', () => {
    expect(localDateOf(new Date('2026-08-29T20:00:00Z'), 'Pacific/Auckland')).toBe('2026-08-30');
  });
});

describe('completionsToStreakInput', () => {
  it('extracts the local dates, newest first', () => {
    expect(completionsToStreakInput([
      { local_date: '2026-08-27' },
      { local_date: '2026-08-29' },
    ])).toEqual(['2026-08-29', '2026-08-27']);
  });

  it('returns an empty list for no completions', () => {
    expect(completionsToStreakInput([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- dailyRepo
```

Expected: FAIL — cannot resolve `dailyRepo`.

- [ ] **Step 3: Write `src/data/dailyRepo.ts`**

```ts
import type { SupabaseClient } from '@supabase/supabase-js';
import type { DailyCheckin } from '../core/index';

/**
 * The local calendar date for an instant, in the user's own zone.
 *
 * Everything daily is keyed on this rather than on a UTC date: a woman doing
 * her routine at 06:00 in Auckland is a full day ahead of UTC, and grouping
 * her mornings by the server's day would silently break her streak.
 */
export function localDateOf(instant: Date, timeZone: string): string {
  // en-CA formats as YYYY-MM-DD, which is exactly the shape we store.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(instant);
}

export interface CompletionRow {
  readonly local_date: string;
}

export function completionsToStreakInput(rows: readonly CompletionRow[]): string[] {
  return rows.map((r) => r.local_date).sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));
}

export async function saveCheckin(
  client: SupabaseClient,
  userId: string,
  localDate: string,
  checkin: DailyCheckin,
): Promise<void> {
  const { error } = await client.from('daily_checkins').upsert(
    { user_id: userId, local_date: localDate, mood: checkin.mood, energy: checkin.energy },
    { onConflict: 'user_id,local_date' },
  );
  if (error) throw error;
}

export async function saveCompletion(
  client: SupabaseClient,
  userId: string,
  localDate: string,
  completedSteps: readonly string[],
  durationSec: number,
): Promise<void> {
  const { error } = await client.from('ritual_completions').upsert(
    {
      user_id: userId,
      local_date: localDate,
      completed_steps: completedSteps,
      duration_sec: durationSec,
    },
    { onConflict: 'user_id,local_date' },
  );
  if (error) throw error;
}

export async function loadCompletionDates(
  client: SupabaseClient,
  userId: string,
  sinceLocalDate: string,
): Promise<string[]> {
  const { data, error } = await client
    .from('ritual_completions')
    .select('local_date')
    .eq('user_id', userId)
    .gte('local_date', sinceLocalDate);

  if (error) throw error;
  return completionsToStreakInput(data ?? []);
}
```

- [ ] **Step 4: Run and commit**

```bash
npm test -- dailyRepo && npm run typecheck
git add src/data/dailyRepo.ts tests/db/dailyRepo.test.ts
git commit -m "feat(data): daily repository keyed on the user's local date"
```

Expected: 5 tests pass.

---

## Task 14: Content repository and exercise reconciliation

The exercise catalog exists in two places after Etappe 1: `src/core/exercises.ts` (which the engine needs synchronously) and `public.exercises` (which carries media paths and the physiotherapist sign-off). They must not drift.

**Files:**
- Create: `src/data/contentRepo.ts`
- Create: `supabase/seed/exercises.sql`
- Test: `tests/db/contentRepo.test.ts`

- [ ] **Step 1: Write the seed from the core catalog**

`supabase/seed/exercises.sql`:

```sql
-- Seeded from src/core/exercises.ts. The engine reads the core catalog; this
-- table adds media paths and the review sign-off. Task 14's test proves the
-- two stay in step.
insert into public.exercises
  (id, level, name, dose, description, duration_sec, video_path, photo_path, contraindications)
values
  ('catcow',      'gentle',   'Katze-Kuh-Stretch',          'mobilisierend', 'Wirbelsäule mobilisieren', 60, 'exercises/catcow.mp4',   'exercises/catcow.jpg',   '{knees}'),
  ('sidebend',    'gentle',   'Sanfte Seitneige',           'dehnend',       'Flanken öffnen',           45, 'exercises/sidebend.mp4', 'exercises/sidebend.jpg', '{}'),
  ('twist',       'gentle',   'Stehende Drehung',           'lösend',        'Rumpf sanft rotieren',     45, null,                     'exercises/twist.jpg',    '{back}'),
  ('fold',        'gentle',   'Stehende Vorbeuge',          'lösend',        'Rücken & Beinrückseite',   60, 'exercises/fold.mp4',     'exercises/fold.jpg',     '{back}'),
  ('tree',        'gentle',   'Baum (Balance)',             'zentrierend',   'Gleichgewicht & Fokus',    60, 'exercises/tree.mp4',     'exercises/tree.jpg',     '{balance}'),
  ('sunlight',    'moderate', 'Sonnengruß light',           'fließend',      'Ganzkörper aktivieren',    60, null, null, '{back,shoulders}'),
  ('wallpush',    'moderate', 'Wandstützen',                '2×10 Wdh',      'Sanfte Armkraft',          45, null, null, '{shoulders}'),
  ('bridge',      'moderate', 'Brücke',                     '2×12 Wdh',      'Po & unterer Rücken',      60, null, null, '{back}'),
  ('lunge',       'moderate', 'Hüftöffner Ausfallschritt',  'je Seite',      'Mobilität',                60, null, null, '{knees,balance}'),
  ('boxbreath',   'moderate', 'Box-Atmung',                 'fokussiert',    'Fokus setzen',             60, null, null, '{}'),
  ('squat-chair', 'moderate', 'Stuhl-Squats',               '2×12 Wdh',      'Beine sanft kräftigen',    45, null, null, '{knees}'),
  ('jacks',       'active',   'Jumping Jacks',              'Warm-up',       'Kreislauf hochfahren',     45, null, null, '{knees,balance}'),
  ('pushup',      'active',   'Push-ups',                   '3×12 Wdh',      'Oberkörperkraft',          60, null, null, '{shoulders}'),
  ('squat',       'active',   'Kniebeuge',                  '3×15 Wdh',      'Beinpower',                60, null, null, '{knees}'),
  ('plank',       'active',   'Plank',                      '3×30 Sek',      'Core-Stabilität',          45, null, null, '{shoulders,back}'),
  ('hipcircle',   'active',   'Dynamischer Hüftkreis',      'Cool-down',     'Mobilität lösen',          45, null, null, '{balance}'),
  ('pigeon',      'active',   'Pigeon Pose',                'je Seite',      'Tiefes Dehnen',            90, null, null, '{knees}')
on conflict (id) do update set
  level = excluded.level,
  name = excluded.name,
  dose = excluded.dose,
  description = excluded.description,
  duration_sec = excluded.duration_sec,
  video_path = excluded.video_path,
  photo_path = excluded.photo_path,
  contraindications = excluded.contraindications;
```

- [ ] **Step 2: Write the drift test**

`tests/db/contentRepo.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { Client } from 'pg';
import { readFileSync } from 'node:fs';
import { EXERCISES } from '../../src/core/index';
import 'dotenv/config';

let db: Client;

beforeAll(async () => {
  db = new Client({ connectionString: process.env.SUPABASE_TEST_DB_URL });
  await db.connect();
  await db.query(readFileSync('supabase/seed/exercises.sql', 'utf8'));
});

afterAll(async () => { await db.end(); });

describe('exercise catalog consistency', () => {
  it('holds exactly the exercises the engine knows', async () => {
    const { rows } = await db.query(`select id from public.exercises order by id`);
    expect(rows.map((r) => r.id)).toEqual([...EXERCISES].map((e) => e.id).sort());
  });

  it('agrees with the engine on every contraindication', async () => {
    const { rows } = await db.query(`select id, contraindications from public.exercises`);
    for (const row of rows) {
      const engine = EXERCISES.find((e) => e.id === row.id);
      expect(engine).toBeDefined();
      expect([...row.contraindications].sort())
        .toEqual([...engine!.contraindications].sort());
    }
  });

  it('agrees with the engine on which exercises have video', async () => {
    const { rows } = await db.query(
      `select id from public.exercises where video_path is not null order by id`,
    );
    const engineVideo = EXERCISES.filter((e) => e.media === 'video').map((e) => e.id).sort();
    expect(rows.map((r) => r.id)).toEqual(engineVideo);
  });

  it('has no exercise cleared for release without a review', async () => {
    const { rows } = await db.query(
      `select count(*)::int as n from public.exercises
       where reviewed_at is not null and reviewed_by is null`,
    );
    expect(rows[0].n).toBe(0);
  });
});
```

The second test is the safety one: if someone loosens a contraindication in the database but not in the engine, the routine builder would still hand out an exercise the woman said she cannot do. This test fails the build instead.

- [ ] **Step 3: Run to verify it fails**

```bash
npm run test:db -- contentRepo
```

Expected: FAIL — table empty or seed not applied.

- [ ] **Step 4: Write `src/data/contentRepo.ts`**

```ts
import type { SupabaseClient } from '@supabase/supabase-js';

export interface ArticleSummary {
  readonly slug: string;
  readonly category: string;
  readonly title: string;
  readonly subtitle: string | null;
  readonly readMin: number;
}

export interface Article extends ArticleSummary {
  readonly body: readonly unknown[];
}

export async function listArticles(
  client: SupabaseClient,
  locale = 'de',
): Promise<ArticleSummary[]> {
  const { data, error } = await client
    .from('articles')
    .select('slug, category, title, subtitle, read_min')
    .eq('locale', locale)
    .not('published_at', 'is', null)
    .order('category');

  if (error) throw error;
  return (data ?? []).map((r) => ({
    slug: r.slug, category: r.category, title: r.title,
    subtitle: r.subtitle, readMin: r.read_min,
  }));
}

export async function loadArticle(
  client: SupabaseClient,
  slug: string,
  locale = 'de',
): Promise<Article | null> {
  const { data, error } = await client
    .from('articles')
    .select('slug, category, title, subtitle, read_min, body')
    .eq('slug', slug).eq('locale', locale)
    .not('published_at', 'is', null)
    .maybeSingle();

  if (error) throw error;
  if (!data) return null;
  return {
    slug: data.slug, category: data.category, title: data.title,
    subtitle: data.subtitle, readMin: data.read_min,
    body: Array.isArray(data.body) ? data.body : [],
  };
}

/** Media paths for the exercises the engine selected, keyed by exercise id. */
export async function loadExerciseMedia(
  client: SupabaseClient,
  ids: readonly string[],
): Promise<Record<string, { video: string | null; photo: string | null }>> {
  if (ids.length === 0) return {};

  const { data, error } = await client
    .from('exercises')
    .select('id, video_path, photo_path')
    .in('id', [...ids]);

  if (error) throw error;

  const media: Record<string, { video: string | null; photo: string | null }> = {};
  for (const row of data ?? []) {
    media[row.id] = { video: row.video_path, photo: row.photo_path };
  }
  return media;
}
```

- [ ] **Step 5: Run and commit**

```bash
npm run test:db -- contentRepo && npm run typecheck
git add src/data/contentRepo.ts supabase/seed/exercises.sql tests/db/contentRepo.test.ts
git commit -m "feat(data): content repository and engine/database catalog drift test"
```

Expected: 4 tests pass.

---

## Task 15: Schema documentation

**Files:**
- Create: `supabase/README.md`

- [ ] **Step 1: Write it**

````markdown
# Database

Supabase, EU region (Frankfurt). Health data must not leave the EU.

## Applying migrations

```bash
npx supabase db push
npm run test:db
```

Migrations are numbered and never edited once applied. The next free number is
0009.

## Layout

| Table | Art. 9 data | Notes |
|---|---|---|
| `profiles` | no | Account. Survives a health-data erasure. |
| `consents` | no | `health_data` consent is separate and revocable alone. |
| `health_profile` | yes | Full concept model, including v2 fields. |
| `symptom_assessments` | yes | Insert-only. No update policy exists. |
| `daily_checkins` | yes | One per `(user, local_date)`. |
| `ritual_completions` | yes | One per `(user, local_date)`. Upserted. |
| `routine_overrides` | yes | Manual step removals and additions. |
| `exercise_feedback` | yes | Written in v1, read by v2. |
| `articles`, `exercises` | no | Service-role write, authenticated read. |

## Rules that live in the database, not in app code

- Writing to `health_profile` and `symptom_assessments` requires a live
  `health_data` consent — enforced in the RLS policy, so no client path skips it.
- An article cannot be published without `reviewed_by` and `reviewed_at`.
- `erase_health_data()` runs as `security invoker`, so it can only ever erase
  the caller's own rows.

## What is deliberately absent

- **No streak column.** The streak is computed from `ritual_completions` by
  `computeStreak` in `src/core/streak.ts`. A stored counter drifts after an
  offline period, a timezone change or a repeated sync.
- **No module catalog table.** It is fused with the engine and lives in
  `src/core/catalog.ts`. Editing it through an admin screen would mean editing
  the engine.
- **No `local_date` derived on the server.** The client supplies it, because the
  day belongs to the user's timezone.

## Open review items

- `exercises.contraindications` needs physiotherapist sign-off before release.
  Set `reviewed_by` and `reviewed_at` when that happens.
- Articles ship unreviewed until a doctor signs them off; the
  `published_needs_review` constraint keeps them out of the app until then.
````

- [ ] **Step 2: Commit**

```bash
git add supabase/README.md
git commit -m "docs(db): schema layout, enforced rules and deliberate omissions"
```

---

## Definition of done

- [ ] `npm run test:db` passes — every table has a policy test proving one user cannot reach another's rows
- [ ] `npm test` still passes (core suite unaffected)
- [ ] `npm run typecheck` clean
- [ ] Every migration 0001–0008 applied to the EU project
- [ ] `grep -rn "service_role" src/` returns nothing outside `client.ts`'s guard
- [ ] Health-data erasure verified end to end: account and terms consent survive, health rows do not
