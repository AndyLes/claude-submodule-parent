# Hunter country presets — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hunter country-aware via preset files, with a drop-folder pre-flight that halts the pipeline on missing manual downloads and a public-API fetch step for NBU / ProZorro / data.gov.ua — no new tools, no adapter code.

**Architecture:** One hand-curated YAML preset per country (`presets/ua.yaml`). Hunter loads it at the start of every run; pre-flight scans `agents/market-research/data/<country>/...` for user-placed files (customs, trademap, prozorro XLS exports) and returns `needs_data` with a human-readable checklist if anything is missing. When all files are present, Hunter registers them as first-class sources (IDs `src-001..N`), fetches public JSON APIs via existing Firecrawl tooling, and biases Tavily discovery toward preset-listed authoritative domains. A sibling `ua.learned.yaml` accumulates new high-signal domains Hunter discovers in the field, never touching the hand-curated file. Mira's lead skill gains a new `needs_data` halt branch and a `resume <topic_id>` entry point so the user can download files, drop them in, and continue.

**Tech Stack:** Markdown skill files (`hunter.md`, `lead/skill.md`), YAML presets, existing Hunter tool surface (`Read`, `Write`, `Glob`, `mcp__tavily__search`, `mcp__firecrawl__scrape`, `mcp__firecrawl__search`). No Python, no new MCP servers.

**Testing philosophy (this plan is unusual):** This is a skill/doc edit, not code. There are no unit tests to write — the "behaviour" lives in Markdown instructions that Hunter follows at runtime. Per-task verification is a **manual Markdown inspection + a `Grep`/`Read` sanity check** to confirm the edit landed in the right place with the right content. The end-to-end validation in Task 8 is a dry-run of Mira against the existing `pvc-windows-doors-profiles-ukraine` topic with three drop-folder states (empty → partial → full), which exercises every new step at least once.

**Reference spec:** `docs/superpowers/specs/2026-04-08-hunter-country-presets-design.md` (commit `087ca86`).

**File map:**
- **Create** `agents/market-research/data/.gitignore`
- **Create** `agents/market-research/data/ua/customs/.gitkeep`
- **Create** `agents/market-research/data/ua/trademap/.gitkeep`
- **Create** `agents/market-research/data/ua/prozorro/.gitkeep`
- **Create** `agents/market-research/data/ua/ukrstat/.gitkeep`
- **Create** `agents/market-research/presets/.gitkeep`
- **Create** `agents/market-research/presets/ua.yaml`
- **Modify** `agents/market-research/stages/hunter.md` — insert Steps 0, 0b, 1b, 3b, 6b; modify Steps 2 and 3; keep existing tool list
- **Modify** `agents/market-research/lead/skill.md` — add `needs_data` branch to Stage 1 Hunter handling (near line 62-63); add `resume <topic_id>` to orchestration loop (near line 24-42)

---

## Task 1: Scaffold the drop-folder skeleton

**Files:**
- Create: `agents/market-research/data/.gitignore`
- Create: `agents/market-research/data/ua/customs/.gitkeep`
- Create: `agents/market-research/data/ua/trademap/.gitkeep`
- Create: `agents/market-research/data/ua/prozorro/.gitkeep`
- Create: `agents/market-research/data/ua/ukrstat/.gitkeep`
- Create: `agents/market-research/presets/.gitkeep`

- [ ] **Step 1: Create `agents/market-research/data/.gitignore`**

Exact content:

```
# Raw research data (customs XLS, trademap exports, prozorro exports, etc.)
# is not committed — may carry redistribution restrictions and bloats git.
# Folder structure IS committed via .gitkeep files so paths exist on clone.
*/*/*/*.xlsx
*/*/*/*.csv
*/*/*/*.pdf
*/*/*/*.zip
!.gitkeep
```

- [ ] **Step 2: Create five `.gitkeep` files (empty) to pin folder structure**

Create each of these as a zero-byte file:
- `agents/market-research/data/ua/customs/.gitkeep`
- `agents/market-research/data/ua/trademap/.gitkeep`
- `agents/market-research/data/ua/prozorro/.gitkeep`
- `agents/market-research/data/ua/ukrstat/.gitkeep`
- `agents/market-research/presets/.gitkeep`

- [ ] **Step 3: Verify the skeleton**

Run (Bash):
```bash
find agents/market-research/data agents/market-research/presets -type f | sort
```

Expected output (exact, 6 lines):
```
agents/market-research/data/.gitignore
agents/market-research/data/ua/customs/.gitkeep
agents/market-research/data/ua/prozorro/.gitkeep
agents/market-research/data/ua/trademap/.gitkeep
agents/market-research/data/ua/ukrstat/.gitkeep
agents/market-research/presets/.gitkeep
```

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/data/.gitignore \
        agents/market-research/data/ua/customs/.gitkeep \
        agents/market-research/data/ua/trademap/.gitkeep \
        agents/market-research/data/ua/prozorro/.gitkeep \
        agents/market-research/data/ua/ukrstat/.gitkeep \
        agents/market-research/presets/.gitkeep
git commit -m "feat(market-research): scaffold drop-folder + presets directories

Adds agents/market-research/data/ with country/source/YYYY-MM layout
and agents/market-research/presets/ directory. .gitignore excludes raw
data exports but preserves folder structure via .gitkeep."
```

---

## Task 2: Create `presets/ua.yaml` — the Ukraine country preset

**Files:**
- Create: `agents/market-research/presets/ua.yaml`

- [ ] **Step 1: Write the preset file**

Exact content for `agents/market-research/presets/ua.yaml`:

```yaml
# Ukraine country preset for Hunter (market-research stage 1).
# Loaded when topic.geography == "ua". Hand-curated; Hunter never writes
# to this file. Discoveries accumulate in sibling ua.learned.yaml.
#
# Schema version: 1
# Last reviewed: 2026-04-08

