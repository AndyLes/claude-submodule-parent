# offwhite.city → Next.js on Vercel + SEO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move offwhite.city off Lovable hosting onto Vercel as a server-rendered Next.js app against the existing Supabase project, so every URL ships its own crawlable HTML, and fix the SEO defects the SPA made impossible.

**Architecture:** In-place migration of `AndyLes/offwhite-city-7a3471eb` on a branch. The Vite SPA shell (react-router + react-helmet-async + prebuild sitemap script) is replaced by the Next.js App Router; every presentational component, the i18n dictionaries, the Supabase lead-form logic and the Tailwind tokens port over essentially unchanged. German stays unprefixed at the route root, `/en` and `/uk` become a `[lang]` segment, all 21 URLs are statically generated. Supabase (`lxznpjbdmeytglzvsjsd`) is untouched — only the env-var names change from `VITE_*` to `NEXT_PUBLIC_*`. Lovable is disconnected; the GitHub repo becomes an ordinary repo Vercel builds on push.

**Tech Stack:** Next.js 15 (App Router, React 18), TypeScript, Tailwind 3 + shadcn/ui (13 used primitives), Supabase JS v2 (browser client + 3 existing edge functions), Vitest + Testing Library, Playwright (parity screenshots), Vercel, Google Cloud DNS.

---

## Status — 2026-09-15

Done in this session, on branch `next-migration` (pushed):

- Tasks 1-12: the port is complete. `npx next build` prerenders all 21 URLs as static HTML; `npx vitest run` is 9/9 green.
- Extra, found during the port and not in the original plan: every section wrapped its
  children in `{isVisible && (...)}`, so the served HTML carried the hero and the footer and
  nothing else. Children now always render and the IntersectionObserver only swaps the
  animation class. Crawlable words: home 324 -> 1547, /software 279 -> 1729, /fenster 279 -> 979.
- Visual parity verified by pixel diff of all 21 routes against the Lovable baseline: identical
  page heights, 0.0% difference everywhere except /fenster at 0.4%, which is next/image
  re-encoding the same photograph.
- Task 13: Vercel project `offwhite-city` (team smartglassplatform) linked, both
  `NEXT_PUBLIC_SUPABASE_*` vars set in all three environments and verified by `vercel env pull`,
  first deployment live at `offwhite-city-fcpnaqzrm-smartglassplatform.vercel.app`.

Blocked on the owner:

- Deployment Protection needs no action: the project is set to `all_except_custom_domains`, so the
  `*.vercel.app` URL asks for a Vercel login but `offwhite.city` will be public once it points here.
  To view the deployment now, open it in a browser signed in to Vercel.
- Task 13 Step 5 (submit a real lead through the deployment) — needs the Supabase dashboard open.
- Task 12 Step 5 (disconnect Lovable), Task 14 (DNS), Task 15 (Search Console / Bing).
- The branch is not merged to `main` on purpose: Lovable still has push rights to `main`.

---

## Current state (verified 2026-09-15)

| Fact | Value |
|---|---|
| Live host | Lovable — `offwhite.city` A → `185.158.133.1`, `x-deployment-id` header, Cloudflare in front |
| DNS | Google Cloud DNS, `ns-cloud-d1..d4.googledomains.com` |
| `www.offwhite.city` | 302 today — must keep redirecting after cutover |
| Supabase | `https://lxznpjbdmeytglzvsjsd.supabase.co`, owner's own account, 10 migrations, 3 edge functions (`send-request-email`, `send-guide-email`, `get-request-by-token`) |
| Routes | 7 pages × 3 languages = 21 URLs (`/`, `/software`, `/fenster`, `/impressum`, `/datenschutz`, `/agb`, `/qualify`; plus `/en/*`, `/uk/*`) |
| App code | ~3.9k LOC (components 1377, pages 865, i18n 1352, hooks/lib 341) + 13 used shadcn primitives |
| Analytics | GA4 `G-WT28BYVDVT` inline in `index.html`; `google-site-verification` meta `8pWJ0HEKfFFJwbtge3pOyTx1GsYM9e1SIHERLt2QWDQ` |

### SEO defects the migration must fix

1. **All 21 URLs serve the identical `index.html`** with the home-page title. Titles, descriptions and canonicals appear only after React hydrates.
2. **No `<link rel="canonical">` and no `hreflang` in the server response** — the three language versions have nothing tying them together, so they compete as duplicates.
3. **`og:image` points at a Lovable preview screenshot** on `pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev` — an R2 URL that dies with the Lovable project.
4. **`public/llms.txt` is stale** — still sells "B2B-Großhandel für Fenstersysteme, Minimalbestellung 30 Einheiten" and links `/de/...` paths that do not exist (German is unprefixed).
5. **No structured data anywhere** — no Organization, no WebSite, no service markup.
6. **Dead debug blocks** sit commented out in `src/components/LeadForm.tsx:119-124,146-149` (`alert("3 before invoke")` and friends). They never reach users — they are inside `/* */` — but they get deleted while porting the component in Task 4.
7. `robots.txt` lists per-bot `Allow: /` blocks that do nothing, and the sitemap comes from a prebuild script that will not exist after the port.

---

## File structure after migration

