# Market Research Team — Session Handoff

**Last updated:** 2026-04-08 (second blocker discovered AND resolved — see correction note below)

---

## CORRECTION NOTE — 2026-04-08 (later same day)

An earlier edit on 2026-04-08 marked the Task 13 blocker as "CLEARED — all 7 subagents registered." That cleared the **wrong** blocker. There were actually two layered blockers:

1. **Registration-level blocker (real, now cleared):** All 7 subagents (mira, hunter, sift, audit, sage, quill, hawk) needed to be registered as CC subagents under `.claude/agents/`. This was done and is genuinely resolved.

2. **Harness-level blocker (discovered during live test, now resolved differently):** The Claude Code harness **forbids nested Task dispatch**. When Bill dispatches Mira via the Task tool, Mira cannot then dispatch the 6 stage subagents — the harness returns `No such tool available: Task` at runtime, even though Mira's frontmatter declares the Task tool. This is a structural limitation: subagents cannot spawn other subagents.

   **Resolution:** Mira was collapsed from a CC subagent into a **skill** that Bill loads and runs himself. Bill is now the orchestrator-of-orchestrators for market research runs. He dispatches the 6 stage subagents directly (top-level Task dispatch works fine). The 6 stage subagents are unchanged and still registered under `.claude/agents/`.

   **Files touched in the resolution:**
   - Deleted: `C:\SuperWork\.claude\agents\mira.md`
   - Normalized: `C:\SuperWork\agents\market-research\lead\skill.md` (now the authoritative playbook; `type: skill`, "Task tool" wording, Bill-as-driver framing, historical note prepended)
   - Updated: `C:\SuperWork\agents\registry.yaml` (Mira entry: removed `cc_subagent` flags, added `type: skill` + `invoked_by: bill`)
   - Updated: `C:\SuperWork\agents\bill\routing.yaml` (market-research rule: agent is now `bill` with `skill:` pointing at the playbook)

**Task 13 acceptance run is still pending but is now actually unblocked.** Bill can immediately load the playbook at `agents/market-research/lead/skill.md` and run the PVC Ukraine loop end-to-end, dispatching hunter/sift/audit/sage/quill/hawk himself.

---

**Original last-updated:** 2026-04-08 (Task 13 blocker cleared) — superseded by correction note above
**Spec:** `docs/superpowers/specs/2026-04-07-market-research-team-design.md`
**Plan:** `docs/superpowers/plans/2026-04-07-market-research-team-implementation.md`
**Purpose:** Let the next Claude Code session pick up exactly where we left off without re-reading the full plan or re-deriving context.

---

## TL;DR for the next session

**Where we are:** All scaffolding and agent skill files are written. 12 of 15 tasks are complete. The next step is **Task 13 — the manual first-run acceptance test**, which exercises the entire Hunter → Sift → Audit → Sage → Quill → Hawk → Publish pipeline end-to-end against the seeded Ukraine PVC windows/doors topic.

**Blocker to clear first:** ~~Claude Code must be restarted so the Firecrawl and Tavily MCP servers (configured in `C:\Users\andre\.claude.json` at the end of session 2) become callable.~~ **CLEARED 2026-04-08** — all 7 market-research subagents (mira, hunter, sift, audit, sage, quill, hawk) are registered and callable via the Task tool in the current Claude Code session. Firecrawl and Tavily MCP servers are live. Task 13 is unblocked and ready to run.

**What Bill should do next:** Load the Mira playbook skill at `agents/market-research/lead/skill.md` and run the orchestration loop directly, dispatching hunter/sift/audit/sage/quill/hawk via the Task tool stage-by-stage. (Mira is no longer a subagent — see Correction Note above.)

---

## Project context (1-paragraph version)