country: ua
display_name: Ukraine
language_hints: [uk, en]
schema_version: 1

# Domains that auto-qualify for initial_confidence: high and are kept
# regardless of Tavily ranking position.
authoritative_domains:
  - customs.gov.ua
  - cabinet.customs.gov.ua
  - ukrstat.gov.ua
  - stat.gov.ua
  - bank.gov.ua
  - prozorro.gov.ua
  - bi.prozorro.org
  - public.api.openprocurement.org
  - me.gov.ua
  - kmu.gov.ua
  - rada.gov.ua
  - data.gov.ua
  - trademap.org

# Classification tables. Research blocks reference entries via
# codes_ref: "<system>.<table_name>".
product_codes:
  ukt_zed:
    pvc_window_profiles:
      - { code: "3916 20 00 10", desc: "Профілі з ПВХ для вікон/дверей" }
      - { code: "3916 20 00 90", desc: "Інші профілі з ПВХ" }
      - { code: "3925 20 00 00", desc: "Двері, коробки та пороги з пластмас" }
      - { code: "3926 90 92 00", desc: "Комплектуючі / фурнітура з пластмас" }
  hs:
    pvc_window_profiles: ["391620"]
  kved:
    pvc_manufacturing: ["22.23", "22.29"]
  dk_021:
    windows_doors: ["44221000-5", "44210000-5"]

# Pre-flight checklist, keyed by research_block. Hunter aborts with
# status: needs_data if any entry's destination is empty.
manual_downloads:
  market_size:
    - source: "ДМС митна статистика ЗЕД"
      url: "https://cabinet.customs.gov.ua"
      codes_ref: "ukt_zed.pvc_window_profiles"
      time_granularity: monthly
      expected_filename_pattern: "customs_zed_.*_{YYYY-MM}\\.xlsx"
      destination: "agents/market-research/data/ua/customs/{YYYY-MM}/"
      download_hint: |
        Log into cabinet.customs.gov.ua → Статистика ЗЕД →
        фільтр за кодами УКТ ЗЕД 3916 20, імпорт, період = звітний місяць →
        експорт XLSX. Збережіть файл як
        customs_zed_391620_{YYYY-MM}.xlsx у вказаній директорії.

    - source: "Trade Map (ITC) — Ukraine imports HS 391620"
      url: "https://www.trademap.org"
      codes_ref: "hs.pvc_window_profiles"
      time_granularity: monthly
      expected_filename_pattern: "trademap_hs391620_ua_{YYYY-MM}\\.xlsx"
      destination: "agents/market-research/data/ua/trademap/{YYYY-MM}/"
      download_hint: |
        Log in → Trade statistics → Bilateral trade → Reporter: Ukraine →
        Product: HS 391620 (Plastics; profile shapes, of polymers of vinyl
        chloride) → Time series by partner → Export XLSX. Save as
        trademap_hs391620_ua_{YYYY-MM}.xlsx.

  procurement:
    - source: "ProZorro BI — windows/doors tenders"
      url: "https://bi.prozorro.org"
      codes_ref: "dk_021.windows_doors"
      time_granularity: monthly
      expected_filename_pattern: "prozorro_.*_{YYYY-MM}\\.xlsx"
      destination: "agents/market-research/data/ua/prozorro/{YYYY-MM}/"
      download_hint: |
        bi.prozorro.org → пошук за ДК 021:2015 код 44221000-5 (Вікна, двері
        та супутні вироби) → фільтр за місяцем → експорт XLSX. Збережіть як
        prozorro_44221000-5_{YYYY-MM}.xlsx.

# Public JSON endpoints — no auth. Hunter scrapes via mcp__firecrawl__scrape.
# Non-blocking: failures are logged but do not halt the run.
api_sources:
  - name: nbu_exchange_rate_month_end
    url_template: "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={YYYYMMDD_end}&json"
    research_block: macro
    description: "НБУ — офіційний курс валют на кінець звітного місяця"

  - name: nbu_policy_rate_series
    url_template: "https://bank.gov.ua/NBUStatService/v1/statdirectory/discountrt?json"
    research_block: macro
    description: "НБУ — облікова ставка, весь історичний ряд"

  - name: prozorro_public_api_tenders
    url_template: "https://public.api.openprocurement.org/api/2.5/tenders?offset={YYYY-MM-DD_start}"
    research_block: procurement
    description: "ProZorro публічний API — перелік тендерів від початку місяця"

  - name: ckan_data_gov_ua_construction_prices
    url_template: "https://data.gov.ua/api/3/action/package_search?q=%D1%86%D1%96%D0%BD%D0%B8+%D0%B1%D1%83%D0%B4%D1%96%D0%B2%D0%BD%D0%B8%D1%86%D1%82%D0%B2%D0%BE&rows=20"
    research_block: construction_demand
    description: "data.gov.ua CKAN — пошук датасетів «ціни будівництво»"

# Tavily query templates. Placeholders: {product}, {year}, {month_name_uk}.
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
    - "{product} prices Ukraine {year}"
  macro:
    - "курс гривні USD {year} НБУ"
    - "облікова ставка НБУ {year}"
    - "інфляція Україна ІСЦ {year}"
  regulation:
    - "антидемпінгове розслідування пластмаси Україна {year}"
    - "ввізне мито 3916 Україна {year}"
    - "ДСТУ EN 12608 Україна"
  procurement:
    - "ProZorro вікна ПВХ тендер {year}"
    - "держзакупівлі вікна металопластикові {year}"
