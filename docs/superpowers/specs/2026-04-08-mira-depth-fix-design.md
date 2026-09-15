# Mira Market Research — Depth Fix Design Spec

**Date:** 2026-04-08
**Status:** Approved (user delegated brainstorming/approval: "just go to plan and implementation")
**Owner:** Bill (orchestrator)
**Context:** First real Mira run on `pvc-windows-doors-profiles-ukraine` (2026-04-r3) produced a shallow report. A reference report authored manually in a prior chat session (`agents/inbox/team/PVH_Vikna_Dveri_2025_Zvit (1).pdf`) defines the quality bar.

## 1. Problem statement

Mira's 2026-04-r3 run produced a report that is structurally empty relative to the reference:

- **39 facts collected, 0 confirmed (100% `weakly_supported`).** The entire verification layer zeroed out, so Quill emitted "insufficient confirmed data" for Sections 4 (Players), 5 (Trends), 6 (Risks).
- **16 of 39 facts have `value=null`** — they are placeholder records for binary `.xls`/`.xlsx` files that Sift cannot parse. The entire quantitative core of the report (ITC Trade Map HS 390410 / 391620 / 392520 flows, ProZorro CPV 44221000-5 tender data) is absent.
- **Construction demand data is absent** — Держстат SDMX datasets are present on disk under `agents/market-research/data/ua/ukrstat/` but the preset has no `manual_downloads` entry for them, so Hunter step 1b never registers them.
- **NBU FX panel appears as 8 facts from one source**, inflating fact count while adding no real coverage.
- **Quill's "no uncited body claim" rule** forbids legitimate derived inferences (e.g. "Poland = 56% of profile imports → likely Polish-brand dominance in Ukrainian fabrication"), forcing player/trend/risk sections to disclaimers.

Five root causes, ranked:

1. **Sift has no binary-file parser.** `mcp__firecrawl__extract` is HTML-only. `.xls`/`.xlsx`/`.webp` sources arrive as `file://` URLs from Hunter step 1b and get stubs.
2. **Audit's strict `≥2 independent sources` rule pathologically collides with the strict official-sources-only whitelist.** There is no second tier-1 publisher of an NBU FX rate or a Rada antidumping decision — every official fact cascades to `weakly_supported`, and Quill discards it from the body.
3. **Missing preset coverage for `ukrstat/` folder.** `ua.yaml` declares `customs`, `trademap`, `prozorro` manual-downloads but not `ukrstat`, so the 3 Держстат xlsx files already on disk are invisible to Hunter.
4. **Silent API-source failures.** Hunter step 3b logs `nbu_policy_rate_series` HTTP 404 and `ckan_data_gov_ua_construction_prices` "too large" then drops them. No fallback.
5. **Quill refuses derived inferences.** Current rule: every body sentence must map to a verbatim fact_id. Gold report synthesizes across facts; Mira cannot.

## 2. Goals

- Restore quantitative depth: trade-flow tables, ProZorro series, Держстат construction numbers — all from already-on-disk official sources.
- Allow Quill to synthesize: named players derived from import geography; risks derived from fact patterns; trends derived from multi-year series.
- Keep the strict official-sources-only whitelist. No media/blogs/consultancies. The fix is about *depth from existing official sources*, not broader sourcing.
- Verification: re-run the PVC Ukraine topic end-to-end and compare to the reference PDF. Target ≥80% of the reference report's numeric content.

## 3. Decisions locked