Building a sub-team inside the Bill agent framework at `C:\SuperWork\agents\market-research\`. The team is Mira (lead orchestrator) + 6 specialized stage subagents (Hunter, Sift, Audit, Sage, Quill, Hawk). Mira dispatches the stages sequentially via the `Agent` tool for each topic in the inbox; stages communicate only via JSON files in `_stage-artifacts/` and return 1-line pointers to Mira. Tool lockout is structural — Sage/Quill/Hawk have no web tools in their frontmatter, so they cannot hallucinate beyond what Audit verified. Rigor is strict: every body fact in the final report needs >=2 independent sources marked `confirmed` by Audit.

---

## Task status

| #  | Task                                         | Status      | Notes |
|----|----------------------------------------------|-------------|-------|
| 1  | Verify Firecrawl + Tavily MCP callable       | ✅ done      | MCP servers live as of 2026-04-08; subagents registered and callable. |
| 2  | Scaffold folders, `.gitignore`, `README.md`  | ✅ done      | |
| 3  | Topic + report templates                     | ✅ done      | |
| 4  | Hunter skill (stage 1 research)               | ✅ done      | |
| 5  | Sift skill (stage 2 extraction)               | ✅ done      | |
| 6  | Audit skill (stage 3 verification)            | ✅ done      | |
| 7  | Sage skill (stage 4 analysis)                 | ✅ done      | |
| 8  | Quill skill (stage 5 report writing)          | ✅ done      | |
| 9  | Hawk skill (stage 6 QA / red team)            | ✅ done      | |
| 10 | Mira lead orchestrator skill                  | ✅ done      | |
| 11 | Register 7 agents in registry + 1 routing rule| ✅ done      | `agents/registry.yaml` + `agents/bill/routing.yaml` updated |
| 12 | Seed first topic (PVC Ukraine)                | ✅ done      | `inbox/pending/pvc-windows-doors-profiles-ukraine.yaml` |
| 13 | Manual first run (acceptance test)            | ⏳ pending   | **Next up — UNBLOCKED 2026-04-08.** All 7 subagents registered and callable; MCP live. |
| 14 | Register monthly scheduled task               | ⏳ pending   | Only after Task 13 passes. |
| 15 | Rotate Firecrawl + Tavily API keys            | ⏳ pending   | Mandatory per spec §9, §11 step 10. |

---

## Files created this session

```
C:\SuperWork\
├── docs\superpowers\
│   ├── specs\2026-04-07-market-research-team-design.md     (from session 1)
│   └── plans\
│       ├── 2026-04-07-market-research-team-implementation.md  (from session 2)
│       └── 2026-04-07-market-research-team-SESSION-HANDOFF.md (this file)
└── agents\
    ├── registry.yaml                                         (edited — +7 entries)
    ├── bill\routing.yaml                                     (edited — +1 rule)
    └── market-research\
        ├── .gitignore
        ├── README.md
        ├── lead\skill.md                                     (Mira — the big one)
        ├── stages\
        │   ├── hunter.md
        │   ├── sift.md
        │   ├── audit.md
        │   ├── sage.md
        │   ├── quill.md
        │   └── hawk.md
        ├── inbox\
        │   ├── pending\pvc-windows-doors-profiles-ukraine.yaml
        │   ├── pending\.gitkeep
        │   ├── in-progress\.gitkeep
        │   └── done\.gitkeep
        ├── reports\.gitkeep
        └── templates\
            ├── topic.template.yaml
            └── report.template.md
```

**Git status note:** The user explicitly said "I don't care about git for this particular project." Nothing has been committed. If a future session wants to commit, the `agents\` directory in `C:\SuperWork\` is a git submodule — commits would need to happen inside `C:\SuperWork\agents\`, not at the top level.

---

## MCP configuration installed (session 2)

**File:** `C:\Users\andre\.claude.json`
**Added:** a top-level `mcpServers` object with `firecrawl` and `tavily` entries using `npx -y firecrawl-mcp` and `npx -y tavily-mcp`.

**API keys (as provided by user, to be rotated in Task 15):**
- Firecrawl: `fc-14082832298249edbc4a352c66e21164`
- Tavily: `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`

⚠️ **These keys are in plaintext in the chat transcript AND in `.claude.json`.** Task 15 must rotate them before this project is considered "done." The spec (§9, §11 step 10) flags this as mandatory.

---

## What the next session should do

### Step A: Verify MCP is live (5 minutes)

1. Confirm you're in a **fresh Claude Code session** (one started AFTER the `.claude.json` edit).
2. Check the tool list in the system reminder at the top of the session. You should see tool names starting with `mcp__firecrawl__*` and `mcp__tavily__*`. If not:
   - Re-read `C:\Users\andre\.claude.json` and confirm the `mcpServers` block is still present and valid JSON.
   - Check for errors in Claude Code's MCP server logs (some versions surface errors in a side panel or notification).
   - Possible issues: `npx` network failure, wrong API key format, firewall blocking, antivirus blocking the spawned node process.
3. Smoke-test both:
   - Tavily: call `mcp__tavily__search` (or whatever exact name appears) with `query: "PVC windows Ukraine"`, limit 1.
   - Firecrawl: call `mcp__firecrawl__scrape` on `https://example.com`.
   - Both should return without auth errors.