```

- [ ] **Step 2: Verify the file parses as YAML**

Run (Bash):
```bash
python -c "import yaml; d = yaml.safe_load(open('agents/market-research/presets/ua.yaml', encoding='utf-8')); print('country:', d['country']); print('authoritative_domains:', len(d['authoritative_domains'])); print('manual_downloads blocks:', list(d['manual_downloads'].keys())); print('api_sources:', [s['name'] for s in d['api_sources']]); print('query_templates blocks:', list(d['query_templates'].keys()))"
```

Expected output:
```
country: ua
authoritative_domains: 13
manual_downloads blocks: ['market_size', 'procurement']
api_sources: ['nbu_exchange_rate_month_end', 'nbu_policy_rate_series', 'prozorro_public_api_tenders', 'ckan_data_gov_ua_construction_prices']
query_templates blocks: ['market_size', 'production', 'construction_demand', 'pricing', 'macro', 'regulation', 'procurement']
```

If any line differs, fix the YAML and re-run until it matches exactly.

- [ ] **Step 3: Commit**

```bash
git add agents/market-research/presets/ua.yaml
git commit -m "feat(market-research): add Ukraine country preset for Hunter

Preset encodes authoritative domains (customs/ukrstat/NBU/ProZorro/
trademap), product codes (УКТ ЗЕД, HS, КВЕД, ДК 021), manual-download
checklist (customs XLS, trademap export, prozorro export), public JSON
APIs (NBU rates, NBU policy, ProZorro public API, data.gov.ua CKAN),
and Tavily query templates per research block."
```

---

## Task 3: Hunter — add Step 0 (preset load + pre-flight)

**Files:**
- Modify: `agents/market-research/stages/hunter.md` — insert new section before the existing `## Workflow` numbered list

- [ ] **Step 1: Read the current `hunter.md` to confirm insertion point**

Run (Read tool): `agents/market-research/stages/hunter.md`

Confirm the `## Workflow` heading exists and that the first numbered step is `1. **Read the topic YAML.**`. The new content goes **immediately after `## Workflow`** and **before** `1. **Read the topic YAML.**`, renumbering nothing (it becomes Step 0 and 0b).

- [ ] **Step 2: Insert the new Step 0 + 0b**

Use the Edit tool to replace:

```
## Workflow

1. **Read the topic YAML.** Extract `topic_id`, `products`, `geography`, `language_hints`, `time_focus`, `research_blocks`, `notes`.
```

With:

```
## Workflow

0. **Load country preset (if any).** If a file exists at `agents/market-research/presets/<topic.geography>.yaml`:

   a. Load it with a YAML parser.
   b. If a sibling `agents/market-research/presets/<topic.geography>.learned.yaml` also exists, load it and shallow-merge its `learned_sources` list into the preset under the same key. Hand-curated `authoritative_domains` in the main preset always win on any domain conflict.
   c. Store the merged preset in memory for the rest of the run.
   d. If no preset file exists for the topic's geography, skip all preset-aware steps below (0b, 1b, 3b, 6b) and run the legacy generic flow starting at step 1. Countries without presets still work — they just don't get the drop-folder pre-flight or authoritative-domain boosting.

0b. **Pre-flight: verify manual downloads are in place.** (Only if a preset was loaded in step 0.)

   a. Iterate `preset.manual_downloads` for each block in `topic.research_blocks`. Skip blocks that don't appear in `preset.manual_downloads` — only the blocks the preset declares as requiring manual files are checked.
   b. For each entry, render `destination` and `expected_filename_pattern` by substituting `{YYYY-MM}` with `topic.time_focus`.
   c. Glob the rendered destination directory. If the directory does not exist OR no filename inside it matches the rendered `expected_filename_pattern` (treat the pattern as a regex anchored to the filename only), mark the entry as **missing**.
   d. If any entry is missing, immediately return to Mira with this exact JSON shape and **do not write `01-sources.json`, do not call Tavily, do not call Firecrawl, do not proceed to step 1**:

   ```json
   {
     "status": "needs_data",
     "topic_id": "<topic.topic_id>",
     "time_focus": "<topic.time_focus>",
     "missing": [
       {
         "source": "<preset.manual_downloads[block][i].source>",
         "research_block": "<block>",
         "destination": "<rendered destination path>",
         "expected_filename_pattern": "<rendered regex>",
         "download_hint": "<preset.manual_downloads[block][i].download_hint>"
       }
     ]
   }
   ```

   e. If all entries pass, continue to step 1.

1. **Read the topic YAML.** Extract `topic_id`, `products`, `geography`, `language_hints`, `time_focus`, `research_blocks`, `notes`.
```

- [ ] **Step 3: Verify the edit landed correctly**

Run (Grep):
```
pattern: "0b\\. \\*\\*Pre-flight"
path: agents/market-research/stages/hunter.md
output_mode: content
-n: true
```

Expected: one match on a single line inside `## Workflow`, before `1. **Read the topic YAML.**`.

Run (Grep):
```
pattern: "needs_data"
path: agents/market-research/stages/hunter.md
output_mode: count
```

Expected: count is 1 (the new JSON block).

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/stages/hunter.md
git commit -m "feat(hunter): add Step 0 preset load + 0b drop-folder pre-flight

Hunter now checks for agents/market-research/presets/<geo>.yaml at the
start of every run. When a preset exists, it scans the drop folder for
required manual downloads (customs XLS, trademap, prozorro exports) and
returns status: needs_data with a download checklist if anything is
missing — zero Tavily/Firecrawl calls on the fail-fast path."
```

---

## Task 4: Hunter — add Step 1b (drop-folder registration) + modify Steps 2 and 3

**Files:**
- Modify: `agents/market-research/stages/hunter.md` — insert Step 1b after Step 1; modify Step 2 (query decomposition) and Step 3 (Tavily discovery) to be preset-aware

- [ ] **Step 1: Insert Step 1b immediately after Step 1**

Use Edit tool. Replace the existing step 1 → step 2 transition:

```
1. **Read the topic YAML.** Extract `topic_id`, `products`, `geography`, `language_hints`, `time_focus`, `research_blocks`, `notes`.

