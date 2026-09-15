# Market Research Team — Design Spec

**Date:** 2026-04-07
**Status:** Approved (brainstorming complete, awaiting implementation plan)
**Owner:** Bill (orchestrator); Mira (new market research lead)

## 1. Purpose & Goals

Build a new sub-team inside the existing Bill agent framework that performs monthly, high-rigor market research on the windows and doors industry — producing fact-checked analytical reports on topics such as PVC/wood/aluminum windows and doors, PVC profiles, import/export flows, pricing, and market trends across specific countries.

The team runs on a monthly cadence (via Claude Code's `scheduled-tasks` MCP server), processes topics supplied through an inbox drop, and delivers multi-format reports (Markdown + XLSX + DOCX + PDF).

**Non-goals for MVP:**
- Parallel multi-topic processing
- Full longitudinal trend mode implementation (skeleton only)
- Custom branding on exports
- Notifications / dashboards / cross-topic analytics
- Automated topic backlog (manual inbox drop only)

## 2. Decisions Locked During Brainstorming

| # | Decision | Value |
|---|---|---|
| Q1 | Team architecture | **C** — Hybrid: one named lead ("Mira") who dispatches 6 specialized subagents |
| Q2 | Topic source | **C** — Manual drop into `inbox/pending/` |
| Q2b | Parallelism | **i** — Sequential, one topic at a time |
| Q3 | Output formats | MD (source) + XLSX (data) + DOCX + PDF |
| Q4 | Verification rigor | **A** — Strict: every fact requires ≥2 sources or is excluded from the report body |
| Q5 | External research tooling | **B** — Firecrawl (fetch) + Tavily (discovery) via MCP |
| Q6 | Scheduling | Claude Code `scheduled-tasks` MCP server (cron `0 9 1 * *`) |
| Q7 | Internal pipeline structure | **A** — 6 real subagents dispatched via `Agent` tool, file-based handoffs |
| Q8 | Trend continuity | **D** — Opt-in per topic via `trend_mode: true` field (MVP ships skeleton only) |
| Q9 | Naming | Mira / Hunter / Sift / Audit / Sage / Quill / Hawk |

## 3. High-Level Architecture

### Folder layout

```
C:\SuperWork\agents\market-research\
├── lead/
│   └── skill.md                    # Mira (orchestrator)
├── stages/
│   ├── hunter.md                   # Research subagent
│   ├── sift.md                     # Extraction subagent
│   ├── audit.md                    # Verification subagent
│   ├── sage.md                     # Analyst subagent
│   ├── quill.md                    # Report subagent
│   └── hawk.md                     # QA/Red Team subagent
├── inbox/
│   ├── pending/                    # User drops topic files here
│   ├── in-progress/                # Mira moves them here while running
│   └── done/                       # Archived after publish
├── reports/
│   └── <topic-id>/
│       └── YYYY-MM/
│           ├── report.md           # Source of truth (committed)
│           ├── data.xlsx           # Structured data (committed)
│           ├── report.docx         # Shareable format (committed)
│           ├── report.pdf          # Shareable format (committed)
│           ├── _run-log.json       # Audit trail (committed)
│           └── _stage-artifacts/   # Intermediate JSON handoffs (gitignored)
├── templates/
│   ├── topic.template.yaml
│   └── report.template.md
├── .gitignore
└── README.md
```

### Top-level flow

1. Bill receives "run market research batch" (from scheduled task or user)
2. Bill dispatches → **Mira**
3. Mira reads `inbox/pending/`, processes one topic at a time, sequentially
4. For each topic, Mira runs the 6-stage pipeline by dispatching 6 subagents in order via the `Agent` tool
5. Stages communicate **only via files** in `_stage-artifacts/`. Subagents return to Mira a 1-line pointer (`{"status": "ok", "output_file": "02-facts.json", "row_count": 47}`), never the full payload.
6. Final Publish step runs in Mira's own context — converts MD → XLSX/DOCX/PDF and archives the inbox file

### Integration with existing Bill team

**`agents/registry.yaml`** gains 7 new `active` entries: `mira`, `hunter`, `sift`, `audit`, `sage`, `quill`, `hawk`.

**`agents/bill/routing.yaml`** gains one new rule:

```yaml
- pattern: "market research|market report|monthly research|window market|door market"
  agent: mira
  description: "Market research pipeline for windows/doors verticals"
```

## 4. Inbox Topic File Format

Topic files are YAML. Filename = topic ID. Mira processes them in alphabetical order (prefix with `01-`, `02-` to force priority).

### Example: `pvc-windows-doors-profiles-ukraine.yaml`

```yaml
# --- Identity ---
topic_id: pvc-windows-doors-profiles-ukraine
title: PVC Windows and Doors Market + PVC Profiles — Ukraine
created: 2026-04-07

# --- Scope ---
products:                           # list when topic covers multiple
  - PVC windows
  - PVC doors
  - PVC profiles
geography: Ukraine
language_hints: [uk, en]            # ISO 639-1 codes. uk = Ukrainian (UA is country code, do not use)
time_focus: "last 24 months"

# --- Research focus blocks (drives Hunter's queries) ---
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
trend_mode: false                   # true = load prior reports for delta analysis (MVP: skeleton only)
trend_lookback_months: 12

# --- Optional: scope tweaks ---
notes: |
  Focus on residential and commercial segments.
  Include impact of post-2022 reconstruction demand.
  Cover both domestic production and imports.
```

### Field rules

- `topic_id`: stable key. Same topic next month reuses the same ID so reports stack under one folder.
- `products`: either a single string or a list.
- `language_hints`: ISO 639-1 language codes, not country codes. Passed to Tavily and Firecrawl to steer queries toward the correct language. **Important:** Ukrainian is `uk`; `ua` is the country code and will fail silently.
- `research_blocks`: maps directly to the structure of the final report. Mira hands this to Hunter as the query decomposition.
- `notes`: only free-form field; used by Mira to constrain or focus the pipeline.
- `trend_mode`: opt-in. When `true`, Sage loads prior `03-verified.json` files for the same `topic_id` up to `trend_lookback_months` back and produces delta/trend insights.

### Lifecycle

- User drops file → `inbox/pending/`
- Mira picks up → moves to `inbox/in-progress/`
- Pipeline succeeds → file moves to `inbox/done/` with `.completed` suffix + `result.json` sibling pointing at final report folder
- Pipeline fails → file stays in `in-progress/` with `error.log` sibling
- Invalid YAML → file moves to `inbox/done/` with `.invalid` suffix + `error.log` sibling; batch continues

## 5. The 6-Stage Pipeline Contract

All stages write to `reports/<topic-id>/<YYYY-MM>/_stage-artifacts/`. Subagents return only a pointer to Mira.

| # | Stage | Subagent | Reads | Writes | Tools allowed |
|---|---|---|---|---|---|
| 1 | Research | **Hunter** | `topic.yaml` | `01-sources.json` | `tavily`, `firecrawl`, Read, Write |
| 2 | Extraction | **Sift** | `01-sources.json`, `topic.yaml` | `02-facts.json` | `firecrawl` (`/extract` schema mode), Read, Write |
| 3 | Verification | **Audit** | `02-facts.json` | `03-verified.json` | `tavily`, `firecrawl`, Read, Write |
| 4 | Analysis | **Sage** | `03-verified.json`, optional prior `verified.json` if `trend_mode: true` | `04-insights.json` | Read, Write (NO web access) |
| 5 | Report | **Quill** | `03-verified.json`, `04-insights.json`, `topic.yaml` | `05-report.md` | Read, Write (NO web access) |
| 6 | QA | **Hawk** | `05-report.md`, `03-verified.json`, `04-insights.json` | `06-qa-issues.json` | Read, Write (NO web access) |

**Tool lockout is structural, not advisory:** Sage/Quill/Hawk have no web tools in their frontmatter. They cannot hallucinate new facts from the web — they can only work with what passed verification.

### File schemas

#### `01-sources.json` — Hunter output

```json
[
  {
    "id": "src-001",
    "source_title": "...",
    "url": "...",
    "key_fact": "...",
    "date": "2025-09-12",
    "research_block": "market_size",
    "why_relevant": "...",
    "initial_confidence": "high"
  }
]
```

#### `02-facts.json` — Sift output (one row per metric)

```json
[
  {
    "id": "fact-001",
    "metric": "PVC window market size",
    "value": 480,
    "unit": "M EUR",
    "geography": "Ukraine",
    "time_period": "2024",
    "source_id": "src-001",
    "source_url": "...",
    "confidence": "high",
    "notes": "..."
  }
]
```

#### `03-verified.json` — Audit output

```json
[
  {
    "fact_id": "fact-001",
    "status": "confirmed",
    "supporting_source_ids": ["src-001", "src-014"],
    "issues_found": [],
    "confidence_score": 0.92
  }
]
```

Status values: `confirmed` (≥2 independent sources, no conflict), `weakly_supported` (1 source), `conflicting` (sources disagree), `outdated` (only stale sources available).

Audit additionally emits a `gaps` array of research_blocks that fell short of strict rigor, which Mira reads to decide on retries.

#### `04-insights.json` — Sage output

```json
[
  {
    "id": "insight-001",
    "insight": "...",
    "supporting_fact_ids": ["fact-001", "fact-007"],
    "implication": "...",
    "confidence_level": "high",
    "type": "trend"
  }
]
```

#### `06-qa-issues.json` — Hawk output

```json
{
  "verdict": "pass",
  "issues": [
    {"severity": "low", "issue": "...", "explanation": "...", "recommendation": "..."}
  ]
}
```

### Strict verification loop

- After **Audit**: if *any* `research_block` from the topic YAML has <50% of its facts marked `confirmed`, Mira re-dispatches **Hunter** with a refined query list drawn from Audit's `gaps` array (scoped to the under-verified blocks). Maximum **2 retry rounds** per topic to bound cost.
- After **Hawk**: if `verdict == "revise"` and any issue is `severity: high`, Mira re-dispatches **Quill** with the issues list. Maximum **1 revision round**.
- All retries logged in `_run-log.json`.

### Report structure (Quill's output)

Per the original orchestrator prompt, the final report has these sections:

1. Executive Summary
2. Market Overview
3. Key Metrics
4. Competitive Landscape (or "General Market Players" — matches the topic's research_blocks label)
5. Trends & Drivers
6. Risks
7. Opportunities
8. Recommendations
9. Methodology

Every metric in the report body must cite a `fact_id` that carries `status: confirmed` in `03-verified.json`. Weakly supported and conflicting facts go to an appendix, never the body.

## 6. Mira's Orchestration Loop

```
1. List inbox/pending/*.yaml → alphabetical order
2. If empty: return "no topics pending" to Bill and exit.
3. For each topic file (sequentially):
   a. Validate YAML against topic schema. On failure → move to inbox/done/
      with .invalid suffix + error.log, continue to next topic.
   b. Determine run_month = current YYYY-MM.
   c. Create reports/<topic_id>/<run_month>/_stage-artifacts/.
   d. Copy topic.yaml into the run directory (immutable snapshot).
   e. Move inbox file: pending/ → in-progress/
   f. Run 6-stage pipeline. Log each stage to _run-log.json.
   g. If any stage fails after retries → leave inbox file in in-progress/
      with error.log, move to next topic (don't crash the batch).
   h. If pipeline succeeds → run Publish stage.
   i. Move inbox file: in-progress/ → done/ with .completed suffix.
4. After all topics processed: return summary to Bill
   (X succeeded, Y failed, paths to reports).
```

### Properties

- **Sequential** (Q2b): one topic fully completes before the next starts.
- **Atomic per topic:** a failure on topic N does not affect topics before or after.
- **Collision handling:** if the same `topic_id` runs twice in the same month, the second run creates `YYYY-MM-r2/` instead of overwriting `YYYY-MM/`.
- **Never destructive:** inbox files are moved, never deleted; all stage artifacts kept for audit.

### Mira's own token discipline

- Mira never reads `01-sources.json` or `02-facts.json` directly. Those are subagent-to-subagent handoffs.
- Mira reads only: topic YAML, `_run-log.json`, subagent return pointers, Audit's `gaps` array for retry decisions, `06-qa-issues.json` only if verdict is `revise`, and `05-report.md` during the Publish stage.
- The batch summary Mira returns to Bill is ≤ 200 words regardless of topic count.

## 7. Publish Stage

Runs in Mira's own context after the 6-stage pipeline succeeds. Mechanical file conversion — not a subagent.

**Inputs:** `05-report.md`, `02-facts.json`, `03-verified.json`, `01-sources.json`, `04-insights.json`, `topic.yaml`
**Outputs:** `report.md`, `data.xlsx`, `report.docx`, `report.pdf` — all at `reports/<topic-id>/<run_month>/` (parent folder, not `_stage-artifacts/`)

### Steps

1. **`report.md`** — Copy `05-report.md` up one level. Inject YAML frontmatter with topic metadata, run date, rigor level, retry counts.

2. **`data.xlsx`** — Invoke `anthropic-skills:xlsx` to generate a workbook with 4 sheets:
   - **Facts** — rows from `02-facts.json` joined with `verification_status` from `03-verified.json`
   - **Sources** — rows from `01-sources.json`
   - **Insights** — rows from `04-insights.json`
   - **Metadata** — topic_id, run_month, run timestamp, rigor, stage retry counts, run duration
   - Column headers match the JSON schemas exactly.

3. **`report.docx`** — Invoke `anthropic-skills:docx` with `report.md` as input. Apply a simple professional style (headings, tables). No custom branding for MVP.

4. **`report.pdf`** — Invoke `anthropic-skills:pdf` to render from `report.docx` (preserves formatting best). Fallback: render from `report.md` if the docx conversion fails.

5. **Update `agents/memory/INDEX.md`** — Append one keyword-indexed line pointing at the new report so Atlas and other agents can discover it without crawling.

6. **Partial success handling:** if the docx/pdf conversion fails, the MD and XLSX are still kept, the topic is marked "partially succeeded," and the failure is logged in `_run-log.json`. The batch continues.

## 8. Scheduling

Via the `scheduled-tasks` MCP server (native Claude Code feature):

```
name:     monthly-market-research-batch
schedule: 0 9 1 * *                  # 09:00 on the 1st of every month
prompt:   "Bill: run the monthly market research batch.
           Dispatch Mira to process all topics in
           agents/market-research/inbox/pending/."
```

- Empty inbox → cheap no-op run
- Manual trigger anytime: "Bill, run the market research batch"
- Task is **not** registered until a manual first run has been validated (see §11)

## 9. External Tooling (Firecrawl + Tavily)

**MCP config lives in the local Claude Code settings**, not in the repo. The repo adds an explicit `.gitignore` rule as belt-and-suspenders.

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "<redacted>" }
    },
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": { "TAVILY_API_KEY": "<redacted>" }
    }
  }
}
```

### Tool allocation per stage

| Stage | tavily | firecrawl | Rationale |
|---|---|---|---|
| Hunter | ✅ | ✅ | Discovery + initial fetch |
| Sift | ❌ | ✅ (`/extract`) | Schema-driven structured extraction only |
| Audit | ✅ | ✅ | Needs to find additional sources to cross-check |
| Sage | ❌ | ❌ | Verified data only — no web |
| Quill | ❌ | ❌ | Verified insights only — no web |
| Hawk | ❌ | ❌ | Critique existing report — no web |

### Security

The Firecrawl and Tavily API keys shared during brainstorming **must be rotated** once the MCP config is set up locally (logged in §11 step 10). The keys are never committed to the repo.

## 10. Error Handling & Observability

| Failure mode | Mira's response |
|---|---|
| Hunter returns 0 sources | Retry once with broadened `research_blocks`. If still 0 → fail topic. |
| Sift output empty | Retry once. If still empty → fail topic. |
| Audit finds <50% `confirmed` facts in any `research_block` | Re-dispatch Hunter with Audit's `gaps` scoped to the under-verified blocks (up to 2 retry rounds). |
| Hawk `verdict: revise` with high-severity issues | Re-dispatch Quill with the issues (1 revision round). |
| Publish docx/pdf step fails | Keep MD + XLSX, log failure, mark topic partially succeeded, continue batch. |
| Subagent hard-crashes | Log to `error.log`, leave topic in `in-progress/`, skip to next topic in batch. |
| Invalid topic YAML | Move to `inbox/done/` with `.invalid` suffix, continue batch. |

**`_run-log.json`** captures per run: stage timings, retry counts, final verdict, token estimates if available, final verdict per topic. Written to `reports/<topic-id>/<run_month>/_run-log.json` and committed (small, useful audit trail).

## 11. First-Run Plan

Bootstrap order for implementation:

1. **Prerequisites** — Install `firecrawl-mcp` and `tavily-mcp`, add to local Claude MCP config with the provided keys, verify both callable.
2. **Create folder skeleton** — `agents/market-research/` with all subdirs, `.gitignore`, `README.md`.
3. **Write the 7 skill files** — Mira + 6 stage subagents, each with explicit schemas in the frontmatter, tool allowlists, and strict role rules carried over from the original orchestrator prompt.
4. **Update `agents/registry.yaml`** — Add 7 entries.
5. **Update `agents/bill/routing.yaml`** — Add the market-research rule pointing to Mira.
6. **Create templates** — `topic.template.yaml`, `report.template.md`.
7. **Drop the first real topic** — The PVC windows/doors/profiles Ukraine file (§4) into `inbox/pending/` as the inaugural test.
8. **Manual first run** — Before scheduling, invoke "Bill: run market research batch" manually. Watch the pipeline execute. Inspect every artifact: sources JSON, facts JSON, verified JSON, insights JSON, report MD, final MD/XLSX/DOCX/PDF. This is the acceptance test.
9. **Only if step 8 looks good:** register the scheduled task for the 1st of each month via `scheduled-tasks` MCP.
10. **Post-run hygiene (mandatory):** rotate the Firecrawl and Tavily API keys shared during brainstorming, update the local MCP config with the new keys, verify still callable.

## 12. Gitignore Additions

New file `agents/market-research/.gitignore`:

```
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