4. If either fails with auth: the keys may need rotation now (see Task 15 instructions) or the user may need to top up their account.

### Step B: Execute Task 13 — Manual first run (30-60 minutes of pipeline + inspection)

Full instructions are in `docs/superpowers/plans/2026-04-07-market-research-team-implementation.md`, Task 13. Summary:

1. **Trigger the batch.** In the main Bill session, say: `"Bill: run the monthly market research batch."`
   - Bill should match the new routing rule (`market research|...`) and dispatch Mira via the `Agent` tool.
   - Mira reads `inbox/pending/`, finds `pvc-windows-doors-profiles-ukraine.yaml`, and starts the pipeline.

2. **Watch stage-by-stage.** For each stage, the agent should return a 1-line pointer. Check that the corresponding file lands in `_stage-artifacts/`:
   - Hunter -> `01-sources.json`
   - Sift -> `02-facts.json`
   - Audit -> `03-verified.json` (note: object with `facts` + `gaps` keys, NOT a bare array)
   - Sage -> `04-insights.json`
   - Quill -> `05-report.md`
   - Hawk -> `06-qa-issues.json`

3. **Watch for the strict verification retry loop.** If Audit reports `gaps` (research_blocks with <50% confirmed), Mira should re-dispatch Hunter with `retry_round: 1` and the gaps list. Up to 2 retry rounds. This is expected behavior for a first run and is NOT an error.

4. **Watch for Hawk's revision loop.** If Hawk verdict is `revise` with any high-severity issue, Mira should re-dispatch Quill with `revision_round: 1`. Max 1 revision round.

5. **Publish stage.** After Hawk passes, Mira runs Publish IN HER OWN CONTEXT (not a subagent):
   - Copies/frontmatters `05-report.md` -> `report.md`
   - Invokes `anthropic-skills:xlsx` -> `data.xlsx` (4 sheets)
   - Invokes `anthropic-skills:docx` -> `report.docx`
   - Invokes `anthropic-skills:pdf` -> `report.pdf`
   - Appends a line to `agents/memory/INDEX.md`

6. **Inspect all artifacts.** Before calling it a success, verify:
   - `reports/pvc-windows-doors-profiles-ukraine/2026-04/report.md` has all 9 sections with real content and inline `(fact-XXX)` citations
   - `data.xlsx` has 4 sheets (Facts, Sources, Insights, Metadata)
   - `report.docx` and `report.pdf` rendered
   - `_run-log.json` shows `final_status: "succeeded"` or `"partially_succeeded"`
   - `inbox/done/` has `pvc-windows-doors-profiles-ukraine.yaml.completed` + `result.json`
   - `inbox/in-progress/` is empty
   - `agents/memory/INDEX.md` has a new entry at the bottom

7. **If things go wrong.** Expected — it's the first run. Identify the responsible agent skill file, edit it to clarify the unclear instruction, move the inbox file back to `pending/`, delete or rename the failed run directory, and re-run. Common likely issues:
   - Hunter returning too few sources -> broaden query decomposition hint
   - Sift struggling with Firecrawl `/extract` schemas -> may need per-source-type fallback
   - Audit's independence rule being too strict -> loosen "same publisher" detection
   - Quill missing the gap-disclosure blockquote when a block is under-verified
   - Publish step failing on xlsx/docx/pdf skills — check partial-success handling is kicking in correctly