2. **Decompose queries.** For each `research_block`, generate 2–4 focused search queries. Combine product × geography × block (e.g. "PVC windows Ukraine market size 2024"). Use language hints to build both English and native-language queries when a native source is likely to be authoritative. **Ukrainian = `uk`**, not `ua`.
```

With:

```
1. **Read the topic YAML.** Extract `topic_id`, `products`, `geography`, `language_hints`, `time_focus`, `research_blocks`, `notes`.

1b. **Register drop-folder files as sources.** (Only if a preset was loaded in step 0.) Glob every file under `agents/market-research/data/<topic.geography>/*/<topic.time_focus>/*`. For each file found, create a source record with the **lowest sequential IDs** (`src-001`, `src-002`, ...) so manual-download sources precede all web sources in `01-sources.json`:

   - `id`: next sequential `src-NNN`
   - `url`: `file:///<absolute path to the file>`
   - `source_title`: the matching `preset.manual_downloads[].source` label. Inference: the file's parent directory name (e.g. `customs`, `trademap`, `prozorro`) maps to the subfolder used in `destination` paths. If multiple manual_download entries share a subfolder, use the first one whose `expected_filename_pattern` matches the filename.
   - `research_block`: the block under which the matching `manual_downloads` entry was declared.
   - `initial_confidence`: `"high"`
   - `key_fact`: `"Manual download: <filename> — <source label>. To be parsed by Sift."`
   - `why_relevant`: `"Authoritative manual export for <research_block> (preset: <topic.geography>)."`
   - `date`: `<topic.time_focus>-01` (first day of the month)

2. **Decompose queries.** For each `research_block` in scope:

   - **If a preset was loaded** and `preset.query_templates[<block>]` exists, render each template by substituting `{product}` (= `topic.products[0].display_name` or its first string form), `{year}` (= year extracted from `topic.time_focus`), and `{month_name_uk}` (= Ukrainian month name, optional — leave the literal placeholder if unsure). These rendered strings ARE the queries for that block. Do not add ad-hoc queries on top.
   - **If no preset or no templates for this block**, fall back to the legacy behaviour: generate 2–4 focused queries combining product × geography × block. Use language hints to build both English and native-language queries when a native source is likely to be authoritative. **Ukrainian = `uk`**, not `ua`.

3. **Discovery via Tavily.** Run each query through `mcp__tavily__search`. Collect URLs, titles, snippets, publication dates. Drop obvious junk (aggregators, spam, SEO farms, forums).

   **Preset-aware ranking (only if a preset was loaded):** any Tavily hit whose hostname (after stripping `www.`) matches an entry in `preset.authoritative_domains` is **kept unconditionally**, regardless of ranking position, and is automatically tagged with `initial_confidence: "high"` when its source record is built in step 5. Non-preset hits go through normal junk filtering and ranking.
```

- [ ] **Step 2: Verify the edit**

Run (Grep):
```
pattern: "1b\\. \\*\\*Register drop-folder"
path: agents/market-research/stages/hunter.md
output_mode: content
-n: true
```

Expected: one match, on a line between Step 1 and Step 2.

Run (Grep):
```
pattern: "Preset-aware ranking"
path: agents/market-research/stages/hunter.md
output_mode: count
```

Expected: count is 1.

- [ ] **Step 3: Commit**

```bash
git add agents/market-research/stages/hunter.md
git commit -m "feat(hunter): register drop-folder files as low-ID sources + preset-aware queries