Committed artifacts per run: `report.md`, `data.xlsx`, `report.docx`, `report.pdf`, `_run-log.json`, and any `topic.yaml` snapshot.

## 13. Out of Scope (Deliberately YAGNI)

- Parallel multi-topic processing
- Full trend mode implementation (Sage's prior-report loader is stubbed; implemented when the first topic actually sets `trend_mode: true`)
- Custom branding / letterhead on DOCX/PDF exports
- Email/Slack/webhook notifications on batch completion
- Cross-topic analytics dashboard
- Automated topic backlog (Option B from Q2) — can be added later as a file that pre-populates `inbox/pending/` on a separate schedule; the pipeline itself requires no changes to support it
- Non-windows/doors verticals (the team is purposely scoped to this domain; broader scope would likely need different research_blocks and different sources)

## 14. Open Questions for Implementation

These are things the implementation plan (next step) needs to resolve, not design decisions:

- Exact Firecrawl `/extract` schema for Sift to call (likely one schema per `research_block` type)
- Which concrete Ukrainian-language sources Hunter should prioritize as high-confidence (can seed a simple allowlist in Hunter's skill.md, grown over time)
- Whether Hawk's `verdict: revise` should also allow re-dispatching Sage (currently only Quill is re-dispatched) — may add if first runs show analysis-level issues
- Exact column formatting for `data.xlsx` (widths, number formats) — cosmetic, defer to Quill/Publish implementation