```
app/
  layout.tsx                 root <html lang="de">, GA4, providers, JSON-LD
  globals.css                ← src/index.css verbatim
  page.tsx                   DE home
  software|fenster|impressum|datenschutz|agb|qualify/page.tsx
  not-found.tsx              404, noindex
  sitemap.ts                 replaces scripts/generate-sitemap.ts
  robots.ts                  replaces public/robots.txt
  opengraph-image.tsx        default OG card (next/og)
  [lang]/
    layout.tsx               validates lang ∈ {en,uk}
    page.tsx + the same six sub-routes
src/
  views/**                   language-agnostic page bodies (from src/pages/)
  components/**              ported verbatim, "use client" where hooks are used
  i18n/**                    unchanged dictionaries; I18nContext becomes client
  hooks/** lib/**            unchanged
  integrations/supabase/**   client reads NEXT_PUBLIC_* env
  seo/routes.ts              single source of truth: page keys, paths, languages
  seo/meta.ts                the META table lifted out of components/Seo.tsx
  seo/metadata.ts            generateMetadata builder
  seo/jsonld.ts              Organization / WebSite / WebPage builders
```

Deleted at Task 12: `src/components/Seo.tsx`, `src/App.tsx`, `src/main.tsx`, `src/pages/**`, `scripts/generate-sitemap.ts`, `index.html`, `vite.config.ts`, `public/robots.txt`, `public/sitemap.xml`, `bun.lock*`.

---

## Task 1: Baseline capture

**Files:** Create `tools/baseline/capture.mjs`, `tools/baseline/titles.txt`, `tools/baseline/*.png`

- [ ] **Step 1: Record what every live URL returns today**

```bash
cd /c/SuperWork/projects/owc-lovable && mkdir -p tools/baseline && for p in "" /software /fenster /impressum /datenschutz /agb /qualify /en /en/software /uk /uk/software; do echo "== $p"; curl -sS "https://offwhite.city$p" | grep -oE '<title>[^<]*</title>' | head -1; done | tee tools/baseline/titles.txt
```

Expected: the same `Software für Fenster-, Tür- und Glashersteller | offwhite.city` for all of them — the before-picture of the defect.

- [ ] **Step 2: Screenshot every route on production**

Sections render only when scroll-revealed (`useScrollReveal`, threshold 0.15), so the script scrolls top→bottom before shooting, and launches with `channel: 'chrome'` (no browser download).

```js
// tools/baseline/capture.mjs
import { chromium } from "@playwright/test";
const ROUTES = ["", "/software", "/fenster", "/impressum", "/datenschutz", "/agb", "/qualify"];
const LANGS = ["", "/en", "/uk"];
const base = process.argv[2] ?? "https://offwhite.city";
const out = process.argv[3] ?? "tools/baseline";
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
for (const l of LANGS) for (const r of ROUTES) {
  await page.goto(`${base}${l}${r}`, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(400);
  const name = `${l || "/de"}${r}`.replace(/\//g, "_");
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
}
await browser.close();
```

```bash
cd /c/SuperWork/projects/owc-lovable && node tools/baseline/capture.mjs https://offwhite.city tools/baseline
```

Expected: 21 PNGs in `tools/baseline/`.

- [ ] **Step 3: Branch and commit the baseline**

```bash
cd /c/SuperWork/projects/owc-lovable && git checkout -b next-migration && git add tools/baseline && git commit -m "chore: capture pre-migration baseline of all 21 routes"
```

---

## Task 2: Next.js scaffolding alongside the Vite app

Both build systems coexist on the branch until Task 12, so the port can be compared side by side.

**Files:** Modify `package.json`, `tsconfig.json`, `tailwind.config.ts`; create `next.config.ts`, `app/layout.tsx`, `app/globals.css`

- [ ] **Step 1: Install Next, drop the Vite/Lovable toolchain**

```bash
cd /c/SuperWork/projects/owc-lovable && npm install next@15 && npm uninstall vite @vitejs/plugin-react-swc lovable-tagger react-helmet-async react-router-dom
```

`npm ci` fails on this repo — always `npm install`. `bun.lock` was the project lockfile; after migration `package-lock.json` is what Vercel uses, so it gets committed and `bun.lock*` are deleted in Task 12.

- [ ] **Step 2: Rewrite the scripts block**

```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
```

- [ ] **Step 3: `next.config.ts`**

```ts
import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  images: { formats: ["image/avif", "image/webp"] },
  async redirects() {
    return [
      // German is unprefixed — /de/* was never a real route but llms.txt advertised it
      { source: "/de", destination: "/", permanent: true },
      { source: "/de/:path*", destination: "/:path*", permanent: true },
    ];
  },
};

export default config;
```

- [ ] **Step 4: Global stylesheet**

```bash
cd /c/SuperWork/projects/owc-lovable && mkdir -p app && cp src/index.css app/globals.css
```

- [ ] **Step 5: Tailwind must scan `app/`**

In `tailwind.config.ts` the `content` array gains `"./app/**/*.{ts,tsx}"` alongside the existing `"./src/**/*.{ts,tsx}"`.

- [ ] **Step 6: Root layout**

```tsx
// app/layout.tsx
import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import Providers from "@/components/Providers";

export const metadata: Metadata = {
  metadataBase: new URL("https://offwhite.city"),
  authors: [{ name: "offwhite.city" }],
  verification: { google: "8pWJ0HEKfFFJwbtge3pOyTx1GsYM9e1SIHERLt2QWDQ" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <Providers>{children}</Providers>
        <Script src="https://www.googletagmanager.com/gtag/js?id=G-WT28BYVDVT" strategy="afterInteractive" />
        <Script id="ga4" strategy="afterInteractive">{`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-WT28BYVDVT');
        `}</Script>
      </body>
    </html>
  );
}
```

- [ ] **Step 7: `tsconfig.json`**

Keep the `@/*` → `./src/*` alias, add `"plugins": [{ "name": "next" }]`, `"jsx": "preserve"`, and include `.next/types/**/*.ts`. Running `npx next dev` once writes the rest itself and creates `next-env.d.ts`.

