# Hunter country presets — design spec

**Date:** 2026-04-08
**Owner:** Bill (orchestrator), implementation by Forge
**Touches:** `agents/market-research/stages/hunter.md`, `agents/market-research/lead/skill.md`, new `agents/market-research/presets/`, new `agents/market-research/data/`
**Status:** draft, awaiting user review

## Problem

Hunter (stage 1 of the Mira market-research pipeline) currently runs the same generic Tavily → Firecrawl flow for every topic regardless of country. For Ukrainian market research this loses three things at once:

1. **Authoritative domain priors.** There is a well-defined set of Ukrainian state sources (customs.gov.ua, ukrstat.gov.ua, bank.gov.ua, prozorro.gov.ua, me.gov.ua, data.gov.ua) plus the global `trademap.org` that every Ukrainian topic should hit. Hunter has no way to express "these domains are pre-trusted for this country."
2. **Product-code targeting.** Ukrainian customs statistics are queried by УКТ ЗЕД codes (e.g. `3916 20 00 10` for PVC window profiles), production by КВЕД (`22.23`), procurement by ДК 021:2015 (`44221000-5`), and trademap by HS codes (`391620`). These classifiers are essential for structured-data sources but have nowhere to live in the current topic schema.
3. **Gated structured sources.** `customs.gov.ua/cabinet`, `trademap.org`, and parts of ProZorro BI require login. No ready adapter library exists for them. Hunter today either skips them or returns unusable portal pages instead of actual numbers.

The source catalog at `agents/inbox/team/Sources UA research.md` lays out exactly what's needed for a monthly PVC-profile report; we want that knowledge encoded so every Ukrainian topic benefits, not re-pasted into each topic YAML.

## Goals

- Give Hunter country-aware behaviour via a single **preset file per country** (`presets/ua.yaml` first; `presets/pl.yaml`, `presets/de.yaml` follow the same shape later).
- Make user-supplied manual downloads (customs XLS, trademap exports) **first-class inputs** that Hunter sees before any web call.
- Fail fast with a **human-readable reminder** when required downloads are missing, so the user is prompted once per run and the pipeline halts cleanly until files appear.
- Pull structured JSON from the three public APIs that don't need auth (NBU, ProZorro public API, data.gov.ua CKAN) using Hunter's existing Firecrawl tool — no new tools, no new code.
- Let Hunter accumulate a **learned sources list** without corrupting the hand-curated preset.

## Non-goals

- Automating login-gated sources (trademap, customs cabinet). Manual download into a drop folder is the intentional pattern — browser-automation fragility and credential handling are out of scope.
- Building per-source Python adapters. If Firecrawl stops working against a JSON endpoint, the fallback is giving Hunter the `WebFetch` tool; no adapter layer.
- Changing Sift/Audit/Sage/Quill/Hawk stage contracts. This spec is Hunter- and Mira-only.
- Multi-language query generation heuristics beyond what `language_hints` already drives.

## Architecture

Five pieces, Hunter as orchestrator, preset as single source of truth for country-specific knowledge:

```
topic.yaml (geography: ua, time_focus: 2026-03, research_blocks: [...])
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  Hunter                                                      │
│  0.  Load preset ua.yaml + ua.learned.yaml                   │
│  0b. Pre-flight ── scan data/ua/<source>/<YYYY-MM>/          │
│                    compare vs preset.manual_downloads        │
│                    ├─ all present → continue                 │
│                    └─ missing     → return needs_data, exit  │
│  1b. Register drop-folder files as src-*** (confidence:high) │
│  2.  Decompose queries from preset.query_templates           │
│  3.  Tavily discovery, boost preset.authoritative_domains    │
│  3b. Fetch api_sources via Firecrawl (NBU, ProZorro, CKAN)   │
│  4.  Firecrawl fetch of best Tavily URLs                     │
│  5.  Build remaining source records                          │
│  6b. Append new authoritative domains → ua.learned.yaml      │
│  7.  Write 01-sources.json                                   │
│  8.  Return to Mira                                          │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
  Mira skill (lead/skill.md) receives Hunter return
       ├─ status: ok          → advance to Sift
       ├─ status: needs_data  → HALT, emit checklist to caller,
       │                        write run-log `awaiting_manual_data`
       └─ status: error       → existing error handling
```

