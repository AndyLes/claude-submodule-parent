# Market Research Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `market-research` sub-team (Mira + 6 stage subagents) inside the existing Bill agent framework, wired to Firecrawl/Tavily MCP, scheduled monthly, and validated by a manual first run against the Ukraine PVC windows/doors topic.

**Architecture:** Mira is a lead orchestrator that dispatches 6 specialized subagents (Hunter → Sift → Audit → Sage → Quill → Hawk) sequentially via the `Agent` tool. Subagents communicate only via JSON files in `_stage-artifacts/` and return 1-line pointers to Mira. Tool lockout is structural via per-agent frontmatter `tools:` allowlists. Publish stage runs in Mira's context.

**Tech Stack:** Markdown skill files (agent definitions), YAML (config, topics, registry, routing), JSON (stage artifacts), Firecrawl MCP, Tavily MCP, `scheduled-tasks` MCP, `anthropic-skills:xlsx/docx/pdf` skills.

**Spec:** `docs/superpowers/specs/2026-04-07-market-research-team-design.md`

---

## Notes for the executing engineer

- This project is 95% configuration/skill-definition files, not runtime code. There is no test runner, no build step. "Verification" here means: YAML parses, frontmatter is valid, required sections exist, paths match what Mira expects.
- **The acceptance test is the manual first run (Task 13).** That's the real "does it work" moment. Treat earlier tasks as scaffolding that must all be in place before Task 13 can pass.
- **Do not edit files outside `agents/market-research/`, `agents/registry.yaml`, and `agents/bill/routing.yaml`** unless the task explicitly says so.
- **Use forward slashes in all paths written inside files**, even on Windows. The Bash tool is bash, so shell commands use Unix syntax (`/dev/null`, forward slashes). File paths in markdown/YAML content use forward slashes too for cross-platform.
- **Commit after every task.** Conventional commit format (`feat:`, `chore:`, `docs:`).
- **When a task says "Write file X"**, use the Write tool with the exact content shown. Do not paraphrase.
- **Schema field names must match exactly across agents.** Hunter writes `source_id`, Sift references `source_id`, Audit uses `fact_id`, etc. If you rename a field in one stage, all downstream agents break. The field names shown in this plan are the canonical names — do not "improve" them.

---

## File Structure

Files created by this plan (all under `C:\SuperWork\`):

```
agents/market-research/
├── lead/skill.md                          # Task 10 — Mira orchestrator
├── stages/
│   ├── hunter.md                          # Task 4
│   ├── sift.md                            # Task 5
│   ├── audit.md                           # Task 6
│   ├── sage.md                            # Task 7
│   ├── quill.md                           # Task 8
│   └── hawk.md                            # Task 9
├── inbox/
│   ├── pending/.gitkeep                   # Task 2
│   ├── in-progress/.gitkeep               # Task 2
│   └── done/.gitkeep                      # Task 2
├── reports/.gitkeep                       # Task 2
├── templates/
│   ├── topic.template.yaml                # Task 3
│   └── report.template.md                 # Task 3
├── .gitignore                             # Task 2
└── README.md                              # Task 2

agents/registry.yaml                       # Task 11 — add 7 entries
agents/bill/routing.yaml                   # Task 11 — add 1 rule

agents/market-research/inbox/pending/
└── pvc-windows-doors-profiles-ukraine.yaml  # Task 12 — first topic
```

Files NOT created by this plan (deferred / out of scope):
- No runtime code files (no `.py`, `.js`, `.ts`)
- No test suite (acceptance test is the manual first run)
- MCP config file (lives in local Claude Code settings, outside the repo — Task 1 is a manual verification step)

---

## Task 1: Prerequisites — MCP servers callable

**Files:** None created. This is a manual verification task.

**Context:** Firecrawl and Tavily MCP servers must be installed and callable from Claude Code before any stage subagent can run. They are configured in the user's local Claude Code settings, not in the repo. If they are already configured, this task is just verification.

- [ ] **Step 1: Check if Firecrawl MCP is already available**

Search the system-reminder at the top of this session for `firecrawl` in the MCP tool list (tools prefixed `mcp__firecrawl__` or similar). Also check Tavily.

If both are present → skip to Step 4.
If either is missing → continue with Step 2.

- [ ] **Step 2: Report missing MCP servers to the user**

Say to the user, verbatim:

> The plan requires `firecrawl-mcp` and `tavily-mcp` to be installed in Claude Code's local MCP config. I see [firecrawl/tavily/both] missing. Per spec §9, the config goes in your local Claude settings (not the repo). Could you install them now? Config shape:
>
> ```json
> {
>   "mcpServers": {
>     "firecrawl": { "command": "npx", "args": ["-y", "firecrawl-mcp"], "env": { "FIRECRAWL_API_KEY": "<your key>" } },
>     "tavily":    { "command": "npx", "args": ["-y", "tavily-mcp"],    "env": { "TAVILY_API_KEY": "<your key>" } }
>   }
> }
> ```
>
> Restart Claude Code after adding them, then tell me to continue.

Then STOP this task and wait for the user. Do not fabricate tool calls.

- [ ] **Step 3: After user confirms, verify tools are listed**

Ask the user to start a fresh Claude Code session (MCP tool lists refresh on restart). In the fresh session, re-read the MCP tool list and confirm both `firecrawl` and `tavily` tools are present.

- [ ] **Step 4: Smoke-test each MCP server**

Run a minimal call against each to confirm the API keys work. Use whatever the actual tool names turn out to be (will be something like `mcp__firecrawl__scrape` and `mcp__tavily__search`). Tavily: search for `"PVC windows Ukraine"`, limit 1. Firecrawl: scrape `https://example.com`.

Expected: both return without auth errors. If auth fails → report to user, stop.

- [ ] **Step 5: No commit for this task**

No files changed. Move to Task 2.

---

## Task 2: Folder skeleton, .gitignore, README

**Files:**
- Create: `agents/market-research/.gitignore`
- Create: `agents/market-research/README.md`
- Create: `agents/market-research/inbox/pending/.gitkeep`
- Create: `agents/market-research/inbox/in-progress/.gitkeep`
- Create: `agents/market-research/inbox/done/.gitkeep`
- Create: `agents/market-research/reports/.gitkeep`
- Create: `agents/market-research/lead/.gitkeep`
- Create: `agents/market-research/stages/.gitkeep`
- Create: `agents/market-research/templates/.gitkeep`

- [ ] **Step 1: Create `.gitignore`**

Write to `C:/SuperWork/agents/market-research/.gitignore`:

```gitignore
# Intermediate stage artifacts — regeneratable, verbose, sometimes large
reports/*/*/_stage-artifacts/

# In-progress inbox state is transient
inbox/in-progress/
inbox/done/*.invalid

# Error logs — transient, may contain fetched content
**/error.log

# Never commit secrets
**/mcp-config.local.json
```

- [ ] **Step 2: Create `README.md`**

Write to `C:/SuperWork/agents/market-research/README.md`:

```markdown
# Market Research Team

Sub-team inside the Bill agent framework. Produces monthly, high-rigor market research reports on the windows and doors industry (PVC/wood/aluminum windows, doors, profiles; pricing, import/export, trends, players, risks) across specific countries.

## Team

| Name   | Role                       | File                |
|--------|----------------------------|---------------------|
| Mira   | Lead / orchestrator        | `lead/skill.md`     |
| Hunter | Research (discovery+fetch) | `stages/hunter.md`  |
| Sift   | Extraction                 | `stages/sift.md`    |
| Audit  | Verification               | `stages/audit.md`   |
| Sage   | Analysis                   | `stages/sage.md`    |
| Quill  | Report writing             | `stages/quill.md`   |
| Hawk   | QA / red team              | `stages/hawk.md`    |

## Pipeline

```
topic.yaml → Hunter → Sift → Audit → Sage → Quill → Hawk → Publish
              01      02     03     04     05     06     report.{md,xlsx,docx,pdf}
```

All stages communicate only via JSON files in `_stage-artifacts/`. Subagents return 1-line pointers to Mira; full payloads never cross agent boundaries.

Verification is strict: every fact in the report body must have ≥2 independent sources marked `confirmed` by Audit. Weakly supported / conflicting facts go to an appendix only.

## Running a batch

- **Manual:** "Bill, run the market research batch"
- **Scheduled:** monthly at 09:00 on the 1st, via `scheduled-tasks` MCP (see spec §8)

## Dropping a new topic

1. Copy `templates/topic.template.yaml` to `inbox/pending/<topic-id>.yaml`
2. Fill in fields (see template comments)
3. File will be processed on next batch run

## Directories

- `lead/` — Mira's skill definition
- `stages/` — the 6 stage subagent skills
- `inbox/{pending,in-progress,done}/` — topic file lifecycle
- `reports/<topic-id>/<YYYY-MM>/` — per-run output
- `templates/` — topic + report templates

## Spec

Full design in `docs/superpowers/specs/2026-04-07-market-research-team-design.md`.
```

- [ ] **Step 3: Create `.gitkeep` files for empty directories**

Create empty files at:
- `C:/SuperWork/agents/market-research/inbox/pending/.gitkeep`
- `C:/SuperWork/agents/market-research/inbox/in-progress/.gitkeep`
- `C:/SuperWork/agents/market-research/inbox/done/.gitkeep`
- `C:/SuperWork/agents/market-research/reports/.gitkeep`
- `C:/SuperWork/agents/market-research/lead/.gitkeep`
- `C:/SuperWork/agents/market-research/stages/.gitkeep`
- `C:/SuperWork/agents/market-research/templates/.gitkeep`

Each file is empty (write empty string as content).

- [ ] **Step 4: Verify structure**

Run: `ls -la C:/SuperWork/agents/market-research/`
Expected: `.gitignore`, `README.md`, `inbox/`, `lead/`, `reports/`, `stages/`, `templates/` all present.

Run: `ls C:/SuperWork/agents/market-research/inbox/`
Expected: `pending/`, `in-progress/`, `done/` all present.

- [ ] **Step 5: Commit**

```bash
git add agents/market-research/
git commit -m "feat(market-research): scaffold folder skeleton, gitignore, README"
```

---

## Task 3: Templates

**Files:**
- Create: `agents/market-research/templates/topic.template.yaml`
- Create: `agents/market-research/templates/report.template.md`

- [ ] **Step 1: Create topic template**

Write to `C:/SuperWork/agents/market-research/templates/topic.template.yaml`:

```yaml
# Market research topic template.
# Copy this file to inbox/pending/<topic-id>.yaml and fill in the fields.
# Filename MUST equal topic_id + .yaml.

# --- Identity ---
topic_id: example-topic-id           # stable key — reused across months so runs stack
title: Example Topic Title
created: 2026-04-07                   # ISO date

# --- Scope ---
products:                             # single string or list
  - PVC windows
  - PVC doors
geography: Ukraine                    # country or region
language_hints: [uk, en]              # ISO 639-1 LANGUAGE codes (NOT country codes!)
                                      # Ukrainian = uk. "ua" is the country code and WILL fail silently.
time_focus: "last 24 months"

# --- Research focus blocks — drives Hunter's query decomposition ---
research_blocks:
  - market_size
  - pricing
  - general_market_players
  - demand_drivers
  - import_export
  - trends
  - regulation
  - risks

# --- Optional: trend mode ---
trend_mode: false                     # true = Sage loads prior reports for delta analysis
                                      # MVP: skeleton only, keep false
trend_lookback_months: 12

# --- Optional free-form focus/constraints ---
notes: |
  Put any scope-shaping notes here. Mira uses this to constrain the pipeline.
  Example: "Focus on residential segment. Include reconstruction-driven demand."
```

- [ ] **Step 2: Create report template**

Write to `C:/SuperWork/agents/market-research/templates/report.template.md`:

```markdown
---
topic_id: <filled by Publish>
title: <filled by Publish>
run_month: <YYYY-MM filled by Publish>
generated: <ISO timestamp filled by Publish>
rigor: strict
retry_counts:
  hunter: 0
  quill: 0
---

# <Report Title>

## 1. Executive Summary

<3-5 bullets of headline findings. Every claim here must reference a fact_id confirmed by Audit.>

## 2. Market Overview

<Market definition, scope, geography, time window.>

## 3. Key Metrics

<Tables of confirmed metrics. Each row cites a fact_id.>

## 4. General Market Players

<Confirmed players and their positioning. Only confirmed facts.>

## 5. Trends & Drivers

<Confirmed trends and demand drivers.>

## 6. Risks

<Confirmed risks, with sources.>

## 7. Opportunities

<Confirmed opportunities.>

## 8. Recommendations

<Actionable recommendations grounded in confirmed insights.>

## 9. Methodology

- Strict verification: ≥2 independent sources required per body fact.
- Sources: see `data.xlsx` → Sources sheet.
- Retry rounds: see frontmatter.
- Tool allocation: Hunter/Audit had web access; Sage/Quill/Hawk did not.

## Appendix A — Weakly supported facts

<Facts that did not reach ≥2 independent sources. Never used in the body.>

## Appendix B — Conflicting sources

<Where sources disagreed. Kept for audit trail.>
```

- [ ] **Step 3: Verify YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('C:/SuperWork/agents/market-research/templates/topic.template.yaml'))" && echo OK`
Expected: `OK`