| # | Decision | Value |
|---|---|---|
| D1 | Verification rule for official sources | **Single whitelisted-official source → `confirmed`.** Drop `≥2 independent sources` for facts where the source is in `preset.authoritative_domains` or is a `file://` manual-download source. Non-official sources cannot reach Audit under strict whitelist mode anyway. |
| D2 | Binary file parsing | **New Parser stage** (`02a-parse`) that runs in Bill's own context between Hunter and Sift. Deterministic Python via `Bash` for xlsx/xls (openpyxl + xlrd), native `Read` tool for webp/png images. Writes `02a-parsed.json` — a normalized array of row-level data keyed by `source_id`. Sift then skips already-parsed `file://` sources and only calls Firecrawl `/extract` on http sources. Keeps Sift's "schema-driven extract only" role clean. |
| D3 | Quill synthesis rule | **Derived inferences allowed** in body sections 4–8, tagged inline as `(derived from fact-003, fact-007)`. Derivation must be a single logical step (count/share/ratio/comparison) — no multi-hop speculation. Hawk validates in QA. Section 3 (Key Metrics) and numerical claims still require verbatim fact_id. |
| D4 | Ukrstat preset entry | Add `manual_downloads` entry for `ukrstat/` with `relevant_blocks: [demand_drivers, construction_demand, production]`. `expected_filename_pattern` accepts the `dataset_*.xlsx` naming Держстат SDMX exports use. |
| D5 | Hunter time_focus fallback | If topic `time_focus` is "2025" and `manual_downloads` destination is `data/ua/ukrstat/{period}/`, but files are in `data/ua/ukrstat/` bare (user-dropped without the period subfolder), Hunter's glob also searches the parent folder with a 1-level depth. Don't force users to move files. |
| D6 | API fallbacks | `nbu_policy_rate_series`: fix URL (current endpoint returns 404; use `https://bank.gov.ua/NBUStatService/v1/statdirectory/discount` — singular `discount`, not `discountrt`). `ckan_data_gov_ua_construction_prices`: narrow query, limit `rows=5`, and on "too large" response, retry with `rows=1`. |
| D7 | Whitelist expansion | **None.** Strict-official stays. No interfax/forbes/chemorbis. |
| D8 | Quill report template | Gap notes become terse 1-line footnotes (`> Note: pricing block has thin coverage, see §9.4.`), not 400-word panic boxes. Executive summary leads with the headline number, not a verification disclaimer. |
| D9 | Sage's role | Sage becomes the synthesis engine, not just an insights lister. Sage produces `04-insights.json` entries tagged with `derivation_type: count | share | ratio | comparison | qualitative` and a `supporting_fact_ids` list. Quill consumes these directly for body narrative. |
| D10 | Hawk's role | Hawk gains a check: every derived-inference tag in the report must trace to a Sage insight with a valid derivation and supporting facts. |

## 4. Architecture changes

### 4.1 Pipeline flow

```
Hunter → Parser (NEW) → Sift → Audit → Sage → Quill → Hawk → Publish
```

- **Parser** is not a subagent. It runs in Bill's own context because (a) it needs `Bash` for Python, which subagents don't have by default, and (b) it's deterministic — no LLM reasoning required for xlsx rows.
- Parser reads `01-sources.json`, filters to `file://` sources, parses each, writes `02a-parsed.json`.
- **Sift** is modified: for each source in `01-sources.json`, if the source_id appears in `02a-parsed.json`, Sift reads rows from there and converts them into `02-facts.json` entries. For http sources, Sift keeps the existing Firecrawl `/extract` flow.
- All other stages unchanged in flow; changed in internal rules (D1, D3, D9, D10).

### 4.2 Parser stage contract

**Input:** `01-sources.json`, topic YAML
**Output:** `02a-parsed.json` — array of `{source_id, rows: [...], sheet_name, parser_type, warnings: []}`

**Parser types:**
- `xlsx_ooxml` — `openpyxl` on real `.xlsx` (Microsoft Excel 2007+ OOXML zip). Used for Держстат SDMX exports.
- `html_table` — `pandas.read_html` (via `lxml` + `beautifulsoup4`) on Trade Map `.xls` files, which are actually HTML tables with `.xls` extension (confirmed 2026-04-08 via `file(1)` — magic shows "HTML document, UTF-8 text"). Trade Map exports use the Microsoft "Excel opens HTML tables" trick.
- `image_vision` — Read tool on `.webp`/`.png`/`.jpg`; Bill (in context) emits structured rows by visual inspection. Used for ProZorro dashboard screenshots.
- `unknown` — log warning, skip.

**Runtime:** **Python 3.12** installed 2026-04-08 via `winget install Python.Python.3.12`. Absolute interpreter path: `C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe` (bare `python`/`python3` on PATH resolves to the Windows Store stub, which exits 49 — always use the absolute path). Required packages (already installed): `openpyxl`, `xlrd==1.2.0` (kept for safety; xlrd≥2 dropped .xls support), `pandas`, `beautifulsoup4`, `lxml`. Parser script is `agents/market-research/tools/parse_sources.py`, invoked via Bash as:
```
"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" \
  agents/market-research/tools/parse_sources.py \
  <sources.json> <output.json>
```
The interpreter path is stored once in `agents/market-research/tools/python-interpreter.txt` so the lead skill can read it without hard-coding the path in the skill file.

**Per-file dispatch:**
- `.xlsx` → `xlsx_tabular`
- `.xls` → `xls_legacy`
- `.webp`, `.png`, `.jpg` → `image_vision`
- other → `unknown` (log, skip)