### Step C: Tasks 14 + 15 (after Task 13 passes)

**Task 14 — Schedule the monthly run.** Only register the scheduled task if Task 13 produced a clean run. Use `mcp__scheduled-tasks__create_scheduled_task` with:
- `name`: `monthly-market-research-batch`
- `schedule`: `0 9 1 * *` (09:00 on the 1st of every month)
- `prompt`: `"Bill: run the monthly market research batch. Dispatch Mira to process all topics in agents/market-research/inbox/pending/."`

**Task 15 — Rotate keys.** Mandatory per spec §9, §11 step 10.
1. Log into firecrawl.dev, revoke `fc-14082832298249edbc4a352c66e21164`, create a new key.
2. Log into tavily.com, revoke `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`, create a new key.
3. Update `C:\Users\andre\.claude.json` `mcpServers.firecrawl.env.FIRECRAWL_API_KEY` and `mcpServers.tavily.env.TAVILY_API_KEY` with the new values.
4. Restart Claude Code.
5. Smoke-test both servers again.

---

## Decisions already locked (do not re-litigate)

These were settled during brainstorming (spec §2) and should not be reopened:

- **Team architecture:** Hybrid lead + 6 subagents (not flat, not monolithic)
- **Topic source:** Manual drop into `inbox/pending/` (no automated backlog in MVP)
- **Parallelism:** Sequential only, one topic at a time
- **Output formats:** MD (source) + XLSX + DOCX + PDF
- **Verification rigor:** Strict — every body fact needs >=2 independent sources
- **External tooling:** Firecrawl (fetch) + Tavily (discovery) via MCP
- **Scheduling:** `scheduled-tasks` MCP, cron `0 9 1 * *`
- **Pipeline structure:** 6 real subagents dispatched via `Agent` tool, file-based handoffs
- **Trend mode:** Skeleton only in MVP (opt-in via `trend_mode: true`)
- **Names:** Mira / Hunter / Sift / Audit / Sage / Quill / Hawk

## Things that are INTENTIONALLY out of scope (do not build)

- Parallel multi-topic processing
- Full trend mode implementation (stubbed)
- Custom branding / letterhead on DOCX/PDF
- Email/Slack/webhook notifications
- Cross-topic analytics dashboard
- Automated topic backlog
- Non-windows/doors verticals

## Known implementation-level open questions (per spec §14)

These are expected to surface DURING Task 13 and be addressed with targeted skill-file edits:
- Exact Firecrawl `/extract` schema per research_block (Sift has a draft, first run will reveal gaps)
- Ukrainian-language high-confidence source allowlist for Hunter (grow over time from first-run experience)
- Whether Hawk's `verdict: revise` should also re-dispatch Sage (currently only Quill)
- Exact column formatting for `data.xlsx` (cosmetic, defer until first run produces a real file)

---

## Quick-reference commands for the next session

```bash
# Verify all files are still where they should be
ls C:/SuperWork/agents/market-research/
ls C:/SuperWork/agents/market-research/stages/
ls C:/SuperWork/agents/market-research/inbox/pending/

# Read the spec (if context is needed)
# docs/superpowers/specs/2026-04-07-market-research-team-design.md

# Read the implementation plan (for Task 13 detail)
# docs/superpowers/plans/2026-04-07-market-research-team-implementation.md

# Trigger the first run (in the MAIN session, not a subagent)
# say to Claude: "Bill: run the monthly market research batch."
```

## Contacts / ownership

- **Sub-team lead:** Mira (`agents/market-research/lead/skill.md`)
- **Parent orchestrator:** Bill (`agents/bill/skill.md`)
- **Sub-team members:** Hunter, Sift, Audit, Sage, Quill, Hawk (`agents/market-research/stages/*.md`)
- **Integration points:** `agents/registry.yaml` (entries 7–13), `agents/bill/routing.yaml` (last rule before fallback)