**Control flow notes.** Mira is a skill, not a standing agent, so the halt/resume cycle is in-session: Hunter returns `needs_data` → Mira skill emits the checklist to its caller (Bill) → Bill relays to the user → user downloads files → user says "resume" → Bill re-invokes Mira's resume entry point → Mira re-dispatches Hunter from stage 1 → pre-flight re-runs. Manual files are load-bearing (halt on missing); API sources are non-blocking (log and continue on failure).

## Preset schema — `presets/ua.yaml`

```yaml
country: ua
display_name: Ukraine
language_hints: [uk, en]

# Domains that auto-qualify for initial_confidence: high and get kept
# regardless of Tavily ranking position.
authoritative_domains:
  - customs.gov.ua
  - ukrstat.gov.ua
  - stat.gov.ua
  - bank.gov.ua
  - prozorro.gov.ua
  - bi.prozorro.org
  - me.gov.ua
  - kmu.gov.ua
  - rada.gov.ua
  - data.gov.ua
  - trademap.org

# Classification tables, nested by system. Research_blocks reference
# entries via codes_ref: "ukt_zed.pvc_window_profiles".
product_codes:
  ukt_zed:
    pvc_window_profiles:
      - { code: "3916 20 00 10", desc: "Профілі з ПВХ для вікон/дверей" }
      - { code: "3916 20 00 90", desc: "Інші профілі з ПВХ" }
      - { code: "3925 20 00 00", desc: "Двері, коробки та пороги з пластмас" }
      - { code: "3926 90 92 00", desc: "Комплектуючі / фурнітура" }
  hs:
    pvc_window_profiles: ["391620"]
  kved:
    pvc_manufacturing: ["22.23", "22.29"]
  dk_021:
    windows_doors: ["44221000-5", "44210000-5"]

# Pre-flight checklist, keyed by research_block. Each entry is a file
# that MUST be in the drop folder before Hunter will proceed.
manual_downloads:
  market_size:
    - source: "ДМС митна статистика ЗЕД"
      url: "https://cabinet.customs.gov.ua"
      codes_ref: "ukt_zed.pvc_window_profiles"
      time_granularity: monthly
      expected_filename_pattern: "customs_zed_.*_{YYYY-MM}\\.xlsx"
      destination: "data/ua/customs/{YYYY-MM}/"
      download_hint: |
        Log into cabinet.customs.gov.ua → Статистика ЗЕД →
        фільтр за кодами УКТ ЗЕД 3916 20, імпорт, період = звітний місяць →
        експорт XLSX.

    - source: "Trade Map (ITC)"
      url: "https://www.trademap.org"
      codes_ref: "hs.pvc_window_profiles"
      time_granularity: monthly
      expected_filename_pattern: "trademap_hs391620_ua_{YYYY-MM}\\.xlsx"
      destination: "data/ua/trademap/{YYYY-MM}/"
      download_hint: |
        Log in → Trade statistics → Bilateral trade → Reporter: Ukraine →
        Product: HS 391620 → Time series by partner → Export XLSX.

  procurement:
    - source: "ProZorro BI"
      url: "https://bi.prozorro.org"
      codes_ref: "dk_021.windows_doors"
      time_granularity: monthly
      expected_filename_pattern: "prozorro_.*_{YYYY-MM}\\.xlsx"
      destination: "data/ua/prozorro/{YYYY-MM}/"
      download_hint: |
        bi.prozorro.org → пошук за ДК 021:2015 код 44221000-5 →
        фільтр за місяцем → експорт XLSX.

# Public JSON endpoints — no auth. Hunter scrapes these via Firecrawl.
# Non-blocking: failures are logged but do not halt the run.
api_sources:
  - name: nbu_exchange_rate_month_end
    url_template: "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={YYYYMMDD_end}&json"
    research_block: macro
    description: "НБУ офіційний курс валют на кінець місяця"

  - name: nbu_policy_rate
    url_template: "https://bank.gov.ua/NBUStatService/v1/statdirectory/discountrt?json"
    research_block: macro
    description: "Облікова ставка НБУ (весь ряд)"

  - name: prozorro_tenders_by_cpv
    url_template: "https://public.api.openprocurement.org/api/2.5/tenders?offset={YYYY-MM-DD_start}"
    research_block: procurement
    description: "ProZorro публічний API — перелік тендерів від початку місяця"

  - name: ckan_construction_prices
    url_template: "https://data.gov.ua/api/3/action/package_search?q=ціни+будівництво&rows=20"
    research_block: construction_demand
    description: "data.gov.ua CKAN — датасети з індексами цін у будівництві"

# Tavily query templates, rendered with {product}, {year}, {month_name_uk}
# placeholders drawn from topic.yaml.
query_templates:
  market_size:
    - "{product} імпорт Україна {year} тонн митниця"
    - "{product} ринок України {year} обсяг"
    - "{product} Ukraine import statistics {year}"
  production:
    - "виробництво {product} Україна КВЕД 22.23 {year}"
    - "Держстат промислове виробництво пластмасових виробів {year}"
  construction_demand:
    - "Держстат індекс будівельної продукції {year}"
    - "обсяг виконаних будівельних робіт Україна {year}"
    - "введення в експлуатацію житла Україна {year}"
  pricing:
    - "ціна {product} Україна {year}"
    - "S-PVC European spot price {year}"
  regulation:
    - "антидемпінгове розслідування пластмаси Україна {year}"
    - "ввізне мито 3916 Україна {year}"
```