Step 1b scans agents/market-research/data/<geo>/*/{YYYY-MM}/ and maps
every file to a src-NNN record with initial_confidence: high, so Sift
processes manual customs/trademap/prozorro exports before any web
sources. Step 2 uses preset.query_templates when a preset is loaded;
Step 3 keeps all preset.authoritative_domains hits unconditionally."
```

---

## Task 5: Hunter — add Step 3b (API sources) + Step 6b (learned sources append)

**Files:**
- Modify: `agents/market-research/stages/hunter.md` — insert Step 3b after Step 3, insert Step 6b after Step 6

- [ ] **Step 1: Insert Step 3b after Step 3**

Use Edit tool. Replace the existing Step 3 → Step 4 transition:

```
3. **Discovery via Tavily.** Run each query through `mcp__tavily__search`. Collect URLs, titles, snippets, publication dates. Drop obvious junk (aggregators, spam, SEO farms, forums).

   **Preset-aware ranking (only if a preset was loaded):** any Tavily hit whose hostname (after stripping `www.`) matches an entry in `preset.authoritative_domains` is **kept unconditionally**, regardless of ranking position, and is automatically tagged with `initial_confidence: "high"` when its source record is built in step 5. Non-preset hits go through normal junk filtering and ranking.

4. **Fetch via Firecrawl.** For the best 3–8 URLs per research_block, use `mcp__firecrawl__scrape` to fetch clean content. Skip paywalled or failed fetches.
```

With:

```
3. **Discovery via Tavily.** Run each query through `mcp__tavily__search`. Collect URLs, titles, snippets, publication dates. Drop obvious junk (aggregators, spam, SEO farms, forums).

   **Preset-aware ranking (only if a preset was loaded):** any Tavily hit whose hostname (after stripping `www.`) matches an entry in `preset.authoritative_domains` is **kept unconditionally**, regardless of ranking position, and is automatically tagged with `initial_confidence: "high"` when its source record is built in step 5. Non-preset hits go through normal junk filtering and ranking.

3b. **Fetch public API sources.** (Only if a preset was loaded.) For each entry in `preset.api_sources` whose `research_block` is in `topic.research_blocks`:

   a. Render `url_template` by substituting these placeholders from `topic.time_focus`:
      - `{YYYYMMDD_end}` → last calendar day of the month as `YYYYMMDD` (e.g. `2026-03` → `20260331`)
      - `{YYYY-MM-DD_start}` → first calendar day of the month as `YYYY-MM-DD` (e.g. `2026-03` → `2026-03-01`)
      - `{YYYY-MM}` → `topic.time_focus` literal
      - `{year}` → 4-digit year from `topic.time_focus`
   b. Call `mcp__firecrawl__scrape` on the rendered URL.
   c. On success, register a source record immediately (with the next sequential `src-NNN`, appended after any drop-folder records from 1b and before the Tavily/Firecrawl records from step 4):
      - `url`: rendered URL
      - `source_title`: `preset.api_sources[].description`
      - `research_block`: `preset.api_sources[].research_block`
      - `initial_confidence`: `"high"`
      - `key_fact`: first 200 characters of the scraped body (JSON text), trimmed
      - `why_relevant`: `"Public API — <preset.api_sources[].name>"`
      - `date`: current run date in `YYYY-MM-DD` (date Hunter is running, not the topic time_focus — the API endpoint itself carries the temporal parameter)
   d. **Non-blocking on failure.** On any HTTP error, empty body, or Firecrawl exception, do NOT fail the run. Instead, append a one-line note to the Hunter run log (stdout/diagnostic output, not `01-sources.json`) of the form `{"skipped_api": "<name>", "reason": "<short>"}` and continue to the next entry.

4. **Fetch via Firecrawl.** For the best 3–8 URLs per research_block, use `mcp__firecrawl__scrape` to fetch clean content. Skip paywalled or failed fetches.
```

- [ ] **Step 2: Insert Step 6b after Step 6**

Use Edit tool. Replace:

```
6. **Target counts.** Aim for >= 10 distinct sources per research_block, total >= 40 sources for a full 8-block topic. Fewer is acceptable if the topic is narrow, but if any block has 0 sources, note it — Mira will retry.

7. **Write output file.** Write the JSON array to `output_path`. Pretty-print with 2-space indent. UTF-8.
```

With:

```
6. **Target counts.** Aim for >= 10 distinct sources per research_block, total >= 40 sources for a full 8-block topic. Fewer is acceptable if the topic is narrow, but if any block has 0 sources, note it — Mira will retry.

6b. **Append learned authoritative domains.** (Only if a preset was loaded.) For every successfully-fetched Tavily source from step 4 whose domain is **not** in `preset.authoritative_domains`, and whose host passes a low-bar authority sniff-test (second-level domain ends in `.gov.ua`, `.gov`, `.org.ua`, `.edu.ua`, or the source's `initial_confidence` you're about to assign is "medium" or "high"), record a learned-source entry:

   a. Target file: `agents/market-research/presets/<topic.geography>.learned.yaml`. Under **no circumstances** write to `presets/<geo>.yaml` — that file is hand-curated and read-only to Hunter.
   b. Read the target file if it exists; otherwise start with `{"learned_sources": []}`.
   c. For each qualifying domain, check if an entry already exists (match by exact `domain` string). If yes, bump `seen_count` by 1, update `last_seen` to today's date (`YYYY-MM-DD`), and union the current `topic_id` into `topics` and the current `research_block` into `research_blocks`. If no, append a new entry:
      ```yaml
      - domain: "<hostname without www.>"
        first_seen: "<YYYY-MM-DD>"
        last_seen: "<YYYY-MM-DD>"
        topics: ["<topic.topic_id>"]
        research_blocks: ["<the research_block>"]
        confidence_observed: "<high|medium>"
        seen_count: 1
      ```
   d. Write the updated file back. Never delete existing entries.
   e. If writing the learned file fails for any reason, log the error and continue — this step is never allowed to block the main run.

7. **Write output file.** Write the JSON array to `output_path`. Pretty-print with 2-space indent. UTF-8.
```

- [ ] **Step 3: Verify both insertions**

Run (Grep):
```
pattern: "3b\\. \\*\\*Fetch public API sources"
path: agents/market-research/stages/hunter.md
output_mode: content
-n: true
```

Expected: one match.

Run (Grep):
```
pattern: "6b\\. \\*\\*Append learned"
path: agents/market-research/stages/hunter.md
output_mode: content
-n: true
```

Expected: one match.

Run (Grep):
```
pattern: "url_template"
path: agents/market-research/stages/hunter.md
output_mode: count
```

Expected: count is 1 (inside Step 3b).

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/stages/hunter.md
git commit -m "feat(hunter): add API source fetch (3b) and learned domains append (6b)

Step 3b iterates preset.api_sources (NBU, ProZorro public API,
data.gov.ua CKAN), renders url_template placeholders against
topic.time_focus, scrapes via existing Firecrawl. Non-blocking on
failure. Step 6b appends newly-observed authoritative domains to
presets/<geo>.learned.yaml (append-only, never touches the
hand-curated preset)."
```

---

## Task 6: Mira — add `needs_data` branch to Stage 1 Hunter handling

**Files:**
- Modify: `agents/market-research/lead/skill.md` — extend the "Failure handling" block under "### Stage 1 — Hunter" (currently at lines 62-63)

- [ ] **Step 1: Read current Stage 1 handling**

Run (Read tool): `agents/market-research/lead/skill.md`, offset 48, limit 20

Confirm the current Stage 1 block ends with:

```
**Failure handling:**
- If `status: error` or `source_count: 0` -> retry once with a broader prompt ("broaden your query decomposition; consider related search terms"). If still fails -> mark topic failed, continue batch.
```

- [ ] **Step 2: Extend the Failure handling block**

Use Edit tool. Replace:

```
**Failure handling:**
- If `status: error` or `source_count: 0` -> retry once with a broader prompt ("broaden your query decomposition; consider related search terms"). If still fails -> mark topic failed, continue batch.
```

With:

```
**Failure handling:**
- If `status: error` or `source_count: 0` -> retry once with a broader prompt ("broaden your query decomposition; consider related search terms"). If still fails -> mark topic failed, continue batch.
- If `status: needs_data` -> **HALT this topic immediately** (do not advance to Sift, do not retry, do not loop). Do the following, in order:
  1. Write `_run-log.json` with `final_status: "awaiting_manual_data"`, `halted_at_stage: "hunter"`, `halted_at: "<ISO-8601 timestamp>"`, and copy Hunter's `missing` array verbatim into a `missing_manual_downloads` field.
  2. Leave the inbox file in `in-progress/` (do NOT move it to `done/`).
  3. Emit to Bill a human-readable message in this exact shape (one entry per missing file):
     ```
     [Mira] Pre-flight halted for <topic_id> (time_focus: <time_focus>).

     The following files must be placed in the drop folder before research can continue:

     1. <source label>
        → <destination path>
        Filename pattern: <expected_filename_pattern>
        How to get it: <download_hint — first line only; full hint is in the preset>

     2. ...

     Once all files are in place, tell Bill "resume <topic_id>" and the pipeline
     will re-dispatch Hunter from stage 1 for the same run directory.
     ```
  4. Continue the batch loop with the next topic (awaiting_manual_data is not a batch-level failure — other topics keep running).
```

- [ ] **Step 3: Verify the edit**

Run (Grep):
```
pattern: "needs_data"
path: agents/market-research/lead/skill.md
output_mode: count
```

Expected: count is 1.

Run (Grep):
```
pattern: "awaiting_manual_data"
path: agents/market-research/lead/skill.md
output_mode: count
```

Expected: count is 1 (appears inside the new block).

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/lead/skill.md
git commit -m "feat(mira): handle Hunter needs_data status as halt-and-prompt

Adds a new Stage 1 failure branch: when Hunter returns needs_data, Mira
halts the topic, writes _run-log final_status awaiting_manual_data,
leaves the inbox file in in-progress/, emits a download checklist to
Bill with destination paths and hints, and continues the batch loop
with other topics. Resume entry point added in next commit."
```

---

## Task 7: Mira — add `resume <topic_id>` entry point

**Files:**
- Modify: `agents/market-research/lead/skill.md` — add a new section "## Resume entry point" after the "## Orchestration loop" section (around line 42-43), and add a resume trigger to "## Trigger phrases"

- [ ] **Step 1: Extend the trigger phrases list**

Use Edit tool. Replace:

```
Examples:
- "Run the monthly market research batch."
- "Process pending topics in agents/market-research/inbox/pending/."
- "Run market research for `pvc-windows-doors-profiles-ukraine`" (single-topic override — still goes through the normal loop but restricted to that one file).
```

With:

```
Examples:
- "Run the monthly market research batch."
- "Process pending topics in agents/market-research/inbox/pending/."
- "Run market research for `pvc-windows-doors-profiles-ukraine`" (single-topic override — still goes through the normal loop but restricted to that one file).
- "Resume `pvc-windows-doors-profiles-ukraine`" (picks up a topic previously halted with `awaiting_manual_data` — see "Resume entry point" section below).
```

- [ ] **Step 2: Insert the Resume entry point section after the orchestration loop**

Use Edit tool. Replace:

```
4. Return 200-word summary to Bill: N succeeded, M failed, K partially succeeded, paths to reports.
```

With:

```
4. Return 200-word summary to Bill: N succeeded, M failed, K partially succeeded, K awaiting_manual_data, paths to reports.
```

Then use Edit tool to replace:

```
## 6-stage pipeline
```

With:

```
## Resume entry point

Triggered by "Resume `<topic_id>`" from Bill. Used to continue a topic that was previously halted with `final_status: "awaiting_manual_data"` (see Stage 1 Hunter failure handling below).

Steps:

1. Locate the most recent run directory for the topic: glob `agents/market-research/reports/<topic_id>/*/`, sort by mtime descending, take the first match. If nothing matches, return `"no prior run found for <topic_id>"` to Bill and stop.
2. Read `_run-log.json` from that run directory. If `final_status != "awaiting_manual_data"`, return `"topic <topic_id> is not awaiting manual data (current status: <status>)"` to Bill and stop.
3. Confirm the inbox file is still in `inbox/in-progress/`. If it has been moved elsewhere, return an error with the current location.
4. **Re-dispatch Hunter** against the same topic YAML inside the same run directory. Use the same dispatch format as Stage 1 in the pipeline below, with `retry_round: 0`. Do NOT create a new `-r2` directory — this is a continuation of the same run, not a collision.
5. Inspect Hunter's return:
   - `status: ok` → clear `final_status` from the run-log (it will be rewritten at the end of the run), then continue the pipeline normally from Stage 2 (Sift) through Publish. Complete the topic as usual.
   - `status: needs_data` → Hunter's pre-flight is still missing files. Re-emit the (shorter) checklist to Bill and stop. `final_status` stays `awaiting_manual_data`. Bill can place the remaining files and say "resume" again.
   - `status: error` → fall through to the normal Stage 1 error handling (retry once with broader prompt, then fail the topic).
6. After the topic completes (success or failure), return a one-line summary to Bill.

Resume is always **single-topic**, never batch. Multiple halted topics are resumed one at a time.

## 6-stage pipeline
```