- [ ] **Step 8: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "chore(next): scaffold App Router alongside the Vite app"
```

---

## Task 3: Providers and the i18n client boundary

**Files:** Create `src/components/Providers.tsx`; modify `src/i18n/I18nContext.tsx`

- [ ] **Step 1: `Providers.tsx` — the client island that used to be `App.tsx`**

```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        {children}
      </TooltipProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 2: Mark the i18n context as client**

Add `"use client";` as the first line of `src/i18n/I18nContext.tsx`. Nothing else changes — the `t()` lookup and `langPrefix` logic stay as they are.

- [ ] **Step 3: Verify the dev server boots**

```bash
cd /c/SuperWork/projects/owc-lovable && npx next dev --port 3100
```

Expected: `Ready in …`, and a 404 at `/` (no pages yet). Kill it after checking.

- [ ] **Step 4: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "feat(next): client providers and i18n boundary"
```

---

## Task 4: Port the components

Mechanical. The rules below are exhaustive — no component needs redesigning.

**Files:** Modify everything under `src/components/`, `src/hooks/`, `src/integrations/`

- [ ] **Step 1: Add `"use client";` to every component using a hook, state, an event handler or a browser API**

That is all of `src/components/*.tsx`, all of `src/components/software/*.tsx` and the 13 used `src/components/ui/*` primitives. Find them:

```bash
cd /c/SuperWork/projects/owc-lovable && grep -rlE "useState|useEffect|useRef|onClick|onChange|onSubmit|useI18n|useScrollReveal|window\.|document\." src/components src/hooks
```

- [ ] **Step 2: Swap the router for `next/link`**

| Vite / react-router | Next |
|---|---|
| `import { Link } from "react-router-dom"` | `import Link from "next/link"` |
| `<Link to={x}>` | `<Link href={x}>` |
| `useSearchParams` from react-router | `useSearchParams` from `next/navigation` (same `.get()` API) |

```bash
cd /c/SuperWork/projects/owc-lovable && grep -rn "react-router-dom" src/ | cat
```

Expected after the sweep: no hits.

- [ ] **Step 3: Rewrite `src/components/NavLink.tsx` on `next/link`**

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

interface NavLinkProps extends React.ComponentPropsWithoutRef<typeof Link> {
  activeClassName?: string;
}

export const NavLink = forwardRef<HTMLAnchorElement, NavLinkProps>(
  ({ className, activeClassName, href, ...props }, ref) => {
    const pathname = usePathname();
    const isActive = pathname === href.toString();
    return <Link ref={ref} href={href} className={cn(className, isActive && activeClassName)} {...props} />;
  },
);
NavLink.displayName = "NavLink";
```

- [ ] **Step 4: Move the five imported images to `public/`**

```bash
cd /c/SuperWork/projects/owc-lovable && mkdir -p public/images && git mv src/assets/hero-building.jpg src/assets/homeowner-nrw-house.jpg src/assets/case-study-1.jpg src/assets/case-study-2.jpg src/assets/case-study-3.jpg public/images/ && grep -rn "@/assets" src/ | cat
```

Every hit becomes a `next/image` with `src="/images/<name>.jpg"`, explicit `width`/`height`, and the alt text that is already in the current markup — carry it over, do not invent new copy. The hero image gets `priority`.

- [ ] **Step 5: Supabase client reads Next env vars**

```ts
// src/integrations/supabase/client.ts
import { createClient } from "@supabase/supabase-js";
import type { Database } from "./types";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;

export const supabase = createClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true },
});
```

`storage: localStorage` is dropped — it evaluates at module load and there is no `localStorage` on the server; `persistSession` already defaults to `localStorage` in the browser.

`src/pages/Qualify.tsx` also hard-codes the project URL twice (`https://lxznpjbdmeytglzvsjsd.supabase.co/functions/v1/...`). Replace both with `${process.env.NEXT_PUBLIC_SUPABASE_URL}/functions/v1/...` while porting it in Task 7.

- [ ] **Step 6: Local env file**

```bash
cd /c/SuperWork/projects/owc-lovable && { echo "NEXT_PUBLIC_SUPABASE_URL=https://lxznpjbdmeytglzvsjsd.supabase.co"; echo -n "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="; grep VITE_SUPABASE_PUBLISHABLE_KEY .env | cut -d'"' -f2; } > .env.local; grep -q ".env.local" .gitignore || echo ".env.local" >> .gitignore
```

- [ ] **Step 7: Delete the dead debug blocks in `LeadForm.tsx`**

Two commented-out `/* alert("3 before invoke") … */` blocks around the `send-request-email` invoke (lines 119-124 and 146-149). They are inert, but they do not survive the port.

- [ ] **Step 7: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "refactor(next): port components to the App Router (next/link, next/image, env)"
```

---

## Task 5: The SEO route table

Everything downstream — metadata, sitemap, hreflang, JSON-LD — reads this one module, so the 21 URLs can never drift apart.

**Files:** Create `src/seo/routes.ts`, `src/seo/meta.ts`; test `src/seo/routes.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/seo/routes.test.ts
import { describe, expect, it } from "vitest";
import { ALL_URLS, LANGS, PAGES, hrefFor } from "./routes";

describe("seo routes", () => {
  it("covers every page in every language", () => {
    expect(ALL_URLS).toHaveLength(PAGES.length * LANGS.length);
    expect(new Set(ALL_URLS).size).toBe(ALL_URLS.length);
  });

  it("leaves German unprefixed and prefixes the rest", () => {
    expect(hrefFor("home", "de")).toBe("/");
    expect(hrefFor("home", "uk")).toBe("/uk");
    expect(hrefFor("software", "de")).toBe("/software");
    expect(hrefFor("software", "en")).toBe("/en/software");
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run src/seo/routes.test.ts
```