If Python unavailable, skip — YAML will be revalidated in later tasks.

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/templates/
git commit -m "feat(market-research): add topic and report templates"
```

---

## Task 4: Hunter (Stage 1 — Research/Discovery)

**Files:**
- Create: `agents/market-research/stages/hunter.md`
- Delete: `agents/market-research/stages/.gitkeep` (no longer needed once stages/ has real files)

**Reference:** spec §5 pipeline table, §5 `01-sources.json` schema, §9 tool allocation (Hunter gets tavily + firecrawl).

- [ ] **Step 1: Write `hunter.md`**

Write to `C:/SuperWork/agents/market-research/stages/hunter.md`:

```markdown
---
name: hunter
description: Stage 1 of the market research pipeline — discovers and fetches candidate sources for a topic. Returns a JSON file of source records, never the payload itself.
type: subagent
tools: [Read, Write, Glob, Grep, mcp__tavily__search, mcp__firecrawl__scrape, mcp__firecrawl__search]
---

## Role

Hunter is stage 1 of the 6-stage market research pipeline led by Mira. Given a topic YAML and a target output path, Hunter discovers candidate sources via Tavily search, fetches the most promising with Firecrawl, and writes a flat JSON array of source records to disk. Hunter does **not** extract structured metrics — that is Sift's job. Hunter does **not** verify — that is Audit's job.

## Inputs (from Mira's dispatch message)

- `topic_yaml_path`: absolute path to the topic YAML file (already validated by Mira)
- `output_path`: absolute path where `01-sources.json` must be written
- `retry_round`: integer, 0 for first run
- `gaps` (optional, only on retries): list of `research_block` names that were under-verified last round; scope queries to these blocks only

## Workflow

1. **Read the topic YAML.** Extract `topic_id`, `products`, `geography`, `language_hints`, `time_focus`, `research_blocks`, `notes`.

2. **Decompose queries.** For each `research_block`, generate 2–4 focused search queries. Combine product × geography × block (e.g. "PVC windows Ukraine market size 2024"). Use language hints to build both English and native-language queries when a native source is likely to be authoritative. **Ukrainian = `uk`**, not `ua`.

3. **Discovery via Tavily.** Run each query through `mcp__tavily__search`. Collect URLs, titles, snippets, publication dates. Drop obvious junk (aggregators, spam, SEO farms, forums).

4. **Fetch via Firecrawl.** For the best 3–8 URLs per research_block, use `mcp__firecrawl__scrape` to fetch clean content. Skip paywalled or failed fetches.

5. **Build source records.** For each successfully fetched URL, create one record in the output schema. Assign sequential IDs `src-001`, `src-002`, ... Capture a short `key_fact` (≤ 200 chars) summarizing what this source contributes, and `why_relevant` (≤ 200 chars).

6. **Target counts.** Aim for ≥ 10 distinct sources per research_block, total ≥ 40 sources for a full 8-block topic. Fewer is acceptable if the topic is narrow, but if any block has 0 sources, note it — Mira will retry.

7. **Write output file.** Write the JSON array to `output_path`. Pretty-print with 2-space indent. UTF-8.

8. **Return to Mira.** Respond with exactly one line of JSON:

```json
{"status": "ok", "output_file": "01-sources.json", "source_count": 47, "blocks_covered": ["market_size", "pricing", ...], "blocks_empty": []}
```

On failure, return `{"status": "error", "reason": "<short>"}` and do not write a partial file.

## Output schema — `01-sources.json`

A JSON array. Each element:

```json
{
  "id": "src-001",
  "source_title": "string",
  "url": "https://...",
  "key_fact": "string (<=200 chars)",
  "date": "YYYY-MM-DD or null if unknown",
  "research_block": "market_size",
  "why_relevant": "string (<=200 chars)",
  "initial_confidence": "high | medium | low"
}
```

- `research_block` MUST match one of the blocks from the topic YAML exactly.
- `initial_confidence`: "high" = government/trade-association/major-consultancy source, "medium" = specialist trade press, "low" = general press/blog.

## Rules

- **Never read other stage files.** Hunter only reads the topic YAML.
- **Never return the sources JSON inline.** Return the pointer only.
- **Never hallucinate sources.** Every record must correspond to a real Tavily hit you actually fetched with Firecrawl.
- **On retry round**, restrict queries to `gaps` blocks only. Start IDs from `src-001` again — each round's file is self-contained.
- **Token discipline:** keep your return message under 200 characters.
```

- [ ] **Step 2: Delete stub**

Delete `C:/SuperWork/agents/market-research/stages/.gitkeep`.

- [ ] **Step 3: Verify frontmatter**

Run: `head -n 6 C:/SuperWork/agents/market-research/stages/hunter.md`
Expected: frontmatter with `name: hunter`, `type: subagent`, `tools:` including tavily and firecrawl tools.

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/stages/
git commit -m "feat(market-research): add Hunter (stage 1 — research/discovery)"
```