### Template variable reference

| Variable | Source | Example |
|---|---|---|
| `{YYYY-MM}` | `topic.time_focus` | `2026-03` |
| `{YYYYMMDD_end}` | last day of `time_focus` month | `20260331` |
| `{YYYY-MM-DD_start}` | first day of `time_focus` month | `2026-03-01` |
| `{year}` | year from `time_focus` | `2026` |
| `{product}` | `topic.products[0].display_name` | `ПВХ профілі` |
| `{codes}` | resolved list from `codes_ref`, joined by `-` | `391620001-39162000902` |

## Drop folder layout

```
agents/market-research/data/
├── .gitignore
└── ua/
    ├── customs/
    │   └── 2026-03/
    │       └── customs_zed_391620_2026-03.xlsx
    ├── trademap/
    │   └── 2026-03/
    │       └── trademap_hs391620_ua_2026-03.xlsx
    ├── prozorro/
    │   └── 2026-03/
    │       └── prozorro_44221000-5_2026-03.xlsx
    └── ukrstat/
        └── 2026-03/
            └── (reserved for manual Ukrstat XLS if ever needed)
```

`.gitignore` content (lives at `agents/market-research/data/.gitignore`, so patterns are relative to that directory — `country/source/YYYY-MM/file.ext`):

```
# Raw research data files are not committed, but folder structure is.
*/*/*/*.xlsx
*/*/*/*.csv
*/*/*/*.pdf
*/*/*/*.zip
!.gitkeep
```

Each country/source/month leaf directory gets a `.gitkeep` so the path exists even before the first download.

## Hunter workflow changes (`stages/hunter.md`)

Diff-level summary; full edit applied during implementation.

### New Step 0 — Preset load and pre-flight

Inserted before existing "Read the topic YAML":

> **0. Load preset and pre-flight.** If a file exists at `presets/<topic.geography>.yaml`:
>
> a. Load it and merge with `presets/<topic.geography>.learned.yaml` if present. Hand-curated entries win on conflict.
>
> b. Compute the manual-download checklist by iterating `preset.manual_downloads` for each block in `topic.research_blocks`. For each entry, substitute `{YYYY-MM}` from `topic.time_focus` in both `destination` and `expected_filename_pattern`.
>
> c. For each required entry, glob the destination directory. If no filename matches the pattern (regex), mark the entry as missing.
>
> d. If any entry is missing, return:
> ```json
> {
>   "status": "needs_data",
>   "topic_id": "<topic.topic_id>",
>   "time_focus": "<topic.time_focus>",
>   "missing": [
>     {
>       "source": "ДМС митна статистика ЗЕД",
>       "destination": "agents/market-research/data/ua/customs/2026-03/",
>       "expected_filename_pattern": "customs_zed_.*_2026-03.xlsx",
>       "download_hint": "Log into cabinet.customs.gov.ua ..."
>     }
>   ]
> }
> ```
> Do **not** write `01-sources.json`. Do **not** run any Tavily/Firecrawl calls. Exit.