- [ ] **Step 3: Verify both edits**

Run (Grep):
```
pattern: "## Resume entry point"
path: agents/market-research/lead/skill.md
output_mode: content
-n: true
```

Expected: one match.

Run (Grep):
```
pattern: "Resume `pvc-windows"
path: agents/market-research/lead/skill.md
output_mode: count
```

Expected: count is 1 (inside the trigger phrases list).

Run (Grep):
```
pattern: "awaiting_manual_data"
path: agents/market-research/lead/skill.md
output_mode: count
```

Expected: count is now 4 or more (previous task added some; resume section adds a few more).

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/lead/skill.md
git commit -m "feat(mira): add resume <topic_id> entry point

New single-topic action that re-dispatches Hunter against the latest
run dir for a topic whose final_status is awaiting_manual_data. Reuses
the same run directory (not a -r2 collision), falls through to Sift..
Publish on success, re-emits a shorter checklist on still-missing
files. Updates the orchestration loop return summary to include an
awaiting_manual_data count."
```

---

## Task 8: End-to-end dry-run validation

**Files:**
- Modify (temporarily, then revert): `agents/market-research/data/ua/customs/2026-04/` — drop a dummy test file
- Read only: `agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04-r3/` or similar new run directory created by Mira

**Scenario:** Exercise Mira against the existing `pvc-windows-doors-profiles-ukraine` topic in three drop-folder states.