Expected: FAIL — `Failed to resolve import "./routes"`.

- [ ] **Step 3: Implement**

```ts
// src/seo/routes.ts
import type { Lang } from "@/i18n/translations";

export const SITE = "https://offwhite.city";
export const LANGS: Lang[] = ["de", "en", "uk"];
export const DEFAULT_LANG: Lang = "de";

export type PageKey = "home" | "software" | "fenster" | "impressum" | "datenschutz" | "agb" | "qualify";

export const PATHS: Record<PageKey, string> = {
  home: "",
  software: "/software",
  fenster: "/fenster",
  impressum: "/impressum",
  datenschutz: "/datenschutz",
  agb: "/agb",
  qualify: "/qualify",
};

export const PAGES = Object.keys(PATHS) as PageKey[];

export const hrefFor = (page: PageKey, lang: Lang): string => {
  const prefix = lang === DEFAULT_LANG ? "" : `/${lang}`;
  return `${prefix}${PATHS[page]}` || "/";
};

export const urlFor = (page: PageKey, lang: Lang): string => `${SITE}${hrefFor(page, lang)}`;

/** hreflang map for one page: every language plus x-default pointing at German. */
export const alternatesFor = (page: PageKey): Record<string, string> => ({
  ...Object.fromEntries(LANGS.map((l) => [l, urlFor(page, l)])),
  "x-default": urlFor(page, DEFAULT_LANG),
});

export const ALL_URLS = PAGES.flatMap((p) => LANGS.map((l) => urlFor(p, l)));
```

- [ ] **Step 4: Run the test again**

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run src/seo/routes.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Lift the META table out of the doomed `Seo.tsx`**

Move the `META` constant from `src/components/Seo.tsx` verbatim into `src/seo/meta.ts`, together with the `fromCopy()` helper that reads titles from `softwareTranslations` — the copy stays the single source of truth. Export one accessor:

```ts
// src/seo/meta.ts (tail — the META literal above it is copied unchanged)
import type { Lang } from "@/i18n/translations";
import type { PageKey } from "./routes";

export const metaFor = (page: PageKey, lang: Lang) => META[page][lang] ?? META[page].de;
```

- [ ] **Step 6: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "feat(seo): single route/meta table for all 21 URLs"
```

---

## Task 6: Shared `generateMetadata` builder

This is the fix for defects 1, 2 and 3.

**Files:** Create `src/seo/metadata.ts`; test `src/seo/metadata.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/seo/metadata.test.ts
import { describe, expect, it } from "vitest";
import { buildMetadata } from "./metadata";