**Header heuristics:** Trade Map and Держstat SDMX both emit multi-row headers. Parser tries row 0 as headers first; if >50% of row-0 cells are empty or numeric, walk down up to row 5 until it finds a row that looks like headers (all strings, ≥3 non-empty cells).

**Per-source row cap:** 500 rows max per sheet. Trade Map "partner country" exports are well under 250 rows; anything larger is likely the wrong sheet.

### 4.3 Sift changes

- Add input: `parsed_path` → `02a-parsed.json`.
- **For each source in `01-sources.json`:**
  - If `source.url` starts with `file://`: look up `source.id` in `02a-parsed.json`. Iterate parsed rows and convert to facts using a **per-parser-type mapping** (see 4.4). No Firecrawl call.
  - Else: existing Firecrawl `/extract` flow.
- New field on each fact: `is_official: true | false`. Set `true` if the source is `file://` (manual download) OR if the hostname of the source URL is in the loaded preset's `authoritative_domains`. Set `false` otherwise. In strict whitelist mode this is always `true` in practice, but the flag is explicit for Audit.

### 4.4 Row-to-fact mapping for parsed data

Parser emits raw rows; Sift maps rows to `02-facts.json` facts using the source's `research_block` and filename. Mapping table:

| Source filename pattern | research_block | Row semantics | Facts emitted |
|---|---|---|---|
| `Trade_Map_*supplying*` | import_export | each row = one supplier country | 1 fact per country per year column: `metric = "HS {code} imports from {country}"`, `value = cell`, `unit = "thousand USD"`, `time_period = column header` |
| `Trade_Map_*importing*` | import_export | each row = one destination country | same, metric = "HS {code} exports to {country}" |
| `dataset_*SSSU_DF_BEGINING_COMPLETION_CONSTRUCTION*` | demand_drivers | each row = one indicator × period | 1 fact per row, metric from indicator column, value from value column |
| `dataset_*SSSU_DF_ECONOM_INDC_SHORT-TERM_CONSTRUCTION*` | demand_drivers | same shape | same |
| `preview*.webp` (ProZorro) | market_size / demand_drivers | visual extraction | Bill extracts KPI values from the screenshot during Parser step |

The filename → HS code mapping is implicit in Trade Map's auto-generated filenames (they include the code if the download was done per-code). If the code can't be inferred from filename, Parser inspects cell A1 of the sheet — Trade Map puts the query in the top-left banner. Fall back: log warning, use `metric = "HS (unknown) …"` and let the user fix by renaming files.

### 4.5 Audit changes

Replace the current verification logic with:

```
for each fact:
  if fact.is_official == true:
    status = "confirmed"
    supporting_source_ids = [fact.source_id]
    confidence_score = 0.95
    continue

  # (existing ≥2-source logic for non-official facts — unreachable under strict
  #  whitelist mode but kept for future loosened modes)
```

Audit still emits the `gaps` array (blocks with < 50% `confirmed`) for Mira's retry decision. With D1, gaps effectively track *coverage* rather than *verification* — a block is a gap if it has few facts at all, not because of verification spread.

### 4.6 Sage changes

Sage becomes a real synthesis engine:

- Input: `03-verified.json`, `02-facts.json` (joined on fact_id for values)
- Output: `04-insights.json` with richer schema:

```json
{
  "id": "insight-001",
  "insight": "Poland is the dominant supplier of PVC profiles to Ukraine (56% of 2024 imports).",
  "derivation_type": "share",
  "supporting_fact_ids": ["fact-012", "fact-017"],
  "derivation_steps": [
    "fact-012: Ukraine imports of HS 391620 from Poland = 25,433 thousand USD in 2024",
    "fact-017: Ukraine total HS 391620 imports = 45,100 thousand USD in 2024",
    "25,433 / 45,100 = 56.4%"
  ],
  "implication": "Polish brands (REHAU, Salamander, Aluplast, Gealan) likely dominate local Ukrainian fabrication.",
  "confidence_level": "high",
  "research_block": "general_market_players"
}
```

- `derivation_type`: `count | share | ratio | comparison | trend | qualitative`
- `derivation_steps`: 1–5 lines, each showing the arithmetic or logical step
- The `implication` field is where Sage is allowed to name players/make forward-looking statements. Quill uses `implication` verbatim as body narrative.

Sage targets ≥ 3 insights per research_block. With the gold report as reference, that's 8 blocks × 3 = **~24 insights minimum**.