**Note:** This task requires the user to be present to kick off Mira (or Bill to dispatch it). The executor running this plan cannot invoke Mira themselves — they can only set up the preconditions, describe the expected behaviour, and verify the artifacts after the user has run it. Treat this task as a **scripted manual QA**.

- [ ] **Step 1: Confirm the `pvc-windows-doors-profiles-ukraine` topic exists and is configured for geography `ua`**

Run (Read tool): `agents/market-research/inbox/in-progress/pvc-windows-doors-profiles-ukraine.yaml`

Confirm: `geography: ua`, `research_blocks` includes at least `market_size` and `procurement`. If the file is not in `in-progress/`, check `inbox/pending/` and `inbox/done/` — wherever it is, note the path. If `geography` is missing or different, stop and report the mismatch; do not attempt to run the dry-run until the topic is ready.

- [ ] **Step 2: Ensure the drop folder for the current run month is empty**

Run (Bash):
```bash
RUN_MONTH=$(date -u +%Y-%m)
echo "Run month: $RUN_MONTH"
ls -la "agents/market-research/data/ua/customs/$RUN_MONTH/" 2>/dev/null || echo "(missing, will be treated as empty)"
ls -la "agents/market-research/data/ua/trademap/$RUN_MONTH/" 2>/dev/null || echo "(missing, will be treated as empty)"
ls -la "agents/market-research/data/ua/prozorro/$RUN_MONTH/" 2>/dev/null || echo "(missing, will be treated as empty)"
```

Expected: all three report either "(missing, will be treated as empty)" or an empty listing. If any directory contains real files from a prior run, move them aside temporarily (e.g. rename the month folder to `<RUN_MONTH>.bak`) — we want a clean empty state for scenario A.

- [ ] **Step 3 — Scenario A (empty drop folder): ask the user to run Mira and verify halt**

Tell the user:

> "Please run: `Run market research for pvc-windows-doors-profiles-ukraine`. Expect Mira to halt at Stage 1 with a `needs_data` message listing three required files (customs, trademap, prozorro). When you see the checklist, paste it back here."

Wait for the user's response. When they paste the output, verify:

1. The output starts with `[Mira] Pre-flight halted for pvc-windows-doors-profiles-ukraine`.
2. It lists exactly three missing files (customs, trademap, prozorro).
3. Each entry has a destination path under `agents/market-research/data/ua/.../$RUN_MONTH/`.
4. No `01-sources.json` file was created in the run directory.

Run (Glob):
```
pattern: agents/market-research/reports/pvc-windows-doors-profiles-ukraine/*/01-sources.json
```

Look for any file modified in the last few minutes. Expected: none from this run (prior runs may exist).

Run (Read tool): the `_run-log.json` in the newest run directory under `reports/pvc-windows-doors-profiles-ukraine/`.

Expected: `final_status: "awaiting_manual_data"`, `halted_at_stage: "hunter"`, `missing_manual_downloads` array with three entries.

- [ ] **Step 4 — Scenario B (partial drop folder): place one file, resume, verify shorter checklist**

Run (Bash) to create a dummy customs file so Scenario B has something to find:
```bash
RUN_MONTH=$(date -u +%Y-%m)
mkdir -p "agents/market-research/data/ua/customs/$RUN_MONTH"
echo "dummy customs export for dry-run validation" > "agents/market-research/data/ua/customs/$RUN_MONTH/customs_zed_391620_$RUN_MONTH.xlsx"
ls -la "agents/market-research/data/ua/customs/$RUN_MONTH/"
```

Expected: one file listed matching the pattern `customs_zed_391620_<RUN_MONTH>.xlsx`.

Tell the user:

> "Now run: `Resume pvc-windows-doors-profiles-ukraine`. Expect Mira to re-dispatch Hunter, whose pre-flight should now report exactly TWO missing files (trademap, prozorro) instead of three. Paste the checklist when you see it."

Wait for the response and verify:

1. The message is emitted by the resume entry point (look for "Pre-flight halted" again but with a two-item list).
2. customs is NOT in the missing list.
3. trademap and prozorro ARE in the missing list.
4. The run directory is the **same** as in Scenario A (no new `-r2` suffix).

- [ ] **Step 5 — Scenario C (full drop folder): place remaining files, resume, verify pre-flight passes**

Run (Bash):
```bash
RUN_MONTH=$(date -u +%Y-%m)
mkdir -p "agents/market-research/data/ua/trademap/$RUN_MONTH" \
         "agents/market-research/data/ua/prozorro/$RUN_MONTH"
echo "dummy trademap export" > "agents/market-research/data/ua/trademap/$RUN_MONTH/trademap_hs391620_ua_$RUN_MONTH.xlsx"
echo "dummy prozorro export" > "agents/market-research/data/ua/prozorro/$RUN_MONTH/prozorro_44221000-5_$RUN_MONTH.xlsx"
```

Tell the user:

> "Now run: `Resume pvc-windows-doors-profiles-ukraine` one more time. Expect Hunter's pre-flight to pass, Step 1b to register the three dummy files as `src-001`, `src-002`, `src-003` in `01-sources.json`, and the pipeline to proceed to Sift. Sift will likely fail or return nothing useful (the dummy files are not real XLSX), which is fine — this dry-run is only validating Hunter + Mira wiring, not the downstream stages. Paste Mira's final summary when it finishes (it will likely be a 'failed' or 'partial' status because Sift can't parse dummy data)."