describe("buildMetadata", () => {
  it("sets a self-referencing canonical", () => {
    expect(buildMetadata("software", "uk").alternates?.canonical).toBe("https://offwhite.city/uk/software");
  });

  it("emits all three languages plus x-default", () => {
    const langs = buildMetadata("fenster", "de").alternates?.languages as Record<string, string>;
    expect(langs).toEqual({
      de: "https://offwhite.city/fenster",
      en: "https://offwhite.city/en/fenster",
      uk: "https://offwhite.city/uk/fenster",
      "x-default": "https://offwhite.city/fenster",
    });
  });

  it("uses the page's own title, not the home page's", () => {
    expect(buildMetadata("impressum", "de").title).toBe("Impressum | offwhite.city");
  });

  it("keeps the token-gated form out of the index", () => {
    expect(buildMetadata("qualify", "de").robots).toMatchObject({ index: false });
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run src/seo/metadata.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```ts
// src/seo/metadata.ts
import type { Metadata } from "next";
import type { Lang } from "@/i18n/translations";
import { metaFor } from "./meta";
import { alternatesFor, urlFor, type PageKey } from "./routes";

/** Token-gated, no search demand — crawlable, but not an index candidate. */
const NOINDEX: PageKey[] = ["qualify"];

const OG_LOCALE: Record<Lang, string> = { de: "de_DE", en: "en_US", uk: "uk_UA" };

export function buildMetadata(page: PageKey, lang: Lang): Metadata {
  const { title, description } = metaFor(page, lang);
  const url = urlFor(page, lang);

  return {
    title,
    description,
    alternates: { canonical: url, languages: alternatesFor(page) },
    robots: NOINDEX.includes(page)
      ? { index: false, follow: true }
      : { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 } },
    openGraph: {
      type: "website",
      siteName: "offwhite.city",
      url,
      title,
      description,
      locale: OG_LOCALE[lang],
      alternateLocale: Object.values(OG_LOCALE).filter((l) => l !== OG_LOCALE[lang]),
    },
    twitter: { card: "summary_large_image", title, description },
  };
}
```

No `og:image` here — `app/opengraph-image.tsx` (Task 10) supplies it for every route, which is what kills the dead R2 URL.

- [ ] **Step 4: Run the tests**

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run src/seo/metadata.test.ts
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "feat(seo): canonical + hreflang + OG metadata builder"
```

---

## Task 7: German routes

Each old page splits in two: the body becomes a language-agnostic **view** under `src/views/` taking `lang` as a prop, and the route file is a thin server component exporting metadata. Both language trees render the same view, so the JSX exists once.

**Files:** Create `app/page.tsx` + six sibling route files; create `src/views/{Home,Software,Fenster,Impressum,Datenschutz,Agb,Qualify}View.tsx`

- [ ] **Step 1: `src/pages/Index.tsx` → `src/views/HomeView.tsx`**

Copy it across, then drop the `useParams`/`useLocation` imports and the `Index` wrapper, drop the `<Seo …/>` element (metadata is the route's job now), change `<Link to=…>` to `<Link href=…>`, and take `lang` from props:

```tsx
// src/views/HomeView.tsx
"use client";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { I18nProvider, useI18n } from "@/i18n/I18nContext";
import type { Lang } from "@/i18n/translations";
import Navbar from "@/components/Navbar";
import SoftwareHero from "@/components/software/SoftwareHero";
import IntroSection from "@/components/software/IntroSection";
import CapabilitiesSection from "@/components/software/CapabilitiesSection";
import KeyValueSection from "@/components/software/KeyValueSection";
import EngagementSection from "@/components/software/EngagementSection";
import ExpertiseSection from "@/components/software/ExpertiseSection";
import PracticeProof from "@/components/software/PracticeProof";
import LeadForm from "@/components/LeadForm";
import SeoSection from "@/components/SeoSection";
import Footer from "@/components/Footer";

const HomeContent = () => {
  const { t, langPrefix } = useI18n();
  const modules = [1, 2, 3, 4, 5, 6].map((n) => ({ k: t(`sw.mod.${n}.k`), v: t(`sw.mod.${n}.v`) }));

  return (
    <div className="min-h-screen">
      <Navbar />
      <SoftwareHero />
      <IntroSection />
      <CapabilitiesSection />
      <KeyValueSection label={t("sw.mod.label")} title={t("sw.mod.title")} sub={t("sw.mod.sub")} items={modules} columns={3} tone="card">
        <div className="text-center mt-10">
          <Link href={`${langPrefix}/software`} className="reveal-up inline-flex items-center gap-2 text-sm font-semibold text-foreground hover:text-accent transition-colors">
            {t("sw.mod.more")}
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </KeyValueSection>
      <EngagementSection />
      <ExpertiseSection />
      <PracticeProof />
      <LeadForm variant="software" />
      <SeoSection prefix="sw.seo" />
      <Footer />
    </div>
  );
};

export default function HomeView({ lang }: { lang: Lang }) {
  return (
    <I18nProvider lang={lang}>
      <HomeContent />
    </I18nProvider>
  );
}
```

The `useEffect` that scrolled to `location.hash` is dropped — the browser does that natively for a server-rendered anchor.

- [ ] **Step 2: Same treatment for the other six**

`Software.tsx → SoftwareView.tsx`, `Fenster.tsx → FensterView.tsx`, `Impressum.tsx → ImpressumView.tsx`, `Datenschutz.tsx → DatenschutzView.tsx`, `AGB.tsx → AgbView.tsx`, `Qualify.tsx → QualifyView.tsx`: `"use client"`, `lang` prop, `I18nProvider` wrapper, no `<Seo/>`, `href` instead of `to`.

`QualifyView` also swaps `useSearchParams` to the `next/navigation` one and uses `process.env.NEXT_PUBLIC_SUPABASE_URL` for both edge-function fetches (Task 4 Step 5).

- [ ] **Step 3: The German route files**

```tsx
// app/page.tsx
import type { Metadata } from "next";
import HomeView from "@/views/HomeView";
import { buildMetadata } from "@/seo/metadata";

export const metadata: Metadata = buildMetadata("home", "de");
export default function Page() { return <HomeView lang="de" />; }
```

The other five are the same three lines with the page key and view swapped. `app/qualify/page.tsx` must wrap the view, because `useSearchParams` opts a component out of static rendering unless it sits under a Suspense boundary:

```tsx
// app/qualify/page.tsx
import { Suspense } from "react";
import type { Metadata } from "next";
import QualifyView from "@/views/QualifyView";
import { buildMetadata } from "@/seo/metadata";

export const metadata: Metadata = buildMetadata("qualify", "de");
export default function Page() {
  return <Suspense fallback={null}><QualifyView lang="de" /></Suspense>;
}
```

- [ ] **Step 4: Verify the German tree renders server-side**

```bash
cd /c/SuperWork/projects/owc-lovable && npx next build && (npx next start --port 3100 &) && sleep 8 && curl -sS http://localhost:3100/software | grep -oE '<title>[^<]*</title>|rel="canonical" href="[^"]*"'
```

Expected: the `/software` title (not the home one) and `rel="canonical" href="https://offwhite.city/software"` **in the raw HTML**. Kill the server afterwards.

- [ ] **Step 5: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "feat(next): German route tree with server-rendered metadata"
```

---

## Task 8: `/en` and `/uk` routes

**Files:** Create `app/[lang]/layout.tsx` + seven `app/[lang]/**/page.tsx`; create `src/components/HtmlLang.tsx`

- [ ] **Step 1: The language layout, which also closes the door on bogus prefixes**

```tsx
// app/[lang]/layout.tsx
import { notFound } from "next/navigation";
import type { Lang } from "@/i18n/translations";
import HtmlLang from "@/components/HtmlLang";

const PREFIXED: Lang[] = ["en", "uk"];

export function generateStaticParams() {
  return PREFIXED.map((lang) => ({ lang }));
}

export default async function LangLayout({ children, params }: { children: React.ReactNode; params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!PREFIXED.includes(lang as Lang)) notFound();
  return <><HtmlLang lang={lang} />{children}</>;
}
```

`params` is a Promise in Next 15 — every route file below awaits it too. Anything that is not `en`/`uk` now 404s instead of silently rendering the German home page under a foreign URL, which is what the old `<Route path="/:lang">` did and what quietly manufactured duplicate content.

- [ ] **Step 2: The seven prefixed route files**

```tsx
// app/[lang]/page.tsx
import type { Metadata } from "next";
import HomeView from "@/views/HomeView";
import { buildMetadata } from "@/seo/metadata";
import type { Lang } from "@/i18n/translations";

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return buildMetadata("home", lang as Lang);
}

export default async function Page({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  return <HomeView lang={lang as Lang} />;
}
```

Repeat for `software`, `fenster`, `impressum`, `datenschutz`, `agb`, `qualify` (the last wrapped in `<Suspense>` exactly as in Task 7 Step 3).

- [ ] **Step 3: `<html lang>` must follow the page language**

The root layout hard-codes `lang="de"`; this corrects it on prefixed routes:

```tsx
// src/components/HtmlLang.tsx
"use client";
import { useEffect } from "react";
export default function HtmlLang({ lang }: { lang: string }) {
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  return null;
}
```

It fixes the DOM for users and assistive tech; the crawler-facing signal is the `hreflang` set from Task 6, which does not depend on it.

- [ ] **Step 4: Verify all 21 URLs build**

```bash
cd /c/SuperWork/projects/owc-lovable && npx next build 2>&1 | grep -E "○|●|λ|ƒ" | head -30
```

Expected: 21 static entries plus `/_not-found`.

- [ ] **Step 5: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "feat(next): /en and /uk route trees"
```

---

## Task 9: sitemap, robots, 404, llms.txt

**Files:** Create `app/sitemap.ts`, `app/robots.ts`, `app/not-found.tsx`; modify `public/llms.txt`; delete `public/sitemap.xml`, `public/robots.txt`, `scripts/generate-sitemap.ts`; test `src/seo/sitemap.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/seo/sitemap.test.ts
import { describe, expect, it } from "vitest";
import sitemap from "../../app/sitemap";

describe("sitemap", () => {
  it("lists the six indexable pages in three languages, with alternates", () => {
    const entries = sitemap();
    expect(entries).toHaveLength(18);
    const home = entries.find((e) => e.url === "https://offwhite.city/");
    expect(home?.alternates?.languages).toMatchObject({ uk: "https://offwhite.city/uk" });
  });

  it("does not advertise the noindexed qualify page", () => {
    expect(sitemap().some((e) => e.url.includes("/qualify"))).toBe(false);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run src/seo/sitemap.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the sitemap**

```ts
// app/sitemap.ts
import type { MetadataRoute } from "next";
import { LANGS, PAGES, alternatesFor, urlFor, type PageKey } from "@/seo/routes";

const PRIORITY: Record<string, number> = { home: 1.0, software: 0.9, fenster: 0.9, impressum: 0.3, datenschutz: 0.3, agb: 0.3 };
const SKIP: PageKey[] = ["qualify"];

export default function sitemap(): MetadataRoute.Sitemap {
  return PAGES.filter((p) => !SKIP.includes(p)).flatMap((page) =>
    LANGS.map((lang) => ({
      url: urlFor(page, lang),
      changeFrequency: (PRIORITY[page] >= 0.9 ? "weekly" : "monthly") as "weekly" | "monthly",
      priority: PRIORITY[page],
      alternates: { languages: alternatesFor(page) },
    })),
  );
}
```

- [ ] **Step 4: Implement robots**

```ts
// app/robots.ts
import type { MetadataRoute } from "next";
import { SITE } from "@/seo/routes";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/qualify"] }],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
```

The old per-bot `Allow: /` blocks are dropped: they granted nothing the wildcard did not already grant, and a named block silently cancels the wildcard rule for that bot — a footgun with no upside.

- [ ] **Step 5: 404 page**

```tsx
// app/not-found.tsx
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "404 | offwhite.city", robots: { index: false, follow: false } };

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-background">
      <h1 className="text-4xl font-bold text-foreground">404</h1>
      <p className="text-muted-foreground">Diese Seite existiert nicht.</p>
      <Link href="/" className="text-accent font-semibold hover:underline">offwhite.city</Link>
    </div>
  );
}
```

- [ ] **Step 6: Rewrite `public/llms.txt`**

It currently sells window wholesale and links non-existent `/de/*` paths. Replace the whole file with the software-first positioning and the real URLs — the same six indexable pages in three languages the sitemap lists, German unprefixed. Keep the terse `# heading` / `> summary` / `## Pages` shape. No prices and no client names (the owner's standing rule for this site).

- [ ] **Step 7: Delete what the App Router now owns**

```bash
cd /c/SuperWork/projects/owc-lovable && git rm public/sitemap.xml public/robots.txt scripts/generate-sitemap.ts
```

- [ ] **Step 8: Run the tests and commit**

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run && git add -A && git commit -m "feat(seo): generated sitemap with hreflang, robots, 404, fresh llms.txt"
```

---

## Task 10: Structured data and OG images

**Files:** Create `src/seo/jsonld.ts`, `src/components/JsonLd.tsx`, `app/opengraph-image.tsx`; modify `app/layout.tsx` and the route files

- [ ] **Step 1: The JSON-LD builders**

```ts
// src/seo/jsonld.ts
import type { Lang } from "@/i18n/translations";
import { SITE, urlFor, type PageKey } from "./routes";

export const organization = () => ({
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": `${SITE}/#organization`,
  name: "OffWhite.City UG",
  url: SITE,
  logo: `${SITE}/favicon.png`,
});

export const website = (lang: Lang) => ({
  "@context": "https://schema.org",
  "@type": "WebSite",
  "@id": `${SITE}/#website`,
  url: SITE,
  name: "offwhite.city",
  inLanguage: lang,
  publisher: { "@id": `${SITE}/#organization` },
});

export const webPage = (page: PageKey, lang: Lang, title: string, description: string) => ({
  "@context": "https://schema.org",
  "@type": "WebPage",
  "@id": `${urlFor(page, lang)}#webpage`,
  url: urlFor(page, lang),
  name: title,
  description,
  inLanguage: lang,
  isPartOf: { "@id": `${SITE}/#website` },
  about: { "@id": `${SITE}/#organization` },
});
```

The `Organization` block carries only facts already published on `/impressum` — legal name and site. Do not add a rating, a founding date, an address or a phone number that is not already on the page.

- [ ] **Step 2: The renderer**

```tsx
// src/components/JsonLd.tsx
export default function JsonLd({ data }: { data: object | object[] }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}
```

- [ ] **Step 3: Wire it in**

`app/layout.tsx` renders `<JsonLd data={[organization(), website("de")]} />` once. Each route file renders `<JsonLd data={webPage(page, lang, title, description)} />` next to its view, reading title/description from `metaFor()` so that text has exactly one source.

- [ ] **Step 4: Default OG image**

```tsx
// app/opengraph-image.tsx
import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "offwhite.city";

export default function Image() {
  return new ImageResponse(
    (
      <div style={{ height: "100%", width: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#f7f5f2", fontFamily: "sans-serif" }}>
        <div style={{ fontSize: 86, fontWeight: 700, color: "#1e2a3a", letterSpacing: "-0.03em" }}>offwhite.city</div>
        <div style={{ fontSize: 34, color: "#8a8a8a", marginTop: 18 }}>ERP · Digitaler Produktpass · Websites</div>
      </div>
    ),
    size,
  );
}
```

- [ ] **Step 5: Verify the dead R2 URL is gone**

```bash
cd /c/SuperWork/projects/owc-lovable && grep -rn "r2.dev\|lovable.app" app/ src/ public/ | cat
```

Expected: no hits.

- [ ] **Step 6: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "feat(seo): Organization/WebSite/WebPage JSON-LD and generated OG image"
```

---

## Task 11: Parity check against the baseline

**Files:** Create `tools/baseline/next/*.png`, `tools/baseline/compare.md`

- [ ] **Step 1: Shoot the same 21 routes against the local Next build**

```bash
cd /c/SuperWork/projects/owc-lovable && npx next build && (npx next start --port 3100 &) && sleep 8 && mkdir -p tools/baseline/next && node tools/baseline/capture.mjs http://localhost:3100 tools/baseline/next
```

- [ ] **Step 2: Compare each pair by eye**

Open the old and new PNG for each of the 21 routes side by side. Record a verdict per route in `tools/baseline/compare.md` (`same` / `fixed` / `regression`). Every `regression` is fixed before the task closes — this is the gate on "the site still looks the same".

- [ ] **Step 3: Confirm the head of every route, which is the whole point**

```bash
cd /c/SuperWork/projects/owc-lovable && for p in "" /software /fenster /impressum /datenschutz /agb /en /en/software /uk /uk/software /uk/agb; do echo "== $p"; curl -sS "http://localhost:3100$p" | grep -oE '<title>[^<]*</title>|rel="canonical" href="[^"]*"|hreflang="[^"]*"' | sort -u | head -8; done
```

Expected: a distinct title per page and language, a self-referencing canonical, and four `hreflang` values (`de`, `en`, `uk`, `x-default`) on every URL. Compare with `tools/baseline/titles.txt`, where all 21 were identical.

- [ ] **Step 4: Commit**

```bash
cd /c/SuperWork/projects/owc-lovable && git add -A && git commit -m "test: route parity and head verification against the pre-migration baseline"
```

---

## Task 12: Remove the Vite app and Lovable

**Files:** Delete `src/App.tsx`, `src/main.tsx`, `src/App.css`, `src/pages/**`, `src/components/Seo.tsx`, `index.html`, `vite.config.ts`, `bun.lock`, `bun.lockb`, `dist/`

- [ ] **Step 1: Delete the SPA shell**

```bash
cd /c/SuperWork/projects/owc-lovable && git rm -r src/App.tsx src/main.tsx src/App.css src/pages src/components/Seo.tsx index.html vite.config.ts bun.lock bun.lockb && rm -rf dist
```

- [ ] **Step 2: Keep Vitest running**

`vitest.config.ts` keeps its `jsdom` environment and `@` alias; drop any Vite React plugin import it carries. Then:

```bash
cd /c/SuperWork/projects/owc-lovable && npx vitest run
```

Expected: PASS — the `src/seo/*` tests plus `src/test/example.test.ts`.

- [ ] **Step 3: Confirm nothing references the dead toolchain**

```bash
cd /c/SuperWork/projects/owc-lovable && grep -rn "lovable\|react-helmet\|react-router" src/ app/ package.json | cat
```

Expected: no hits.

- [ ] **Step 4: Commit the lockfile Vercel will use**

```bash
cd /c/SuperWork/projects/owc-lovable && npm install && git add -A && git commit -m "chore: remove the Vite SPA shell and Lovable tooling"
```

- [ ] **Step 5: Disconnect Lovable (owner action, in the Lovable UI)**

Disconnect the GitHub repo in the Lovable project settings so Lovable can no longer push to `main`. Do this **before** the DNS cutover, so nothing overwrites the migrated `main` mid-flight.

---

## Task 13: Vercel project

- [ ] **Step 1: Link the repo**

```bash
cd /c/SuperWork/projects/owc-lovable && vercel link
```

Answer: existing scope, new project `offwhite-city`.

- [ ] **Step 2: Set the two env vars in all three environments**

Use `--value`, never stdin — piping the value mis-sets Preview/Production.

```bash
cd /c/SuperWork/projects/owc-lovable && for env in production preview development; do vercel env add NEXT_PUBLIC_SUPABASE_URL $env --value "https://lxznpjbdmeytglzvsjsd.supabase.co" --no-sensitive --force; done
```

Repeat for `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` with the anon key from `.env`, then verify by pulling:

```bash
cd /c/SuperWork/projects/owc-lovable && vercel env pull .env.vercel.check && grep -c NEXT_PUBLIC .env.vercel.check && rm .env.vercel.check
```

Expected: `2`.

- [ ] **Step 3: Preview deploy from the branch**

```bash
cd /c/SuperWork/projects/owc-lovable && vercel deploy
```

- [ ] **Step 4: Run the head check against the preview URL**

The Task 11 Step 3 loop with the preview host substituted. Expected: identical output — distinct titles, self-referencing canonicals, four hreflangs.

- [ ] **Step 5: Submit a real lead through the preview**

Fill the form on the preview URL with a test company, submit, then confirm in the Supabase dashboard that a row landed in `requests` and that `send-request-email` fired. Screenshots cannot verify this; nothing else in the plan covers it.

- [ ] **Step 6: Merge to main**

```bash
cd /c/SuperWork/projects/owc-lovable && git checkout main && git merge --no-ff next-migration -m "feat: migrate offwhite.city to Next.js on Vercel" && git push origin main
```

- [ ] **Step 7: Production deploy**

```bash
cd /c/SuperWork/projects/owc-lovable && vercel deploy --prod
```

Expected: a `*.vercel.app` production URL serving the site correctly, while `offwhite.city` still points at Lovable.

---

## Task 14: DNS cutover

Nothing here reverses in under a TTL, so it runs only after Task 13 Step 7 is verified green.

- [ ] **Step 1: Lower the TTL first, then wait**

In Google Cloud DNS, set the TTL on the `offwhite.city` A record and the `www` record to 300 s. Wait out the old TTL before touching the values.

- [ ] **Step 2: Add both domains in Vercel**

`offwhite.city` primary, `www.offwhite.city` redirecting to it — Vercel's own redirect, permanent (it 302s today, which is the weaker signal).

- [ ] **Step 3: Point the records at Vercel**

Apex `A` → `76.76.21.21`; `www` `CNAME` → `cname.vercel-dns.com`. Confirm the exact values in the Vercel domain panel before applying — Vercel does hand out different targets per project.

- [ ] **Step 4: Watch the switch land**

```bash
for i in 1 2 3 4 5 6; do curl -sSI https://offwhite.city/ | grep -iE "^(server|x-vercel-id|x-matched-path)"; sleep 30; done
```

Expected: `x-vercel-id` appears and the Lovable `x-deployment-id` header disappears.

- [ ] **Step 5: Verify HTTPS and the redirect**

```bash
curl -sSI https://www.offwhite.city/ | head -3; curl -sSI http://offwhite.city/ | head -3
```

Expected: `308`/`301` to `https://offwhite.city/` in both cases, valid certificate.

- [ ] **Step 6: Re-run the full head check against production**

The Task 11 Step 3 loop against `https://offwhite.city`. Expected: the same distinct titles, canonicals and hreflangs the preview produced.

---

## Task 15: Post-cutover SEO

- [ ] **Step 1: Search Console**

Confirm the property is still verified (the `google-site-verification` meta rides along in `app/layout.tsx`). Submit `https://offwhite.city/sitemap.xml`. Request indexing for `/`, `/software`, `/fenster` and their `/en` and `/uk` counterparts.

- [ ] **Step 2: Live rich-results and hreflang checks**

Rich Results Test on `/` and `/software` — expect `Organization` and `WebSite` detected, no errors. URL Inspection on `/uk/software` — confirm Google sees the Ukrainian title, not the German home one.

- [ ] **Step 3: Bing Webmaster Tools**

Add the site, verify, submit the same sitemap. Bing executes JavaScript poorly, so this is where the migration changes the most.

- [ ] **Step 4: GA4 still receiving**

Open the site, check GA4 Realtime for a hit on `G-WT28BYVDVT`. The tag moved from `index.html` to `next/script` — confirm it fires, including on a client-side route change.

- [ ] **Step 5: Core Web Vitals**

PageSpeed Insights on `/`, `/software`, `/fenster` (mobile). The hero image carrying `priority` and the AVIF/WebP formats from `next.config.ts` should improve LCP, not regress it.

- [ ] **Step 6: Do not let the old Lovable deployment linger**

Once production is verified, unpublish or delete the Lovable deployment so the old build cannot be served from a `*.lovable.app` URL that Google may already have indexed. Check Search Console for any such URL.

---

## Open questions for the owner

1. **`email-reply-handler`** — `src/pages/Qualify.tsx:106` calls a Supabase edge function by that name, but only `send-request-email`, `send-guide-email` and `get-request-by-token` exist under `supabase/functions/`. Either it lives only in the remote project (fine, nothing to do) or that submit path has been broken for a while. Confirm in the Supabase dashboard before Task 13 Step 5.
2. **`/qualify` noindex** — the plan keeps it crawlable but out of the index (token-gated form, no search demand). Say so if it should be indexable instead.
3. **Ukrainian and English demand** — the hreflang work makes the three versions legible to Google, but whether `/uk` and `/en` deserve their own keyword targeting is a content decision. A follow-up plan can cover it.