---

## Task 5: Sift (Stage 2 — Extraction)

**Files:**
- Create: `agents/market-research/stages/sift.md`

**Reference:** spec §5 `02-facts.json` schema, §9 tool allocation (Sift gets firecrawl `/extract` only).

- [ ] **Step 1: Write `sift.md`**

Write to `C:/SuperWork/agents/market-research/stages/sift.md`:

```markdown
---
name: sift
description: Stage 2 of the market research pipeline — extracts structured facts (metrics, values, units) from Hunter's source list. Schema-driven extraction via Firecrawl /extract only. Returns a JSON file of fact rows.
type: subagent
tools: [Read, Write, mcp__firecrawl__extract]
---

## Role

Sift is stage 2. Given Hunter's `01-sources.json`, Sift fetches each URL through Firecrawl `/extract` with a structured schema and converts prose into one row per metric. Sift does not discover new sources. Sift does not verify. Sift does not have Tavily or generic Firecrawl scrape — only the schema-driven `/extract`.

## Inputs (from Mira)

- `sources_path`: absolute path to `01-sources.json`
- `topic_yaml_path`: absolute path to topic YAML (for context: geography, time_focus)
- `output_path`: absolute path where `02-facts.json` must be written

## Workflow

1. **Read `sources_path`** — full list of source records from Hunter.
2. **Read topic YAML** — for geography, products, time_focus, research_blocks.
3. **Build an extraction schema per research_block type.** Use the schemas below. Each schema targets metrics relevant to that block.
4. **Call Firecrawl `/extract`** on each source URL with the appropriate block schema. Use the source's `research_block` to pick the schema.
5. **Convert extract output to fact rows.** One row per distinct metric found. Assign sequential IDs `fact-001`, `fact-002`, ... Preserve the originating `source_id` from Hunter.
6. **Skip empty extracts** — if `/extract` returns nothing for a source, drop it silently (don't write empty rows). Log the count of skipped sources in the return pointer.
7. **Write `02-facts.json`** — JSON array, pretty-printed, UTF-8.
8. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "02-facts.json", "fact_count": 134, "sources_processed": 47, "sources_skipped": 3}
```

## Extraction schemas

Sift calls Firecrawl `/extract` with a JSON schema describing what to pull. Pick one of these based on the source's `research_block`:

**`market_size` schema:**
```json
{"type": "object", "properties": {
  "metric_name": {"type": "string"},
  "value": {"type": "number"},
  "unit": {"type": "string", "description": "e.g. M EUR, thousand units, tons"},
  "geography": {"type": "string"},
  "time_period": {"type": "string", "description": "e.g. 2024, Q3 2024, 2022-2024"},
  "notes": {"type": "string"}
}}
```

**`pricing` schema:** same shape, metric_name reflects price point (e.g. "average PVC profile retail price per meter").

**`import_export` schema:** add `trade_direction` ("import" | "export") and `counterparty_country`.

**`general_market_players` schema:**
```json
{"type": "object", "properties": {
  "player_name": {"type": "string"},
  "market_share": {"type": "number", "description": "percent, 0-100, null if unknown"},
  "positioning": {"type": "string"},
  "geography": {"type": "string"},
  "time_period": {"type": "string"}
}}
```

**`demand_drivers`, `trends`, `regulation`, `risks` schemas:** treat as qualitative — extract one row per distinct claim with `metric_name` = short claim label and `value` = null, `unit` = null, `notes` = the claim text (≤ 300 chars).

## Output schema — `02-facts.json`

```json
{
  "id": "fact-001",
  "metric": "string (metric_name from extract)",
  "value": 480,
  "unit": "M EUR",
  "geography": "Ukraine",
  "time_period": "2024",
  "source_id": "src-001",
  "source_url": "https://...",
  "confidence": "high | medium | low (inherit from source's initial_confidence)",
  "notes": "string, may be empty",
  "research_block": "market_size"
}
```

- `value` may be `null` for qualitative facts (trends, risks, regulation).
- `unit` may be `null` for qualitative facts.
- `research_block` is carried forward from the source — Audit needs it for gap analysis.

## Rules

- **No web tools except `/extract`.** Sift cannot search, cannot scrape, cannot invent metrics.
- **No summarization.** Extract what's stated. If a source doesn't state a hard metric, use the qualitative treatment (value=null, claim in notes).
- **Preserve source_id linkage** — Audit relies on it.
- **Keep return pointer under 200 characters.**
```

- [ ] **Step 2: Commit**

```bash
git add agents/market-research/stages/sift.md
git commit -m "feat(market-research): add Sift (stage 2 — extraction)"
```

---

## Task 6: Audit (Stage 3 — Verification)

**Files:**
- Create: `agents/market-research/stages/audit.md`

**Reference:** spec §5 `03-verified.json` schema, §5 strict verification loop, §9 (Audit gets both tavily and firecrawl).

- [ ] **Step 1: Write `audit.md`**

Write to `C:/SuperWork/agents/market-research/stages/audit.md`:

```markdown
---
name: audit
description: Stage 3 of the market research pipeline — verifies every fact by cross-checking against ≥2 independent sources. Produces verified.json with per-fact verdict and a gaps array Mira uses to trigger retries.
type: subagent
tools: [Read, Write, mcp__tavily__search, mcp__firecrawl__scrape, mcp__firecrawl__search]
---

## Role

Audit is stage 3, the verification gatekeeper. Every fact from Sift is cross-checked against additional independent sources. The rigor level is **strict**: a fact only becomes `confirmed` if at least 2 independent sources support it and no source contradicts it. Audit has Tavily and Firecrawl because it often needs to find new corroborating sources that Hunter missed.

## Inputs (from Mira)

- `facts_path`: absolute path to `02-facts.json`
- `sources_path`: absolute path to `01-sources.json` (for source metadata)
- `output_path`: absolute path where `03-verified.json` must be written
- `topic_yaml_path`: absolute path to topic YAML (to list the expected research_blocks for gap analysis)

## Workflow

1. **Read facts, sources, topic YAML.**

2. **For each fact:**
   - Check if another source in `01-sources.json` already independently supports this fact (same metric, compatible value within ±10%, same time window, same geography). If yes → candidate for `confirmed`.
   - If only the original source supports it, run a targeted Tavily search for the metric (e.g. `"PVC windows Ukraine market size 2024"`). Fetch top 2–3 results with Firecrawl. If any independently confirms → status `confirmed`.
   - If sources disagree on value (>20% spread, or contradictory qualitative claims) → status `conflicting`, list all supporting_source_ids.
   - If only stale (>3 years older than `time_focus`) sources support → status `outdated`.
   - Otherwise → status `weakly_supported`.

3. **Independence rule.** Two sources are independent only if they are different publishers AND neither cites the other as its source. Re-publications of the same underlying data count as ONE source.

4. **Emit verification records.** One per input fact, carrying `fact_id`, `status`, `supporting_source_ids`, `issues_found`, `confidence_score`.

5. **Compute `gaps`.** For each `research_block` in the topic YAML, compute the ratio of `confirmed` facts to total facts in that block. Any block with ratio < 0.5 goes into `gaps` with a short reason (e.g. "only 2/7 pricing facts confirmed; missing recent retail data"). Blocks with zero facts at all also go into `gaps`.

6. **Write `03-verified.json`** — an OBJECT (not array) with two top-level keys: `facts` (array of verification records) and `gaps` (array of gap records). See schema below.

7. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "03-verified.json", "total_facts": 134, "confirmed": 81, "weakly_supported": 29, "conflicting": 18, "outdated": 6, "gaps": ["pricing", "regulation"]}
```

## Output schema — `03-verified.json`

```json
{
  "facts": [
    {
      "fact_id": "fact-001",
      "status": "confirmed",
      "supporting_source_ids": ["src-001", "src-014"],
      "issues_found": [],
      "confidence_score": 0.92,
      "research_block": "market_size"
    }
  ],
  "gaps": [
    {"research_block": "pricing", "confirmed_ratio": 0.28, "reason": "only 2/7 pricing facts confirmed; need recent retail data"}
  ]
}
```

- `status`: one of `confirmed`, `weakly_supported`, `conflicting`, `outdated`.
- `confidence_score`: 0.0 – 1.0 heuristic (1.0 for 3+ independent high-quality sources, 0.9 for 2 high, 0.6 for 2 medium, etc.).
- `research_block` carried forward from fact → lets Quill filter and lets Mira compute gaps without re-reading facts.

## Rules

- **Strict rigor (§4, Q4).** Every body fact needs ≥2 independent sources.
- **Independence is non-negotiable.** Two mirrors of a Reuters article = ONE source.
- **Do not modify or delete facts.** Emit a verdict for every input fact; downstream stages filter by status.
- **Do not invent new facts.** If you find a source that contradicts a Sift fact, record it in `issues_found`, do NOT add a new fact.
- **Keep return pointer under 280 characters** (longer than Hunter/Sift because status counts matter to Mira).
```