### 4.7 Quill changes

- **New rule:** Body narrative in sections 4–8 may cite either a `fact_id` (verbatim claim) or an `insight_id` (derived claim). Both forms are acceptable; insight citations use `(insight-003)` format.
- **Key Metrics (section 3) still verbatim-only.** Every number in a table must be a fact_id.
- **Gap notes:** one-line footnote at the end of the section, not a blockquote panic box. Example: `> Coverage note: 0 pricing facts; see §9.4.`
- **Executive summary:** lead with the single biggest number from confirmed facts. Never lead with verification status.
- **Remove the "Important reader note — verification status" preamble entirely.** That was a workaround for the broken verification layer. With D1, verification passes and the apology is obsolete.

### 4.8 Hawk changes

Add two checks:

1. **Derivation validation.** For each `(insight-NNN)` citation in the body, load the insight from `04-insights.json`, verify `supporting_fact_ids` all resolve, verify `derivation_steps` exists, and verify the arithmetic is plausible (if `derivation_type` is `share` or `ratio`, recompute the ratio from the cited facts and check it's within ±5% of the stated figure).
2. **Gap-note presence.** If any research_block has < 50% confirmed facts, the corresponding report section must contain the gap footnote. Missing gap notes = severity high.

## 5. Preset updates (`ua.yaml`)

Add one entry to `manual_downloads`:

```yaml
  - source: "Держстат SDMX — будівництво та введення в експлуатацію"
    url: "https://sdmx.ukrstat.gov.ua"
    codes_ref: null
    relevant_blocks: [demand_drivers, construction_demand, production]
    time_granularity: any
    optional: true
    expected_filename_pattern: ".*(CONSTRUCTION|BEGINING_COMPLETION).*\\.xlsx?$"
    destination: "agents/market-research/data/ua/ukrstat/{period}/"
    download_hint: |
      sdmx.ukrstat.gov.ua → пошук датасету SSSU_DF_BEGINING_COMPLETION_CONSTRUCTION
      (введення в експлуатацію житла, початок будівництва) та/або
      SSSU_DF_ECONOM_INDC_SHORT-TERM_CONSTRUCTION (обсяг будівельних робіт) →
      експорт XLSX. Файл можна покласти в директорію без підпапки з періодом —
      Hunter просканує і батьківську папку.
```

Fix `api_sources`:

```yaml
  - name: nbu_policy_rate_series
    # old URL returned 404: /statdirectory/discountrt?json
    url_template: "https://bank.gov.ua/NBUStatService/v1/statdirectory/discount?json"
    relevant_blocks: [pricing, macro, demand_drivers]
    description: "НБУ — облікова ставка, весь історичний ряд"
```

## 6. Testing / verification

After implementation, re-run the PVC Ukraine topic (`pvc-windows-doors-profiles-ukraine.yaml`) as a new r4 run. Acceptance checks:

- [ ] `02-facts.json` contains ≥ 100 facts (vs. 39 in r3)
- [ ] `03-verified.json` contains ≥ 80% `confirmed` status (vs. 0% in r3)
- [ ] `04-insights.json` contains ≥ 20 insights with non-trivial `derivation_steps`
- [ ] `report.uk.md` body contains concrete numbers for:
  - HS 391620 imports by country (≥ 5 countries)
  - HS 392520 exports by country (≥ 5 countries)
  - ProZorro lots + value for 2025
  - Держstat construction volume 2024 vs 2025
  - NBU FX + policy rate
- [ ] Sections 4 (Players), 5 (Trends), 6 (Risks) each contain ≥ 4 body sentences, not "insufficient data."
- [ ] Hawk verdict = `pass` (no high-severity issues)
- [ ] Side-by-side with reference PDF: ≥ 80% of reference's numeric content present.

## 7. Out of scope

- Full trend mode (Sage loading prior-run verified.json for delta analysis).
- DOCX/PDF custom styling.
- New country presets (Mira's only production preset is `ua.yaml`).
- Extending whitelist to media/consultancies.
- OCR beyond ProZorro screenshots (no plan to consume arbitrary user-dropped images).

## 8. Open items deferred to planning

- Exact structure of `02a-parsed.json` schema.
- Whether Parser runs as a single Python call per file or one big script — planning picks based on the actual shape of the real xlsx files on disk.
- Whether Sage's derivation validation lives in Sage itself or in Hawk (current design puts validation in Hawk; planning may move it earlier).