### New Step 1b — Drop-folder registration

Inserted immediately after "Read the topic YAML" and **before** any query generation or web fetching, so manual-download records get the lowest `src-NNN` IDs and Sift sees them first.

> **1b. Register drop-folder files.** Scan the topic's drop folder (`agents/market-research/data/<geography>/*/{YYYY-MM}/*`). For each file found, register a source record with sequential `src-001`, `src-002`, ...:
> - `url`: `file:///absolute/path/to/file.xlsx`
> - `source_title`: the matching `preset.manual_downloads[].source` label (inferred from the subfolder name, e.g. `customs/` → "ДМС митна статистика ЗЕД")
> - `research_block`: the block under which the entry was declared in the preset
> - `initial_confidence`: `high`
> - `key_fact`: `"Manual download: <filename> — <source label>. To be parsed by Sift."`
> - `date`: `topic.time_focus + "-01"` (first of the month)

### Existing Step 2 — Decompose queries (modified)

> If a preset was loaded in step 0, use `preset.query_templates` instead of ad-hoc decomposition. Render each template with `{product}`/`{year}` from the topic. Generate queries only for `research_blocks` that are in scope (all blocks on first run, `gaps` subset on retries).

### Existing Step 3 — Tavily discovery (modified)

> Any hit whose domain is in `preset.authoritative_domains` is kept regardless of ranking position and is tagged with `initial_confidence: high` automatically. Non-preset hits follow existing junk-filtering rules.

### New Step 3b — API sources

> For each entry in `preset.api_sources` whose `research_block` is in the current scope set, render `url_template` against `topic.time_focus`, call `mcp__firecrawl__scrape` on the rendered URL, and register the result as a source record with:
> - `id`: next sequential `src-NNN`
> - `url`: rendered URL
> - `source_title`: `preset.api_sources[].description`
> - `research_block`: `preset.api_sources[].research_block`
> - `initial_confidence`: `high`
> - `key_fact`: first 200 chars of the scraped JSON body
>
> API fetches are **non-blocking**. On any failure (HTTP error, empty body, scrape timeout), log `{"skipped": "<name>", "reason": "<short>"}` to the run log and continue. Do not fail the run.

### Existing Step 6 — Target counts (unchanged)

### New Step 6b — Learned sources append

> For each authoritative-looking domain Hunter encountered during Tavily discovery that is *not* already in `preset.authoritative_domains`, append or bump-count in `presets/<geography>.learned.yaml`:
> ```yaml
> learned_sources:
>   - domain: "buildportal.com.ua"
>     first_seen: "2026-04-08"
>     last_seen: "2026-04-08"
>     topics: ["pvc-windows-doors-profiles-ukraine"]
>     research_blocks: ["market_size"]
>     seen_count: 1
> ```
> Rules: append-only; deduplicate by `domain`; on re-hit, bump `seen_count`, update `last_seen`, union `topics` and `research_blocks`. Never delete, never rewrite existing entries. Never touch the hand-curated `ua.yaml`.

### Tool surface

Hunter's `tools:` frontmatter stays exactly as it is today. The new steps use only `Read`, `Write`, `Glob`, `mcp__firecrawl__scrape`, `mcp__tavily__search`, `mcp__firecrawl__search` — all already listed.

## Mira skill changes (`lead/skill.md`)

### New Hunter-return branch

After dispatching Hunter, inspect the status:

- `ok` → existing behaviour (advance to Sift).
- `error` → existing behaviour.
- **`needs_data`** (new):
  1. Write the current run's `_run-log.json` with:
     ```json
     {
       "status": "awaiting_manual_data",
       "halted_at_stage": "hunter",
       "halted_at": "<ISO-8601 timestamp>",
       "missing": [ ... from Hunter's return ... ]
     }
     ```
  2. Return a human-readable message to the caller in this exact shape:
     ```
     [Mira] Pre-flight halted for <topic_id> (time_focus: <time_focus>).

     The following files must be placed in the drop folder before research can continue:

     1. <source label>
        → <destination path>
        Filename pattern: <expected_filename_pattern>
        How to get it: <download_hint>

     2. ...

     Once all files are in place, ask Bill to "resume <topic_id>" and the pipeline
     will re-dispatch Hunter from stage 1. Pre-flight will re-run and either proceed
     or return a shorter checklist.
     ```
  3. Do not advance to Sift. Do not retry. Return control to the caller.

### New `resume` entry point

The Mira skill gains a top-level `resume <topic_id>` action:

1. Look up the topic's most recent run directory under `reports/<topic_id>/<time_focus>/`.
2. Read `_run-log.json`. If `status != awaiting_manual_data`, return an error ("nothing to resume").
3. Otherwise, re-dispatch Hunter with the same topic YAML. Hunter's pre-flight will re-run. If it now passes, the pipeline proceeds to Sift normally. If it still returns `needs_data`, Mira re-emits the shorter checklist.

## Security, safety, and boundaries

- **No credentials are stored anywhere in the repo.** Gated sources are only ever accessed manually by the user; Hunter never sees a password.
- **Drop folder files never get committed.** The `.gitignore` rules above are load-bearing — customs and trademap data may carry redistribution restrictions.
- **Hunter cannot modify `presets/ua.yaml`.** Only `presets/ua.learned.yaml`. Implementation should enforce this in the step 6b code path (explicit target filename, never the hand-curated one).
- **Firecrawl against public JSON APIs is not scraping in the ToS sense** for the three endpoints listed (NBU, ProZorro public, data.gov.ua CKAN) — all three are explicit public APIs. Still worth naming so it doesn't get conflated with, say, Ukrstat HTML scraping which we intentionally avoid.

## Testing plan

This is a doc/skill change, so "testing" means end-to-end dry-runs, not unit tests:

1. **Pre-flight miss** — run Mira on the existing `pvc-windows-doors-profiles-ukraine` topic with an **empty** drop folder. Expect: `needs_data` halt, checklist printed, no Tavily calls made, run-log has `awaiting_manual_data`.
2. **Pre-flight partial** — place one of the three required files (e.g. only customs). Re-run. Expect: shorter checklist listing just trademap + prozorro.
3. **Pre-flight pass** — place all three files. Re-run. Expect: Hunter advances through steps 1–6, `01-sources.json` contains file:// records for the three manual files plus API-source records plus Tavily/Firecrawl records, pipeline proceeds to Sift.
4. **API failure tolerance** — temporarily break one `url_template` (typo). Re-run. Expect: Hunter logs the skip and continues; `01-sources.json` is written; pipeline proceeds.
5. **Learning loop** — confirm that on a run where Tavily surfaces a new domain (e.g. `buildportal.com.ua`), `presets/ua.learned.yaml` is created or appended, and `presets/ua.yaml` is byte-identical before and after.
6. **Resume entry point** — trigger a `needs_data` halt, place files, invoke `resume pvc-windows-doors-profiles-ukraine`, confirm the same run directory is reused (not a new `-r2` directory) and pipeline proceeds.

## Out of scope / explicit non-goals

- Automating login to trademap / customs cabinet (browser automation, session replay, credential vaults).
- Building Python adapter scripts for NBU/ProZorro/CKAN. URL templates + Firecrawl is deliberately the entire implementation.
- Editing Sift to parse XLS/PDF contents — Sift already handles schema-driven extraction; if it needs a helper for XLSX, that's a separate spec.
- Multi-country pre-flight in a single run. Each topic has one `geography`; there is no cross-country join.
- Auto-promotion of `learned_sources` into `authoritative_domains`. User reviews and promotes manually. (A future helper slash-command is possible but not in this spec.)

## Open questions

None as of 2026-04-08. All design decisions are committed.
