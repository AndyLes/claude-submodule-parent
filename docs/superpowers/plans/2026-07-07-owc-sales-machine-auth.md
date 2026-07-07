# OWC Sales Machine — Minimal Auth Implementation Plan (Plan 1.5)

> **For agentic workers:** implement task-by-task, TDD where noted. Checkbox (`- [ ]`) steps.

**Goal:** Add a single-account email/password login so authenticated sessions satisfy the RLS policies (`to authenticated`), making the pipeline board and deal pages actually read/write data in the browser. Protect all `(app)` routes; leave `/login` public.

**Why:** Plan 1 shipped RLS granted to role `authenticated`, but no login flow. The server components use the anon-key cookie client; with no session the role is `anon`, so RLS returns empty and server actions fail. This plan closes that gap.

**Architecture:** Canonical `@supabase/ssr` middleware refreshes the session cookie on every request and redirects unauthenticated users to `/login`. A client login page calls `signInWithPassword`. An `(app)` layout adds a sign-out control. The single admin user is created via the service-role Admin API (one-shot script, then deleted).

**Tech Stack:** Next.js 15 middleware, `@supabase/ssr`, existing `src/lib/supabase/{server,client}.ts`.

**Depends on:** Plan 1 (spine) complete; `.env.local` populated; migration `0001_spine.sql` applied.

---

## Task A1: Session middleware + route protection

**Files:**
- Create: `src/lib/supabase/middleware.ts`
- Create: `src/middleware.ts`

- [ ] **Step 1: `src/lib/supabase/middleware.ts`**

```ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Public paths that do NOT require a session.
const PUBLIC_PATHS = ["/login"];

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // IMPORTANT: getUser() revalidates the token with the auth server (secure).
  const { data: { user } } = await supabase.auth.getUser();

  const path = request.nextUrl.pathname;
  const isPublic = PUBLIC_PATHS.some((p) => path === p || path.startsWith(p + "/"));

  if (!user && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // Signed-in user hitting /login → send to the board.
  if (user && path === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/pipeline";
    return NextResponse.redirect(url);
  }

  return response;
}
```

- [ ] **Step 2: `src/middleware.ts`**

```ts
import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  // Run on everything except Next internals and static asset files.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
```

- [ ] **Step 3: Verify compilation**

Run: `npx tsc --noEmit` → no errors. `npm run build` → succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/lib/supabase/middleware.ts src/middleware.ts
git commit -m "feat(auth): session middleware + protect (app) routes"
```

---

## Task A2: Login page

**Files:**
- Create: `src/app/login/page.tsx`

- [ ] **Step 1: `src/app/login/page.tsx`**

```tsx
"use client";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { getBrowserSupabase } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, start] = useTransition();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    start(async () => {
      const supabase = getBrowserSupabase();
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
        toast.error(error.message);
        return;
      }
      router.push("/pipeline");
      router.refresh();
    });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">OWC Sales Machine</h1>
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="Email" className="w-full rounded border p-2 text-sm"
        />
        <input
          type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="Пароль" className="w-full rounded border p-2 text-sm"
        />
        <button
          type="submit" disabled={pending}
          className="w-full rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          {pending ? "Вхід…" : "Увійти"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Verify + commit**

Run: `npx tsc --noEmit` → clean. Then:
```bash
git add src/app/login/page.tsx
git commit -m "feat(auth): email/password login page"
```

---

## Task A3: (app) layout with sign-out

**Files:**
- Create: `src/lib/auth/actions.ts`
- Create: `src/components/auth/SignOutButton.tsx`
- Create: `src/app/(app)/layout.tsx`

- [ ] **Step 1: `src/lib/auth/actions.ts`**

```ts
"use server";
import { redirect } from "next/navigation";
import { getServerSupabase } from "@/lib/supabase/server";

export async function signOut() {
  const supabase = await getServerSupabase();
  await supabase.auth.signOut();
  redirect("/login");
}
```

- [ ] **Step 2: `src/components/auth/SignOutButton.tsx`**

```tsx
"use client";
import { useTransition } from "react";
import { signOut } from "@/lib/auth/actions";

export function SignOutButton() {
  const [pending, start] = useTransition();
  return (
    <button
      onClick={() => start(() => signOut())}
      disabled={pending}
      className="text-sm text-slate-500 hover:text-slate-800 disabled:opacity-50"
    >
      Вийти
    </button>
  );
}
```

- [ ] **Step 3: `src/app/(app)/layout.tsx`**

```tsx
import Link from "next/link";
import { SignOutButton } from "@/components/auth/SignOutButton";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <Link href="/pipeline" className="text-sm font-semibold text-slate-900">
          OWC Sales Machine
        </Link>
        <SignOutButton />
      </header>
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Verify + commit**

Run: `npx tsc --noEmit` → clean. `npm run build` → succeeds. Then:
```bash
git add src/lib/auth/actions.ts src/components/auth/SignOutButton.tsx "src/app/(app)/layout.tsx"
git commit -m "feat(auth): app shell with sign-out"
```

---

## Task A4: Create the single admin user (one-shot)

**Files:**
- Create then DELETE: `create_admin.mjs` (never committed)

- [ ] **Step 1: Write `create_admin.mjs`**

```js
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { createClient } from "@supabase/supabase-js";

const env = Object.fromEntries(
  readFileSync(new URL("./.env.local", import.meta.url), "utf8")
    .split(/\r?\n/).filter((l) => l.includes("="))
    .map((l) => { const i = l.indexOf("="); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; }),
);

const db = createClient(env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

const email = "andriy.leso@gmail.com";
const password = randomBytes(12).toString("base64url"); // temp password

const { data, error } = await db.auth.admin.createUser({
  email, password, email_confirm: true,
});
if (error) { console.error("CREATE USER FAILED:", error.message); process.exit(1); }
console.log("ADMIN USER CREATED");
console.log("email:   ", email);
console.log("password:", password);
console.log("(temporary — change it after first login)");
```

- [ ] **Step 2: Run it, capture the printed credentials, then delete the script**

Run: `node create_admin.mjs` → prints email + temp password. Save the password to report to the user. Then `rm create_admin.mjs`.
If the user already exists, that's fine — report "user already exists" and move on (the user can reset the password in the dashboard).

- [ ] **Step 3: Confirm no script left behind**

Run: `git status --short` → must NOT list `create_admin.mjs`.

---

## Verification (live, no dev server)

A one-shot node script proves the RLS boundary end-to-end:
- **anon** client `select` on `deals` → returns 0 rows / blocked (RLS denies).
- **authenticated** client (`signInWithPassword` with the admin creds) `select` on `deals` → succeeds (RLS allows).

The controller runs this after implementation; the browser UI check (`npm run dev` → log in → board) is the user's to run.

## Self-review checklist
- Login is outside `(app)` so it isn't behind the app layout / redirect loop.
- Middleware allows `/login`, redirects signed-in users away from it, protects everything else.
- Matcher excludes static assets so they load pre-auth.
- `getUser()` (not `getSession()`) used in middleware for token revalidation.
- Service-role key used ONLY in the one-shot node script (server/local), never imported into any browser component.