Wait for the response and verify:

1. Hunter advanced past pre-flight (no `needs_data` this time).
2. `01-sources.json` exists in the run directory.
3. Run (Bash):
   ```bash
   RUN_DIR=$(ls -td agents/market-research/reports/pvc-windows-doors-profiles-ukraine/*/ | head -1)
   python -c "
   import json
   with open('$RUN_DIR/_stage-artifacts/01-sources.json', encoding='utf-8') as f:
       sources = json.load(f)
   manual = [s for s in sources if s['url'].startswith('file://')]
   print(f'Total sources: {len(sources)}')
   print(f'Manual (file://) sources: {len(manual)}')
   for s in manual:
       print(f'  {s[\"id\"]}: {s[\"source_title\"]} — {s[\"url\"]}')
   "
   ```
   Expected: Total sources is some N >= 3. Manual sources is exactly 3, with IDs `src-001`, `src-002`, `src-003`, and URLs starting with `file:///`.

4. Sift/Audit may fail on the dummy data — that is acceptable. Success criterion for this task is **Hunter + Mira wiring works**, not a complete report.

- [ ] **Step 6: Clean up dummy files and revert any temporarily-moved real data**

Run (Bash):
```bash
RUN_MONTH=$(date -u +%Y-%m)
rm -f "agents/market-research/data/ua/customs/$RUN_MONTH/customs_zed_391620_$RUN_MONTH.xlsx"
rm -f "agents/market-research/data/ua/trademap/$RUN_MONTH/trademap_hs391620_ua_$RUN_MONTH.xlsx"
rm -f "agents/market-research/data/ua/prozorro/$RUN_MONTH/prozorro_44221000-5_$RUN_MONTH.xlsx"
# If you renamed any month folders to <month>.bak in Step 2, rename them back now:
# mv "agents/market-research/data/ua/customs/$RUN_MONTH.bak" "agents/market-research/data/ua/customs/$RUN_MONTH"
```

Verify dummy files are gone and no real files were disturbed.

- [ ] **Step 7: Optionally delete the dry-run's broken report directory**

If the Scenario C run created a report directory whose downstream stages failed on dummy data, it's fine to delete that run directory to keep the reports folder tidy — but ask the user first before deleting anything under `reports/`.

- [ ] **Step 8: Write a short dry-run log and commit it**

Create `docs/superpowers/plans/2026-04-08-hunter-country-presets-dryrun.md` with a 20-30 line summary of what was tested in each scenario and the observed vs. expected outcomes. Exact content depends on what the user reported in steps 3-5; write it from their feedback.

Then commit:
```bash
git add docs/superpowers/plans/2026-04-08-hunter-country-presets-dryrun.md
git commit -m "docs: dry-run validation log for Hunter country presets

Three scenarios exercised: empty drop folder (halt + checklist),
partial drop folder (resume + shorter checklist), full drop folder
(pre-flight passes, drop-folder files registered as src-001..003).
All new Hunter steps and the Mira needs_data/resume flow verified."
```

---

## Self-review findings

Ran the self-review checklist against the spec (`docs/superpowers/specs/2026-04-08-hunter-country-presets-design.md`):

**Spec coverage:**
- Architecture diagram → covered by the plan's Goal + Architecture header and Tasks 3-5
- Preset schema (`authoritative_domains`, `product_codes`, `manual_downloads`, `api_sources`, `query_templates`) → Task 2 writes all five sections
- Drop folder layout + `.gitignore` → Task 1
- Step 0 (preset load) and 0b (pre-flight) → Task 3
- Step 1b (drop-folder registration) → Task 4
- Step 2 modifications (preset-aware query decomposition) → Task 4
- Step 3 modifications (authoritative-domain boosting) → Task 4
- Step 3b (API sources via Firecrawl) → Task 5
- Step 6b (learned-sources append) → Task 5
- Mira `needs_data` halt branch → Task 6
- Mira `resume <topic_id>` entry point → Task 7
- Testing plan's 6 scenarios (pre-flight miss / partial / pass / API failure tolerance / learning loop / resume) → Task 8 covers scenarios 1-3 and 6 directly; scenarios 4 (API failure) and 5 (learning loop) are implicitly exercised in Scenario C if the real pipeline runs, but are not explicitly scripted because they require real API access and real Tavily hits that we can't guarantee in a dry-run. **Accepted gap:** API-failure and learning-loop validation happens organically in the first real production run; documented as such in the dry-run log.
- Security boundaries (`ua.yaml` read-only, data files never committed) → enforced by Task 1's `.gitignore` and Task 5 Step 2's explicit "under no circumstances write to `presets/<geo>.yaml`" wording in Hunter's Step 6b.

**Placeholder scan:** No TBD / TODO / "implement later" / "add error handling" / "write tests for the above" / "similar to Task N" in any step. Every step that modifies a file shows the exact content and every verification step shows the exact command + expected output.

**Type consistency:** Field names used consistently across tasks:
- `status: needs_data` (Task 3, Task 6) ✓
- `missing` (Task 3 JSON schema, Task 6 run-log field `missing_manual_downloads` — DIFFERENT names intentionally; Hunter returns `missing` inline, Mira persists it as `missing_manual_downloads` in the run log to disambiguate from other log fields) ✓ (intentional divergence, noted here)
- `final_status: "awaiting_manual_data"` (Task 6, Task 7) ✓
- `halted_at_stage: "hunter"` (Task 6) — not referenced elsewhere, but consistent with the existing run-log schema stage naming ✓
- `preset.manual_downloads`, `preset.authoritative_domains`, `preset.api_sources`, `preset.query_templates` — used identically across Tasks 3, 4, 5 ✓
- `initial_confidence: "high"` string value — used in Tasks 4 and 5 consistently ✓