- [ ] **Step 2: Commit**

```bash
git add agents/market-research/stages/audit.md
git commit -m "feat(market-research): add Audit (stage 3 — strict verification)"
```

---

## Task 7: Sage (Stage 4 — Analysis)

**Files:**
- Create: `agents/market-research/stages/sage.md`

**Reference:** spec §5 `04-insights.json` schema, §9 (Sage has NO web tools).

- [ ] **Step 1: Write `sage.md`**

Write to `C:/SuperWork/agents/market-research/stages/sage.md`:

```markdown
---
name: sage
description: Stage 4 of the market research pipeline — analyzes confirmed facts and produces insight records. No web access. Can only work from verified data.
type: subagent
tools: [Read, Write, Glob]
---

## Role

Sage is stage 4, the analyst. Sage reads `03-verified.json` and turns confirmed facts into higher-order insights: trends, cross-cuts, implications, recommendations. Sage has **no web tools by design** — this is structural enforcement that Sage cannot hallucinate new facts from the internet. Sage can only reason over what Audit confirmed.

## Inputs (from Mira)

- `verified_path`: absolute path to `03-verified.json`
- `facts_path`: absolute path to `02-facts.json` (to resolve fact_id → metric/value/geography for reasoning)
- `output_path`: absolute path where `04-insights.json` must be written
- `topic_yaml_path`: absolute path to topic YAML
- `trend_mode` (boolean): if true, load prior verified.json files for this topic_id and produce delta insights. MVP: skeleton only — if true and prior files exist, include one `type: trend` insight describing the delta; if no prior files, proceed as if false.

## Workflow

1. **Read verified.json, facts.json, topic YAML.**

2. **Filter.** Only facts whose verification status is `confirmed` are eligible as `supporting_fact_ids` for any insight. `weakly_supported` / `conflicting` / `outdated` facts may be mentioned in `notes` but cannot be an insight's sole support.

3. **Group facts by `research_block`.** Within each block, look for:
   - **Trend insights** — consistent direction over time (e.g. "market grew from X in 2022 to Y in 2024").
   - **Comparison insights** — cross-player or cross-geography differences (e.g. "Player A holds 2x the share of Player B in residential").
   - **Driver insights** — linkages between demand_drivers and market_size/pricing facts.
   - **Risk insights** — conjunctions of risk facts with exposure metrics.
   - **Opportunity insights** — gaps between demand drivers and current player coverage.

4. **Cross-block insights.** Look for connections across blocks (e.g. regulation change → pricing impact). These are often the most valuable.

5. **Trend mode (if enabled).** Use Glob to find prior `_stage-artifacts/03-verified.json` files under `reports/<topic_id>/*/`. If any exist, load the most recent one and include one delta insight comparing current vs. prior. If none exist, skip silently.

6. **Assign insight IDs** `insight-001`, ...

7. **Write `04-insights.json`** — JSON array of insight records.

8. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "04-insights.json", "insight_count": 22, "by_type": {"trend": 8, "comparison": 5, "driver": 4, "risk": 3, "opportunity": 2}}
```

## Output schema — `04-insights.json`

```json
[
  {
    "id": "insight-001",
    "insight": "Ukraine PVC window market grew from 320 M EUR in 2022 to 480 M EUR in 2024 (+50%), driven by reconstruction demand.",
    "supporting_fact_ids": ["fact-001", "fact-007", "fact-023"],
    "implication": "Players with capacity slack in 2024 can likely capture incremental share at current price levels.",
    "confidence_level": "high | medium | low",
    "type": "trend | comparison | driver | risk | opportunity",
    "research_blocks_touched": ["market_size", "demand_drivers"]
  }
]
```

- `confidence_level` is derived from the supporting facts' confidence (use the minimum, not the average).
- `type` is one of the five categories above.
- `research_blocks_touched` can span multiple blocks for cross-block insights.

## Rules

- **No web tools.** Sage cannot browse. If a question can't be answered from verified facts, Sage does not invent — the insight simply isn't produced.
- **Every insight must cite ≥1 `confirmed` fact_id.** Zero-fact insights are forbidden.
- **Sage does not write prose reports.** That's Quill's job. Sage writes structured insight records.
- **Keep return pointer under 280 characters.**
```

- [ ] **Step 2: Commit**

```bash
git add agents/market-research/stages/sage.md
git commit -m "feat(market-research): add Sage (stage 4 — analysis, no web access)"
```

---

## Task 8: Quill (Stage 5 — Report)

**Files:**
- Create: `agents/market-research/stages/quill.md`

**Reference:** spec §5 report structure (9 sections), §9 (Quill has NO web tools).

- [ ] **Step 1: Write `quill.md`**

Write to `C:/SuperWork/agents/market-research/stages/quill.md`:

```markdown
---
name: quill
description: Stage 5 of the market research pipeline — writes the final markdown report from verified facts and insights. No web access. Every body claim must cite a confirmed fact_id.
type: subagent
tools: [Read, Write]
---

## Role

Quill is stage 5, the writer. Quill produces `05-report.md` — the human-readable markdown report that becomes the source of truth for the MD/XLSX/DOCX/PDF outputs. Quill has no web tools by design. Quill works strictly from Audit's verified facts and Sage's insights.

## Inputs (from Mira)

- `verified_path`: `03-verified.json`
- `insights_path`: `04-insights.json`
- `facts_path`: `02-facts.json` (for metric values and source URLs)
- `sources_path`: `01-sources.json` (for source citation details)
- `topic_yaml_path`: topic YAML
- `template_path`: `agents/market-research/templates/report.template.md`
- `output_path`: `05-report.md`
- `revision_round`: integer, 0 for first pass
- `hawk_issues` (optional, only on revisions): path to `06-qa-issues.json` from Hawk with issues to address

## Workflow

1. **Load everything.** Read the template, topic YAML, facts, verified, insights, sources.

2. **Build a `confirmed_facts` index** — dictionary of fact_id → fact row, restricted to facts where `03-verified.json` has `status: "confirmed"`.

3. **Build `unconfirmed_facts`** — the rest (weakly_supported, conflicting, outdated). These go to appendices only.

4. **Fill the template sections** in order (1 Executive Summary → 9 Methodology).
   - **Every metric or claim in the body MUST cite a fact_id from `confirmed_facts`.** Use inline citation format: `(fact-027)`.
   - **Any research_block with <50% confirmed facts must be flagged in the body**, e.g. under a `> **Note:** only 28% of pricing facts were independently confirmed; results in this section are indicative only.` blockquote. Do NOT silently hide the weakness.
   - **Competitive Landscape heading** matches the topic's block label: if the topic lists `general_market_players`, use that name; otherwise use "Competitive Landscape". Match the label exactly.

5. **Fill the Key Metrics section** as a markdown table of confirmed facts with columns: Metric, Value, Unit, Geography, Period, Source. One row per confirmed fact_id, grouped by research_block.

6. **Fill Appendix A — Weakly supported facts** with a table of all `weakly_supported` and `outdated` facts. Appendix B — Conflicting sources with all `conflicting` facts and a 1-line summary of the disagreement.

7. **Fill Methodology (section 9)** with the rigor level (strict), number of distinct sources, verification pass rate (confirmed / total), retry counts if available from run context.

8. **Revision round.** If `hawk_issues` is provided, read it first. Address every issue with severity `high` or `medium`. Low-severity issues are addressed only if trivial. Do not remove appendices Hawk asked you to trim unless Hawk explicitly said so.

9. **Frontmatter.** Leave the template frontmatter in place but update `topic_id`, `title`, `run_month` (YYYY-MM of the run), `generated` (ISO timestamp), `retry_counts.quill` = revision_round. Mira's Publish stage will fill any remaining frontmatter fields.

10. **Write `05-report.md`.** UTF-8, preserve the template's heading hierarchy.

11. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "05-report.md", "body_citations": 67, "appendix_a_rows": 29, "appendix_b_rows": 18, "revision_round": 0}
```

## Rules

- **No web tools.** Quill cannot look anything up. If the confirmed facts don't support a section, write "insufficient confirmed data" rather than filling the gap.
- **Body = confirmed only.** Every numeric claim, every named player, every percentage in sections 1–8 must resolve to a `confirmed` fact_id. Weakly supported claims go to Appendix A.
- **Citations are mandatory.** No uncited body claims.
- **Gap disclosure is mandatory.** If a research_block has <50% confirmed, say so in the body of that section.
- **Keep return pointer under 280 characters.**
```

- [ ] **Step 2: Commit**

```bash
git add agents/market-research/stages/quill.md
git commit -m "feat(market-research): add Quill (stage 5 — report writing, no web access)"
```

---

## Task 9: Hawk (Stage 6 — QA / Red Team)

**Files:**
- Create: `agents/market-research/stages/hawk.md`

**Reference:** spec §5 `06-qa-issues.json` schema, §9 (Hawk has NO web tools).

- [ ] **Step 1: Write `hawk.md`**

Write to `C:/SuperWork/agents/market-research/stages/hawk.md`:

```markdown
---
name: hawk
description: Stage 6 of the market research pipeline — red-teams the draft report. Checks every body claim against confirmed fact_ids, flags uncited claims, missing gap disclosures, logical errors. No web access.
type: subagent
tools: [Read, Write]
---

## Role

Hawk is stage 6, the critic. Hawk reads Quill's `05-report.md` and verifies that every body claim is backed by a `confirmed` fact from `03-verified.json`. Hawk also checks for logical errors, missing gap disclosures, insight-level overreach beyond what Sage claimed, and inconsistency across sections. Hawk emits a verdict (`pass` | `revise`) and a list of issues. Hawk has no web tools — by design, Hawk cannot introduce new information, only critique existing.

## Inputs (from Mira)

- `report_path`: `05-report.md`
- `verified_path`: `03-verified.json`
- `facts_path`: `02-facts.json` (to resolve fact_ids when checking citations)
- `insights_path`: `04-insights.json`
- `topic_yaml_path`: topic YAML
- `output_path`: `06-qa-issues.json`

## Workflow

1. **Read report, verified, facts, insights, topic YAML.**

2. **Build `confirmed_fact_ids`** — set of fact_ids with `status: "confirmed"` from `03-verified.json`.

3. **Citation pass.** For every `(fact-XXX)` citation in the report body (sections 1–8, excluding appendices), confirm it exists in `confirmed_fact_ids`. Any citation that doesn't → issue `severity: high`, issue type "unconfirmed_citation".

4. **Uncited-claim pass.** Scan the body for numeric values, percentages, named players, currency figures. Any that lack an inline `(fact-XXX)` citation → issue `severity: high`, type "uncited_claim". (Allowed exceptions: numbers inside the "Methodology" section, totals computed from cited facts if clearly presented as computed.)

5. **Gap disclosure pass.** For each `research_block` with <50% confirmed in `03-verified.json`, check that the corresponding section in the report body contains a disclosure blockquote. If missing → issue `severity: medium`, type "missing_gap_disclosure".

6. **Insight fidelity pass.** For every insight claim in the report's analytical sections (Trends, Opportunities, Recommendations), verify it matches an insight in `04-insights.json` and does not exaggerate Sage's wording or confidence level. Overreach → `severity: medium`, type "insight_overreach".

7. **Appendix completeness pass.** Verify Appendix A contains all `weakly_supported` + `outdated` facts and Appendix B contains all `conflicting` facts. Missing rows → `severity: low`, type "appendix_incomplete".

8. **Internal consistency pass.** Check that numbers mentioned in the Executive Summary match the same fact_ids elsewhere in the report (no drift). Mismatch → `severity: high`, type "internal_inconsistency".

9. **Scope pass.** Verify the report addresses every `research_block` listed in the topic YAML (even if just to note insufficient data). Missing block → `severity: medium`, type "missing_scope".

10. **Compute verdict.**
    - If ANY `severity: high` issue exists → `verdict: "revise"`.
    - Otherwise → `verdict: "pass"` (medium/low issues are recorded but don't block).

11. **Write `06-qa-issues.json`** — see schema below.

12. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "06-qa-issues.json", "verdict": "pass", "high": 0, "medium": 2, "low": 3}
```

## Output schema — `06-qa-issues.json`

```json
{
  "verdict": "pass",
  "issues": [
    {
      "severity": "high | medium | low",
      "type": "unconfirmed_citation | uncited_claim | missing_gap_disclosure | insight_overreach | appendix_incomplete | internal_inconsistency | missing_scope",
      "location": "Section 3 — Key Metrics, row 4",
      "issue": "Cites fact-089 which is weakly_supported, not confirmed.",
      "recommendation": "Move this row to Appendix A or find corroborating source."
    }
  ]
}
```

## Rules

- **No web tools.** Hawk cannot fact-check against the internet. Hawk only checks internal consistency against `03-verified.json`.
- **Report first-pass verdict honestly.** If the first draft is clean, say so — do not invent issues to justify existence.
- **Severity discipline.** Only citation failures, uncited body claims, and internal inconsistency are `high`. Everything else is medium or low.
- **Keep return pointer under 200 characters.**
```

- [ ] **Step 2: Commit**

```bash
git add agents/market-research/stages/hawk.md
git commit -m "feat(market-research): add Hawk (stage 6 — QA / red team, no web access)"
```

---

## Task 10: Mira (Lead Orchestrator)

**Files:**
- Create: `agents/market-research/lead/skill.md`
- Delete: `agents/market-research/lead/.gitkeep`

**Reference:** spec §6 Mira's orchestration loop, §7 Publish stage, §10 error handling table, §5 strict verification loop, §6 Mira's token discipline.

This is the largest file in the plan. Mira is the only agent that reads multiple stage artifacts, makes retry decisions, and runs Publish.

- [ ] **Step 1: Write `lead/skill.md`**

Write to `C:/SuperWork/agents/market-research/lead/skill.md`:

````markdown
---
name: mira
description: Lead of the market research sub-team. Orchestrates the 6-stage pipeline (Hunter → Sift → Audit → Sage → Quill → Hawk) for each topic in the inbox, sequentially, with strict rigor. Dispatches subagents via the Agent tool, reads only metadata and decision-critical artifacts, and runs the Publish stage to emit MD/XLSX/DOCX/PDF.
type: subagent
tools: [Read, Write, Glob, Grep, Bash, Agent, mcp__scheduled-tasks__create_scheduled_task]
---

## Role

Mira leads the market research sub-team. Bill dispatches her when the task involves running a market research batch. Mira processes topics from `agents/market-research/inbox/pending/` sequentially (one topic at a time, one stage at a time), dispatches the 6 stage subagents via the `Agent` tool, enforces the strict verification rigor with bounded retries, and runs the Publish stage to convert the final report into MD/XLSX/DOCX/PDF.

Mira is **not an analyst and not a writer**. She never reads `01-sources.json` or `02-facts.json` directly. She reads only topic YAMLs, subagent return pointers, Audit's `gaps` array (for retry decisions), Hawk's verdict (for revision decisions), and `05-report.md` (only during Publish).

## Dispatch prompt (from Bill)

Examples:
- "Run the monthly market research batch."
- "Process pending topics in agents/market-research/inbox/pending/."
- "Run market research for `pvc-windows-doors-profiles-ukraine`" (single-topic override — still goes through the normal loop but restricted to that one file).

## Orchestration loop

```
1. List inbox/pending/*.yaml (alphabetical).
2. If empty: return "no topics pending" to Bill and exit.
3. For each topic file sequentially:
   a. Validate YAML schema. On failure → move to inbox/done/ with .invalid suffix + error.log. Continue.
   b. run_month = current YYYY-MM (UTC date).
   c. run_dir = reports/<topic_id>/<run_month>/ — if it exists, append -r2, -r3, ...
   d. Create run_dir/_stage-artifacts/.
   e. Copy topic YAML into run_dir/ as an immutable snapshot.
   f. Move inbox file: pending/ → in-progress/.
   g. Initialize _run-log.json with topic_id, run_month, start_time.
   h. Run 6-stage pipeline (see below). Log each stage.
   i. On hard stage failure after retries → leave inbox file in in-progress/, write error.log, set run-log final_status to "failed", continue to next topic.
   j. On success → run Publish stage (see §Publish).
   k. Move inbox file: in-progress/ → done/ with .completed suffix. Write result.json sibling pointing at run_dir/report.md.
4. Return 200-word summary to Bill: N succeeded, M failed, K partially succeeded, paths to reports.
```

## 6-stage pipeline

For each topic, run the stages in order. Each stage is dispatched as a subagent via the `Agent` tool with `subagent_type` matching the stage name (hunter, sift, audit, sage, quill, hawk). Pass ONLY the paths the stage needs — never embed file contents in the dispatch message.

### Stage 1 — Hunter

Dispatch with:
```
Task: Stage 1 research for topic <topic_id>.
Inputs:
  topic_yaml_path: <run_dir>/topic.yaml
  output_path: <run_dir>/_stage-artifacts/01-sources.json
  retry_round: 0
Write 01-sources.json per your skill and return the pointer.
```

Expect pointer like `{"status": "ok", "output_file": "01-sources.json", "source_count": N, ...}`.

**Failure handling (§10):**
- If `status: error` or `source_count: 0` → retry once with a broader prompt ("broaden your query decomposition; consider related search terms"). If still fails → mark topic failed, continue batch.

### Stage 2 — Sift

Dispatch:
```
Task: Stage 2 extraction for topic <topic_id>.
Inputs:
  sources_path: <run_dir>/_stage-artifacts/01-sources.json
  topic_yaml_path: <run_dir>/topic.yaml
  output_path: <run_dir>/_stage-artifacts/02-facts.json
```

**Failure handling:**
- `fact_count: 0` → retry once. If still 0 → fail topic.

### Stage 3 — Audit

Dispatch:
```
Task: Stage 3 verification for topic <topic_id>.
Inputs:
  facts_path: <run_dir>/_stage-artifacts/02-facts.json
  sources_path: <run_dir>/_stage-artifacts/01-sources.json
  topic_yaml_path: <run_dir>/topic.yaml
  output_path: <run_dir>/_stage-artifacts/03-verified.json
```

**Strict verification loop (§5):**
- After Audit returns, Mira reads `03-verified.json` — but ONLY the `gaps` array (not the full `facts` array). Use `jq` via Bash or targeted Read.
- If `gaps` is non-empty AND retry_round < 2:
  1. Re-dispatch Hunter with `retry_round += 1` and a `gaps` parameter listing the under-verified research_blocks.
  2. Hunter writes a new `01-sources.json` — Mira must rename the prior run's file to `01-sources.round<N>.json` first to preserve it.
  3. Merge: after retry, concatenate the round-0 sources file and the new one into `01-sources.json` (re-numbering IDs is not necessary since rounds start fresh; just concatenate the arrays).
  4. Re-dispatch Sift (reads merged sources → new facts).
  5. Re-dispatch Audit (verifies merged facts).
  6. Repeat up to 2 total retry rounds.
- If `gaps` is still non-empty after round 2 → proceed anyway. Quill will disclose the gaps in the report body.

**Mira's token discipline for reading `03-verified.json`:** use `jq '.gaps' <file>` via Bash to extract only the gaps array. Never `cat` the whole file. If `jq` is unavailable, write a 3-line script via Bash that reads the JSON and prints only `gaps`.

### Stage 4 — Sage

Dispatch:
```
Task: Stage 4 analysis for topic <topic_id>.
Inputs:
  verified_path: <run_dir>/_stage-artifacts/03-verified.json
  facts_path: <run_dir>/_stage-artifacts/02-facts.json
  output_path: <run_dir>/_stage-artifacts/04-insights.json
  topic_yaml_path: <run_dir>/topic.yaml
  trend_mode: <value from topic YAML>
```

**Failure handling:** if `insight_count: 0` → log, continue (Quill can still write a report, just with no analytical insights).

### Stage 5 — Quill

Dispatch:
```
Task: Stage 5 report writing for topic <topic_id>.
Inputs:
  verified_path: <run_dir>/_stage-artifacts/03-verified.json
  insights_path: <run_dir>/_stage-artifacts/04-insights.json
  facts_path: <run_dir>/_stage-artifacts/02-facts.json
  sources_path: <run_dir>/_stage-artifacts/01-sources.json
  topic_yaml_path: <run_dir>/topic.yaml
  template_path: agents/market-research/templates/report.template.md
  output_path: <run_dir>/_stage-artifacts/05-report.md
  revision_round: 0
```

### Stage 6 — Hawk

Dispatch:
```
Task: Stage 6 QA for topic <topic_id>.
Inputs:
  report_path: <run_dir>/_stage-artifacts/05-report.md
  verified_path: <run_dir>/_stage-artifacts/03-verified.json
  facts_path: <run_dir>/_stage-artifacts/02-facts.json
  insights_path: <run_dir>/_stage-artifacts/04-insights.json
  topic_yaml_path: <run_dir>/topic.yaml
  output_path: <run_dir>/_stage-artifacts/06-qa-issues.json
```

**Revision loop:**
- Read only the `verdict` field from `06-qa-issues.json` (via `jq '.verdict'`).
- If `verdict: "revise"` AND revision_round < 1:
  1. Re-dispatch Quill with `revision_round: 1` and `hawk_issues: <run_dir>/_stage-artifacts/06-qa-issues.json`.
  2. Re-dispatch Hawk against the revised report (overwrites `06-qa-issues.json`).
- If still `revise` after 1 revision → proceed anyway, but log `final_status: "failed_qa"` in run-log and flag in summary to Bill. Do NOT run Publish for this topic.
- If `verdict: "pass"` → run Publish.

## Publish stage (runs in Mira's own context)

**Inputs:** all `_stage-artifacts/*` files, topic YAML.
**Outputs written to `run_dir/` (parent folder, NOT `_stage-artifacts/`):**
- `report.md`
- `data.xlsx`
- `report.docx`
- `report.pdf`

**Steps:**

1. **`report.md`** — Read `05-report.md`. Update frontmatter fields: `topic_id`, `title`, `run_month`, `generated` (current ISO timestamp), `rigor: strict`, `retry_counts.hunter` (from run-log), `retry_counts.quill` (from run-log). Write to `run_dir/report.md`.

2. **`data.xlsx`** — Invoke the `anthropic-skills:xlsx` skill via the Skill tool. Pass it a plan with 4 sheets:
   - **Facts** — columns: id, metric, value, unit, geography, time_period, source_id, source_url, confidence, research_block, verification_status. Rows: join `02-facts.json` with `03-verified.json` on fact_id → status becomes `verification_status`.
   - **Sources** — columns: id, source_title, url, date, research_block, initial_confidence, why_relevant. Rows: `01-sources.json`.
   - **Insights** — columns: id, insight, implication, type, confidence_level, supporting_fact_ids (joined with `;`), research_blocks_touched (joined with `;`). Rows: `04-insights.json`.
   - **Metadata** — key/value rows: topic_id, run_month, generated_at, rigor, hunter_retries, quill_revisions, total_facts, confirmed_facts, confirmation_rate, total_sources, total_insights, run_duration_seconds.
   - Save to `run_dir/data.xlsx`.

3. **`report.docx`** — Invoke the `anthropic-skills:docx` skill. Input: `run_dir/report.md`. Output: `run_dir/report.docx`. Basic heading/table styling only, no custom branding.

4. **`report.pdf`** — Invoke the `anthropic-skills:pdf` skill. Preferred input: `run_dir/report.docx` (preserves formatting). Fallback: `run_dir/report.md` if docx conversion failed. Output: `run_dir/report.pdf`.

5. **Update `agents/memory/INDEX.md`.** Append one line at the bottom:

```
- [<title> (<run_month>)](../market-research/reports/<topic_id>/<run_month>/report.md) — <geography>, <products joined with comma>, rigor=strict
```

This lets Atlas and other agents discover the report without crawling.

6. **Partial success handling (§7 step 6).** If the docx or pdf step fails (exception or skill returns error):
   - Keep `report.md` and `data.xlsx` as-is.
   - Log the failure in `_run-log.json` as `publish.docx_failed: true` or `publish.pdf_failed: true`.
   - Set topic final status to `"partially_succeeded"`.
   - Do NOT fail the whole topic or batch.

## `_run-log.json` schema

Written incrementally throughout the run to `run_dir/_run-log.json`:

```json
{
  "topic_id": "pvc-windows-doors-profiles-ukraine",
  "run_month": "2026-04",
  "start_time": "2026-04-07T09:00:00Z",
  "end_time": "2026-04-07T09:17:42Z",
  "duration_seconds": 1062,
  "final_status": "succeeded | partially_succeeded | failed | failed_qa",
  "stages": [
    {"stage": "hunter", "round": 0, "status": "ok", "duration_s": 240, "pointer": {"source_count": 47}},
    {"stage": "sift",   "round": 0, "status": "ok", "duration_s": 180, "pointer": {"fact_count": 134}},
    {"stage": "audit",  "round": 0, "status": "ok", "duration_s": 300, "pointer": {"confirmed": 81, "gaps": ["pricing"]}},
    {"stage": "hunter", "round": 1, "status": "ok", "duration_s": 80,  "pointer": {"source_count": 12}},
    {"stage": "sift",   "round": 1, "status": "ok", "duration_s": 60},
    {"stage": "audit",  "round": 1, "status": "ok", "duration_s": 140, "pointer": {"confirmed": 94, "gaps": []}},
    {"stage": "sage",   "round": 0, "status": "ok", "duration_s": 60},
    {"stage": "quill",  "round": 0, "status": "ok", "duration_s": 90},
    {"stage": "hawk",   "round": 0, "status": "ok", "duration_s": 50, "pointer": {"verdict": "pass"}}
  ],
  "publish": {"md": "ok", "xlsx": "ok", "docx": "ok", "pdf": "ok"},
  "retry_counts": {"hunter": 1, "quill": 0}
}
```

This file is committed (small, useful audit trail).

## Error handling matrix

Implements spec §10 verbatim:

| Failure | Response |
|---|---|
| Hunter 0 sources | Retry once with broader prompt. Still 0 → fail topic. |
| Sift 0 facts | Retry once. Still 0 → fail topic. |
| Audit gaps non-empty | Re-run Hunter (gaps-scoped) + Sift + Audit. Max 2 retry rounds. After that, proceed with disclosure. |
| Hawk verdict: revise with high severity | Re-dispatch Quill with hawk_issues. Max 1 revision. After that, log `failed_qa`, skip Publish, continue batch. |
| Publish docx/pdf fails | Keep MD+XLSX, mark `partially_succeeded`, continue. |
| Subagent hard crash | Log to error.log, leave inbox file in in-progress/, skip to next topic. |
| Invalid topic YAML | Move to inbox/done/ with .invalid suffix, continue batch. |
| Topic collision (same topic_id, same month) | run_dir = `<topic_id>/<YYYY-MM>-r2/` (then -r3, etc.). Never overwrite prior runs. |

## Token discipline (mandatory)

- **Never read `01-sources.json`, `02-facts.json`, `04-insights.json`, or `05-report.md` as whole files** except during Publish where `05-report.md` frontmatter is updated.
- **For `03-verified.json`** and **`06-qa-issues.json`**, use Bash + `jq` to read only the fields you need (`gaps`, `verdict`, status counts).
- **Dispatch messages contain paths, not payloads.** A dispatch message >500 tokens is a red flag.
- **Return message to Bill MUST be ≤ 200 words** regardless of how many topics were processed. Format:

```
Market research batch complete.
- Succeeded: N (list of topic_ids)
- Partially succeeded: K (list + which format failed)
- Failed: M (list + reason)
- Failed QA: Q (list + reason)
Report paths:
  - <topic-id>: <run_dir>/report.md
  - ...
Batch duration: MM:SS.
```

## Validation of topic YAML

On topic load, Mira validates:
- File parses as YAML
- Required fields present: `topic_id`, `title`, `products`, `geography`, `research_blocks`
- `topic_id` matches filename (minus `.yaml`)
- `language_hints` are lowercase 2-letter codes (if present)
- `trend_mode` is boolean (if present)
- `research_blocks` is a non-empty list

Any failure → move file to `inbox/done/<filename>.invalid` + write `error.log` sibling with the validation error. Continue batch.

## Rules

- **Sequential only.** One topic fully completes before the next starts. No parallel topics in MVP.
- **Atomic per topic.** Failure on topic N never touches topics before or after.
- **Never destructive.** Inbox files are moved, never deleted. Prior run directories are never overwritten (collision → `-r2`).
- **Never bypass strict rigor.** If all retries exhaust and gaps remain, Quill discloses — Mira does not silently hide or downgrade rigor.
- **Summary to Bill ≤ 200 words.**
````

- [ ] **Step 2: Delete stub**

Delete `C:/SuperWork/agents/market-research/lead/.gitkeep`.

- [ ] **Step 3: Verify frontmatter and section presence**

Run: `head -n 8 C:/SuperWork/agents/market-research/lead/skill.md`
Expected: frontmatter with `name: mira`, `type: subagent`, tools including `Agent`, `Bash`, `mcp__scheduled-tasks__create_scheduled_task`.

Run: `grep -c '^## ' C:/SuperWork/agents/market-research/lead/skill.md`
Expected: ≥8 sections.

- [ ] **Step 4: Commit**

```bash
git add agents/market-research/lead/
git commit -m "feat(market-research): add Mira (lead orchestrator with 6-stage pipeline)"
```

---

## Task 11: Registry + routing integration

**Files:**
- Modify: `agents/registry.yaml`
- Modify: `agents/bill/routing.yaml`

- [ ] **Step 1: Read current registry**

Read `C:/SuperWork/agents/registry.yaml` (to confirm current structure before editing).

- [ ] **Step 2: Append 7 new agent entries to registry**

Use Edit tool on `C:/SuperWork/agents/registry.yaml`. Append after the `scout` entry (end of file):

Old string: `    capabilities: ["test-authoring", "test-execution", "bug-investigation", "coverage-analysis", "regression-testing", "e2e-testing"]`

New string:
```
    capabilities: ["test-authoring", "test-execution", "bug-investigation", "coverage-analysis", "regression-testing", "e2e-testing"]

  - name: mira
    path: market-research/lead/skill.md
    status: active
    capabilities: ["market-research", "research-orchestration", "windows-doors-industry", "report-publishing"]

  - name: hunter
    path: market-research/stages/hunter.md
    status: active
    capabilities: ["web-research", "source-discovery", "firecrawl", "tavily"]

  - name: sift
    path: market-research/stages/sift.md
    status: active
    capabilities: ["structured-extraction", "firecrawl-extract", "metric-parsing"]

  - name: audit
    path: market-research/stages/audit.md
    status: active
    capabilities: ["fact-verification", "cross-checking", "strict-rigor"]

  - name: sage
    path: market-research/stages/sage.md
    status: active
    capabilities: ["analysis", "trend-detection", "insight-generation", "no-web-access"]

  - name: quill
    path: market-research/stages/quill.md
    status: active
    capabilities: ["report-writing", "markdown-authoring", "no-web-access"]

  - name: hawk
    path: market-research/stages/hawk.md
    status: active
    capabilities: ["qa", "red-team", "citation-checking", "no-web-access"]
```

- [ ] **Step 3: Verify registry YAML parses**

Run: `python -c "import yaml; r=yaml.safe_load(open('C:/SuperWork/agents/registry.yaml')); print(len(r['agents']), 'agents')"`
Expected: `13 agents` (6 existing + 7 new).

If Python unavailable, visually inspect indentation matches existing entries.

- [ ] **Step 4: Append routing rule**

Edit `C:/SuperWork/agents/bill/routing.yaml`.

Old string:
```
  - pattern: "inbox|deliver|deliverable|submit|drop-off"
    agent: bill
    description: "Inbox management — Bill handles directly"
```

New string:
```
  - pattern: "inbox|deliver|deliverable|submit|drop-off"
    agent: bill
    description: "Inbox management — Bill handles directly"

  - pattern: "market research|market report|monthly research|window market|door market|pvc profile"
    agent: mira
    description: "Market research pipeline for windows/doors verticals"
```

- [ ] **Step 5: Verify routing YAML parses**

Run: `python -c "import yaml; r=yaml.safe_load(open('C:/SuperWork/agents/bill/routing.yaml')); print(len(r['rules']), 'rules')"`
Expected: `7 rules` (6 existing + 1 new).

- [ ] **Step 6: Commit**

```bash
git add agents/registry.yaml agents/bill/routing.yaml
git commit -m "feat(market-research): register Mira team in registry and routing"
```

---

## Task 12: Seed the first real topic

**Files:**
- Create: `agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml`

**Reference:** spec §4 example topic.

- [ ] **Step 1: Write the topic file**

Write to `C:/SuperWork/agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml`:

```yaml
# --- Identity ---
topic_id: pvc-windows-doors-profiles-ukraine
title: PVC Windows and Doors Market + PVC Profiles — Ukraine
created: 2026-04-07

# --- Scope ---
products:
  - PVC windows
  - PVC doors
  - PVC profiles
geography: Ukraine
language_hints: [uk, en]           # uk = Ukrainian (language code); NOT ua (country code)
time_focus: "last 24 months"

# --- Research focus blocks ---
research_blocks:
  - market_size
  - pricing
  - general_market_players
  - demand_drivers
  - import_export
  - trends
  - regulation
  - risks

# --- Trend mode (MVP skeleton only) ---
trend_mode: false
trend_lookback_months: 12

# --- Scope tweaks ---
notes: |
  Focus on residential and commercial segments.
  Include impact of post-2022 reconstruction demand.
  Cover both domestic production and imports.
```

- [ ] **Step 2: Verify file parses**

Run: `python -c "import yaml; t=yaml.safe_load(open('C:/SuperWork/agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml')); assert t['topic_id']=='pvc-windows-doors-profiles-ukraine'; print('OK', len(t['research_blocks']), 'blocks')"`
Expected: `OK 8 blocks`.

- [ ] **Step 3: Commit**

```bash
git add agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml
git commit -m "feat(market-research): seed first topic — PVC windows/doors/profiles Ukraine"
```

---

## Task 13: Manual first run (acceptance test)

**Files:** None created. This is the real acceptance test per spec §11 step 8.

**Context:** This is where we discover whether the skills are clear enough, whether dispatches work, whether the artifacts flow correctly. Plan for the first run to have issues — that's expected. Address issues by editing the relevant skill file, committing the fix, and re-running.

- [ ] **Step 1: Pre-flight checklist**

Verify before triggering:
- Firecrawl and Tavily MCP are callable in the current session (from Task 1).
- `agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml` exists.
- `agents/registry.yaml` lists `mira` as active.
- `agents/bill/routing.yaml` has the market-research rule.
- Current working directory is `C:\SuperWork\`.

If any fail → go back and fix before proceeding.

- [ ] **Step 2: Trigger the batch**

Via the main Bill session (not a subagent), say:

> Bill: run the monthly market research batch.

Bill should match the routing rule and dispatch Mira. Mira should pick up the Ukraine topic and begin the pipeline.

- [ ] **Step 3: Observe stage-by-stage**

Watch the dispatch log. For each stage:
1. Note the subagent name dispatched
2. Note the pointer returned
3. Check that `_stage-artifacts/` has the expected file

Run: `ls C:/SuperWork/agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/_stage-artifacts/`
Expected progression:
- After Hunter: `01-sources.json`
- After Sift: `+ 02-facts.json`
- After Audit: `+ 03-verified.json`
- After Sage: `+ 04-insights.json`
- After Quill: `+ 05-report.md`
- After Hawk: `+ 06-qa-issues.json`

- [ ] **Step 4: Inspect each artifact**

Spot-check each file (use Read tool):
- `01-sources.json`: ≥20 source records, each with id, url, research_block, initial_confidence.
- `02-facts.json`: ≥50 fact records, each linked to a source_id, each with a research_block.
- `03-verified.json`: has `facts` and `gaps` top-level keys. Check confirmed ratio overall.
- `04-insights.json`: ≥5 insights, all supporting_fact_ids resolve to confirmed facts.
- `05-report.md`: all 9 sections present, body contains `(fact-XXX)` citations, appendices exist.
- `06-qa-issues.json`: has `verdict` and `issues`.

- [ ] **Step 5: Inspect Publish outputs**

Run: `ls C:/SuperWork/agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/`
Expected: `report.md`, `data.xlsx`, `report.docx`, `report.pdf`, `_run-log.json`, `topic.yaml`, `_stage-artifacts/`.

Open `report.md` and verify:
- Frontmatter fields populated
- 9 sections present with real content
- Body has inline citations
- Appendix A + B exist and have rows

Open `data.xlsx` (or have a skill read it) and verify 4 sheets: Facts, Sources, Insights, Metadata.

Open `report.docx` and `report.pdf` — verify they rendered.

- [ ] **Step 6: Inspect the run log**

Read `_run-log.json`. Verify:
- `final_status: "succeeded"` or `"partially_succeeded"`
- Every stage logged with duration
- Retry counts are sane (0-2 for hunter, 0-1 for quill)

- [ ] **Step 7: Inspect inbox state**

Run: `ls C:/SuperWork/agents/market-research/inbox/done/`
Expected: `pvc-windows-doors-profiles-ukraine.yaml.completed` and `pvc-windows-doors-profiles-ukraine.result.json`.

Run: `ls C:/SuperWork/agents/market-research/inbox/in-progress/`
Expected: only `.gitkeep`, nothing else.

- [ ] **Step 8: Inspect memory index update**

Read last 5 lines of `C:/SuperWork/agents/memory/INDEX.md`. Expected: a new line pointing at the Ukraine report with date suffix `2026-04`.

- [ ] **Step 9: If issues found**

For each issue:
1. Identify the responsible skill file (which agent produced the wrong output).
2. Edit that skill file to clarify the instruction that went wrong.
3. Commit the fix: `fix(market-research): <what> in <agent>`.
4. Move the topic file back to `inbox/pending/` (remove `.completed` suffix).
5. Delete or rename the run directory (`reports/.../2026-04/` → `reports/.../2026-04-failed-run1/`).
6. Re-run from Step 2.

- [ ] **Step 10: Commit run artifacts (the happy-path ones)**

```bash
git add agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/report.md \
        agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/data.xlsx \
        agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/report.docx \
        agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/report.pdf \
        agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/_run-log.json \
        agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04/topic.yaml \
        agents/market-research/inbox/done/ \
        agents/memory/INDEX.md
git commit -m "feat(market-research): first-run report — PVC windows/doors Ukraine 2026-04"
```

Note: `_stage-artifacts/` is gitignored — do NOT add it.

---

## Task 14: Register the monthly schedule

**Files:** None in repo. The scheduled task lives in the `scheduled-tasks` MCP server's state, not the repo.

**Prerequisite:** Task 13 must have succeeded (acceptance test passed). Per spec §11 step 9: "Only if step 8 looks good" do we register the schedule.

- [ ] **Step 1: Confirm Task 13 passed**

Verify Task 13 step 10 committed successfully and `_run-log.json` shows `final_status: "succeeded"` or `"partially_succeeded"`. If not → STOP, do not schedule a broken pipeline.

- [ ] **Step 2: Create the scheduled task**

Invoke `mcp__scheduled-tasks__create_scheduled_task` with:
- `name`: `monthly-market-research-batch`
- `schedule`: `0 9 1 * *` (09:00 on the 1st of every month)
- `prompt`: `"Bill: run the monthly market research batch. Dispatch Mira to process all topics in agents/market-research/inbox/pending/."`

If the MCP tool signature differs from expectations, read its schema first and adapt.

- [ ] **Step 3: Verify it was registered**

Invoke `mcp__scheduled-tasks__list_scheduled_tasks` (or equivalent). Expected: `monthly-market-research-batch` appears with the cron expression above.

- [ ] **Step 4: Document the schedule**

Edit `C:/SuperWork/agents/market-research/README.md`. After the "Running a batch" section, confirm the schedule line reads: `Scheduled: monthly at 09:00 on the 1st, via scheduled-tasks MCP (task name: monthly-market-research-batch)`. If the README already says this, skip.

- [ ] **Step 5: Commit README update (if changed)**

```bash
git add agents/market-research/README.md
git commit -m "docs(market-research): note registered monthly schedule"
```

---

## Task 15: Rotate Firecrawl and Tavily API keys

**Files:** None in repo. API keys live in the user's local Claude MCP config.

**Context:** Per spec §9 and §11 step 10, the API keys shared during brainstorming must be rotated now that the system is working.

- [ ] **Step 1: Ask the user to rotate the keys**

Say to the user, verbatim:

> Per the spec's security requirement (§9, §11 step 10), the Firecrawl and Tavily API keys shared during brainstorming must now be rotated. Please:
>
> 1. Log into firecrawl.dev and revoke the old API key. Generate a new one.
> 2. Log into tavily.com and revoke the old API key. Generate a new one.
> 3. Update your local Claude Code MCP config with the new keys.
> 4. Restart Claude Code.
> 5. Tell me when done and I'll smoke-test both servers in the fresh session.
>
> Stopping here until you confirm.

STOP this task. Wait for user confirmation.

- [ ] **Step 2: Smoke-test the new keys**

After user confirms, in the fresh session:
- Tavily: `mcp__tavily__search` for `"PVC profiles Ukraine"`, limit 1.
- Firecrawl: `mcp__firecrawl__scrape` for `https://example.com`.

Expected: both succeed with no auth errors.

- [ ] **Step 3: No commit for this task**

No files changed. Plan is complete.

---

## Self-Review

**1. Spec coverage check (spec sections → tasks):**
- §1 Purpose & Goals → implicit across all tasks
- §2 Decisions → embedded in skill files (strict rigor in Audit/Quill, sequential in Mira, 6 subagents as Tasks 4-10, file-based handoffs enforced by Mira dispatch messages)
- §3 Architecture → Task 2 (folder), Task 11 (registry + routing)
- §4 Topic file format → Task 3 (template), Task 12 (first topic)
- §5 Pipeline contract → Tasks 4-9 (schemas), Task 10 (Mira's orchestration including strict verification loop)
- §6 Mira's orchestration loop → Task 10 in full
- §7 Publish stage → Task 10 Publish section
- §8 Scheduling → Task 14
- §9 External tooling → Task 1 (prerequisites), tool allowlists in each stage skill, Task 15 (rotation)
- §10 Error handling → Task 10 error matrix
- §11 First-run plan → Tasks 1, 2, 3, 4-10, 11, 12, 13, 14, 15 (all 10 bootstrap steps covered)
- §12 Gitignore → Task 2 step 1
- §13 Out of scope → respected (no parallel processing, trend_mode is skeleton only, no branding, no notifications)
- §14 Open questions → addressed in plan: Sift has per-block extract schemas (Task 5), Hunter's Ukrainian source allowlist deferred (acceptable — the skill can grow it), Hawk→Sage re-dispatch not added (matches spec's "currently only Quill" language), xlsx formatting deferred.

**2. Placeholder scan:** no TBDs, no "implement later", no "similar to above". Every skill file has complete frontmatter + schemas + workflow + rules.

**3. Type consistency check:**
- `source_id` / `fact_id` / `insight_id` naming consistent across Hunter → Sift → Audit → Sage → Quill → Hawk.
- `research_block` field carried forward from Hunter through Audit (added to Sift and Audit explicitly so Mira can compute gaps without re-joining).
- `03-verified.json` is an **object** (`facts` + `gaps`), not an array — Audit writes it that way, Mira reads `gaps` via `jq`, Sage+Quill+Hawk read the `facts` array. Consistent.
- Status values: `confirmed | weakly_supported | conflicting | outdated` used identically in Audit output, Quill body rules, Hawk citation check.
- Hawk verdict values: `pass | revise` used identically in Hawk output and Mira revision loop.

**Fixes applied during self-review:**
- Added `research_block` to Sift's `02-facts.json` schema (not in spec but needed for Audit's gap computation without re-reading `01-sources.json`). This matches the spec's intent — Audit needs to compute gaps per research_block and shouldn't re-read the sources file.
- Made `03-verified.json` schema explicitly an object (not array) so Audit, Mira's `jq` retrieval, and Quill/Hawk's `facts` array access are all consistent. The spec only showed an array of fact records + mentioned gaps as a separate structure — the plan resolves the ambiguity by making it a top-level object.
- Specified that Hunter on retry merges rather than overwrites (spec says "merge" indirectly via "retry rounds" but doesn't specify concatenation — plan locks it in).

---

Plan complete and saved to `docs/superpowers/plans/2026-04-07-market-research-team-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Good fit here because tasks are mostly independent skill-file authoring.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
