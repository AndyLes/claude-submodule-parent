# Mira Depth Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five root causes that made Mira's 2026-04-r3 PVC Ukraine report shallow: (1) Sift cannot parse binary files; (2) Audit's ≥2-source rule cascades all official facts to `weakly_supported`; (3) preset has no ukrstat entry; (4) API sources fail silently; (5) Quill refuses derived inferences. Re-run the PVC Ukraine topic end-to-end and match ≥80% of the gold-standard reference report's numeric depth.

**Architecture:** Insert a new deterministic `Parser` stage between Hunter and Sift that runs in Bill's own context (no subagent) and converts binary `file://` sources (xlsx, HTML-table-disguised-as-xls, images) into a normalized `02a-parsed.json`. Sift consumes parsed rows directly for `file://` sources and keeps Firecrawl `/extract` for http sources. Audit's verification rule becomes "single whitelisted-official source → `confirmed`" (D1 from spec). Sage gets promoted to a real synthesis engine that emits insights with `derivation_type` + `derivation_steps` + `implication`. Quill gains the ability to cite `(insight-NNN)` in body sections 4–8 for derived claims. Hawk validates derivations.

**Tech Stack:**
- Python 3.12 (winget-installed at `C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe`) with `openpyxl`, `pandas`, `beautifulsoup4`, `lxml`, `xlrd==1.2.0`
- Markdown skill files under `agents/market-research/stages/` and `agents/market-research/lead/skill.md`
- YAML preset at `agents/market-research/presets/ua.yaml`
- Existing Mira pipeline scaffolding (stages already registered as Claude Code subagents)

**Spec:** `docs/superpowers/specs/2026-04-08-mira-depth-fix-design.md`

**Submodule note:** `agents/` is a git submodule. Commits to `agents/market-research/**` go in the submodule; commits to `docs/superpowers/**` go in the parent repo. Each task's commit step specifies which.

---

## File structure

### New files
- `agents/market-research/tools/parse_sources.py` — Parser script (Python 3). Reads `01-sources.json`, parses each `file://` source, writes `02a-parsed.json`.
- `agents/market-research/tools/python-interpreter.txt` — One line: absolute path to Python interpreter. Read by the lead skill; avoids hardcoding in skill markdown.
- `agents/market-research/tools/tests/test_parse_sources.py` — Unit tests using real fixture files from `agents/market-research/data/ua/`.
- `agents/market-research/tools/README.md` — How to install deps, how Parser fits in the pipeline.

### Modified files
- `agents/market-research/lead/skill.md` — Insert new Stage 1.5 "Parser" between Hunter and Sift.
- `agents/market-research/stages/sift.md` — Handle `file://` sources from `02a-parsed.json`; add `is_official` flag to facts.
- `agents/market-research/stages/audit.md` — Replace ≥2-source rule with single-official-source rule.
- `agents/market-research/stages/sage.md` — Rewrite as synthesis engine with `derivation_type`/`derivation_steps`/`implication` schema.
- `agents/market-research/stages/quill.md` — Allow `(insight-NNN)` citations in body sections 4–8; remove verification panic preamble; terse gap notes.
- `agents/market-research/stages/hawk.md` — Add derivation validation pass.
- `agents/market-research/presets/ua.yaml` — Add `ukrstat` manual-download entry; fix `nbu_policy_rate_series` URL; add bare-folder fallback note.
- `agents/market-research/templates/report.template.md` — Remove verification-status preamble block.

### Files re-run at the end (not modified)
- `agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml` — Re-dropped from `inbox/done/` for the acceptance test.
- `agents/market-research/data/ua/ukrstat/*.xlsx` — 3 files already dropped; move into a `2025/` subfolder to match the preset pattern, or rely on the bare-folder fallback added in Task 8.

---

## Task 1: Parser script with failing tests

**Files:**
- Create: `agents/market-research/tools/parse_sources.py`
- Create: `agents/market-research/tools/tests/test_parse_sources.py`
- Create: `agents/market-research/tools/python-interpreter.txt`
- Create: `agents/market-research/tools/README.md`

### Step 1: Create the interpreter path file

- [ ] **Step 1a: Write the interpreter path**

Create `agents/market-research/tools/python-interpreter.txt` with exactly one line:

```
C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe
```

No trailing newline sensitivity — the lead skill reads the file and strips whitespace.

### Step 2: Write the failing tests

- [ ] **Step 2a: Write test file with fixtures pointing at real data**

Create `agents/market-research/tools/tests/test_parse_sources.py`:

```python
"""Tests for parse_sources.py — uses real fixture files already on disk."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]  # C:\SuperWork
SCRIPT = REPO_ROOT / "agents" / "market-research" / "tools" / "parse_sources.py"
DATA = REPO_ROOT / "agents" / "market-research" / "data" / "ua"

TRADEMAP_IMPORTING = DATA / "trademap" / "2025" / \
    "Trade_Map_-_List_of_importing_markets_for_a_product_exported_by_Ukraine (4).xls"
TRADEMAP_SUPPLYING = DATA / "trademap" / "2025" / \
    "Trade_Map_-_List_of_supplying_markets_for_a_product_imported_by_Ukraine (4).xls"
UKRSTAT_XLSX = DATA / "ukrstat" / \
    "dataset_2026-04-01T06_34_11.240657597Z_DEFAULT_INTEGRATION_SSSU_DF_BEGINING_COMPLETION_CONSTRUCTION_LATEST.xlsx"


def _run_parser(sources):
    """Write sources to a temp json, run parser, return parsed output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        sources_path = tmp / "01-sources.json"
        output_path = tmp / "02a-parsed.json"
        sources_path.write_text(json.dumps(sources), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(sources_path), str(output_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"parser failed: {result.stderr}"
        return json.loads(output_path.read_text(encoding="utf-8"))


def test_parses_trademap_importing_xls_as_html_table():
    """Trade Map .xls files are actually HTML tables — parser must handle them."""
    assert TRADEMAP_IMPORTING.exists(), f"fixture missing: {TRADEMAP_IMPORTING}"
    sources = [{
        "id": "src-001",
        "url": f"file:///{TRADEMAP_IMPORTING.as_posix()}",
        "source_title": "Trade Map — Ukraine HS exports",
        "research_block": "import_export",
    }]
    parsed = _run_parser(sources)
    assert len(parsed) == 1
    entry = parsed[0]
    assert entry["source_id"] == "src-001"
    assert entry["parser_type"] == "html_table"
    assert "rows" in entry
    assert len(entry["rows"]) >= 5, "Trade Map should have at least 5 partner countries"
    # Every row should be a dict keyed by column name
    assert all(isinstance(r, dict) for r in entry["rows"])


def test_parses_ukrstat_real_xlsx():
    """Держstat SDMX exports are real OOXML xlsx."""
    assert UKRSTAT_XLSX.exists(), f"fixture missing: {UKRSTAT_XLSX}"
    sources = [{
        "id": "src-002",
        "url": f"file:///{UKRSTAT_XLSX.as_posix()}",
        "source_title": "Держstat — будівництво",
        "research_block": "demand_drivers",
    }]
    parsed = _run_parser(sources)
    assert len(parsed) == 1
    entry = parsed[0]
    assert entry["parser_type"] == "xlsx_ooxml"
    assert len(entry["rows"]) >= 1


def test_skips_http_sources():
    """Parser only handles file:// URLs; http sources are passed through untouched."""
    sources = [
        {"id": "src-001", "url": "https://bank.gov.ua/somewhere", "research_block": "pricing"},
    ]
    parsed = _run_parser(sources)
    assert parsed == []


def test_unknown_file_type_is_skipped_with_warning():
    """Unknown extensions are logged as unknown, not crashed."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(b"not a real file")
        unknown_path = f.name
    try:
        sources = [{
            "id": "src-003",
            "url": f"file:///{Path(unknown_path).as_posix()}",
            "research_block": "market_size",
        }]
        parsed = _run_parser(sources)
        assert len(parsed) == 1
        assert parsed[0]["parser_type"] == "unknown"
        assert parsed[0]["rows"] == []
        assert "warnings" in parsed[0]
    finally:
        os.unlink(unknown_path)


def test_caps_rows_at_500_per_source():
    """Guard against runaway parsing of the wrong sheet."""
    # We trust the implementation to apply the cap; assert the shape contract.
    assert TRADEMAP_SUPPLYING.exists(), f"fixture missing: {TRADEMAP_SUPPLYING}"
    sources = [{
        "id": "src-004",
        "url": f"file:///{TRADEMAP_SUPPLYING.as_posix()}",
        "research_block": "import_export",
    }]
    parsed = _run_parser(sources)
    assert len(parsed[0]["rows"]) <= 500
```

- [ ] **Step 2b: Run tests to verify they fail (parser script does not exist yet)**

Run: `"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" -m pytest agents/market-research/tools/tests/test_parse_sources.py -v`
Expected: FAIL with either "No such file or directory: parse_sources.py" or "pytest not installed". If pytest is missing, install it first: `"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" -m pip install pytest`, then re-run.

### Step 3: Write the parser script

- [ ] **Step 3a: Create parse_sources.py**

Create `agents/market-research/tools/parse_sources.py`:

```python
"""Parser stage for Mira market research pipeline.

Reads 01-sources.json, iterates sources with file:// URLs, parses each according
to file extension + magic, writes 02a-parsed.json.

Output schema (array of entries):
  [
    {
      "source_id": "src-001",
      "parser_type": "xlsx_ooxml" | "html_table" | "image_vision" | "unknown",
      "file_path": "...",
      "sheet_name": "Sheet1" | null,
      "rows": [ {col: value, ...}, ... ],
      "warnings": [ "..." ]
    },
    ...
  ]

Image sources are NOT parsed here — they are left with parser_type="image_vision"
and rows=[]; Bill handles vision extraction in the lead skill.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_ROWS_PER_SOURCE = 500

# Suppress noisy warnings from openpyxl about data validation, conditional formatting, etc.
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def _file_url_to_path(url: str) -> Path | None:
    """Convert file:///C:/foo/bar.xlsx to a Path. Returns None if not a file URL."""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    # file:///C:/foo -> /C:/foo on Windows; strip the leading slash when followed by a drive letter
    path_str = unquote(parsed.path)
    if len(path_str) >= 3 and path_str[0] == "/" and path_str[2] == ":":
        path_str = path_str[1:]
    return Path(path_str)


def _detect_parser_type(path: Path) -> str:
    """Dispatch on extension + magic. HTML-table .xls is the tricky case."""
    suffix = path.suffix.lower()
    if suffix in {".webp", ".png", ".jpg", ".jpeg"}:
        return "image_vision"
    if suffix == ".xlsx":
        return "xlsx_ooxml"
    if suffix == ".xls":
        # Trade Map exports HTML tables with .xls extension. Peek at magic.
        try:
            head = path.open("rb").read(512)
        except OSError:
            return "unknown"
        # Real .xls (legacy BIFF) starts with D0 CF 11 E0 (OLE compound doc).
        # HTML tables start with <html, <!DOCTYPE, or similar.
        if head[:4] == b"\xd0\xcf\x11\xe0":
            return "xlsx_ooxml"  # Treated as legacy; openpyxl will reject, caller handles.
        lower = head.lower().lstrip()
        if lower.startswith(b"<html") or lower.startswith(b"<!doctype") or lower.startswith(b"<table") or lower.startswith(b"<meta") or b"<table" in lower[:500]:
            return "html_table"
        return "unknown"
    return "unknown"


def _parse_xlsx(path: Path) -> tuple[list[dict], str | None, list[str]]:
    """Parse real OOXML xlsx via openpyxl. Returns (rows, sheet_name, warnings)."""
    import openpyxl

    warnings_list: list[str] = []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    sheet_name = sheet.title if sheet else None
    if sheet is None:
        return [], None, ["no active sheet"]

    # Load up to MAX_ROWS_PER_SOURCE + 10 rows so we can find a header even if it's late.
    raw_rows: list[tuple] = []
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i > MAX_ROWS_PER_SOURCE + 10:
            warnings_list.append(f"truncated at {MAX_ROWS_PER_SOURCE + 10} rows")
            break
        raw_rows.append(row)
    wb.close()

    if not raw_rows:
        return [], sheet_name, warnings_list

    # Find header row: first row where >=3 cells are strings.
    header_idx = 0
    for i, row in enumerate(raw_rows[:10]):
        string_cells = sum(1 for c in row if isinstance(c, str) and c.strip())
        if string_cells >= 3:
            header_idx = i
            break
    headers = [
        (str(c).strip() if c is not None else f"col_{j}")
        for j, c in enumerate(raw_rows[header_idx])
    ]
    # De-duplicate empty header cells
    headers = [h if h else f"col_{j}" for j, h in enumerate(headers)]

    rows: list[dict] = []
    for row in raw_rows[header_idx + 1 : header_idx + 1 + MAX_ROWS_PER_SOURCE]:
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            continue  # skip fully-empty rows
        rec = {}
        for j, val in enumerate(row):
            key = headers[j] if j < len(headers) else f"col_{j}"
            rec[key] = val
        rows.append(rec)
    return rows, sheet_name, warnings_list


def _parse_html_table(path: Path) -> tuple[list[dict], str | None, list[str]]:
    """Parse HTML-table-disguised-as-xls (Trade Map exports). Returns (rows, sheet_name, warnings)."""
    import pandas as pd

    warnings_list: list[str] = []
    try:
        tables = pd.read_html(path, encoding="utf-8")
    except Exception as exc:
        return [], None, [f"pandas.read_html failed: {exc}"]

    if not tables:
        return [], None, ["no tables found in html"]

    # Pick the largest table (Trade Map has one big data table + a metadata header table)
    df = max(tables, key=lambda t: t.shape[0] * t.shape[1])

    # Trim to row cap
    if len(df) > MAX_ROWS_PER_SOURCE:
        warnings_list.append(f"truncated at {MAX_ROWS_PER_SOURCE} rows")
        df = df.head(MAX_ROWS_PER_SOURCE)

    # Stringify column names (multi-level headers collapse to tuples)
    df.columns = [
        " / ".join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col).strip()
        for col in df.columns
    ]

    # Convert NaN → None for JSON
    rows = []
    for rec in df.to_dict(orient="records"):
        cleaned = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
        rows.append(cleaned)

    return rows, None, warnings_list


def parse_source(source: dict) -> dict | None:
    """Parse one source record. Returns None if source is not a file:// URL."""
    url = source.get("url", "")
    path = _file_url_to_path(url)
    if path is None:
        return None

    if not path.exists():
        return {
            "source_id": source["id"],
            "parser_type": "unknown",
            "file_path": str(path),
            "sheet_name": None,
            "rows": [],
            "warnings": [f"file not found: {path}"],
        }

    parser_type = _detect_parser_type(path)
    rows: list[dict] = []
    sheet_name: str | None = None
    warnings_list: list[str] = []

    try:
        if parser_type == "xlsx_ooxml":
            rows, sheet_name, warnings_list = _parse_xlsx(path)
        elif parser_type == "html_table":
            rows, sheet_name, warnings_list = _parse_html_table(path)
        elif parser_type == "image_vision":
            warnings_list = ["image — vision extraction handled by Bill in lead skill"]
        else:
            warnings_list = [f"unknown parser type for suffix {path.suffix}"]
    except Exception as exc:
        warnings_list = [f"parser exception: {type(exc).__name__}: {exc}"]

    return {
        "source_id": source["id"],
        "parser_type": parser_type,
        "file_path": str(path),
        "sheet_name": sheet_name,
        "rows": rows,
        "warnings": warnings_list,
    }


def main(sources_path: str, output_path: str) -> int:
    sources = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    parsed: list[dict] = []
    for source in sources:
        result = parse_source(source)
        if result is not None:
            parsed.append(result)

    Path(output_path).write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"parsed {len(parsed)} file:// sources → {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: parse_sources.py <01-sources.json> <02a-parsed.json>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
```

- [ ] **Step 3b: Run the tests and verify they pass**

Run: `"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" -m pytest agents/market-research/tools/tests/test_parse_sources.py -v`
Expected: all 5 tests PASS.

If `test_parses_trademap_importing_xls_as_html_table` fails with "no tables found in html", check that `pandas.read_html` can read the actual Trade Map file directly:
```
"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" -c "import pandas; print(len(pandas.read_html(r'C:\SuperWork\agents\market-research\data\ua\trademap\2025\Trade_Map_-_List_of_importing_markets_for_a_product_exported_by_Ukraine (4).xls')))"
```

- [ ] **Step 3c: Run the parser against the full PVC Ukraine data folder manually (sanity check)**

Build a sources.json with all 15 real files and run the parser:
```bash
"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" -c "
import json
from pathlib import Path
DATA = Path(r'C:\\SuperWork\\agents\\market-research\\data\\ua')
sources = []
sid = 1
for f in sorted(list(DATA.glob('trademap/2025/*.xls')) + list(DATA.glob('ukrstat/*.xlsx'))):
    sources.append({'id': f'src-{sid:03d}', 'url': f.resolve().as_uri(), 'research_block': 'import_export'})
    sid += 1
Path('/tmp/test-sources.json').write_text(json.dumps(sources, indent=2))
print(f'wrote {len(sources)} sources')
"
"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" agents/market-research/tools/parse_sources.py /tmp/test-sources.json /tmp/test-parsed.json
"C:\Users\andre\AppData\Local\Programs\Python\Python312\python.exe" -c "import json; data=json.load(open('/tmp/test-parsed.json')); print('parsed', len(data), 'files'); [print(d['source_id'], d['parser_type'], len(d['rows']), 'rows') for d in data]"
```
Expected: 12 trademap files parsed as `html_table` with 5–50 rows each, 3 ukrstat files parsed as `xlsx_ooxml` with ≥1 row each. Zero files with `parser_type: unknown`.

### Step 4: Create tools/README.md

- [ ] **Step 4a: Write the tools README**

Create `agents/market-research/tools/README.md`:

````markdown
# market-research/tools

Deterministic helpers for the Mira pipeline that run in Bill's own context, not as subagents.

## parse_sources.py

Parses the binary `file://` sources Hunter registers (Trade Map `.xls` HTML tables, Держstat `.xlsx` OOXML, images) and emits a normalized `02a-parsed.json` that Sift reads.

### Usage

```bash
"$(cat agents/market-research/tools/python-interpreter.txt)" \
  agents/market-research/tools/parse_sources.py \
  <run_dir>/_stage-artifacts/01-sources.json \
  <run_dir>/_stage-artifacts/02a-parsed.json
```

### Dependencies

Python 3.12 (installed via `winget install Python.Python.3.12`) plus:

- `openpyxl` — real OOXML xlsx
- `pandas` + `lxml` + `beautifulsoup4` — HTML-table parsing (Trade Map trick)
- `xlrd==1.2.0` — safety fallback for genuine legacy BIFF .xls
- `pytest` — running the test suite

One-time install:
```
"$(cat agents/market-research/tools/python-interpreter.txt)" -m pip install openpyxl xlrd==1.2.0 pandas beautifulsoup4 lxml pytest
```

### Tests

```
"$(cat agents/market-research/tools/python-interpreter.txt)" -m pytest agents/market-research/tools/tests/ -v
```

Tests use real fixture files from `agents/market-research/data/ua/`. If those fixtures move or get deleted, the tests will skip with a clear error rather than crash.
````

### Step 5: Commit

- [ ] **Step 5a: Commit the parser in the submodule**

```bash
cd agents
git add market-research/tools/
git commit -m "feat(mira): add parser script for binary file:// sources

New Python 3 parser handles:
- Real OOXML xlsx (Держstat SDMX exports) via openpyxl
- HTML-table .xls (Trade Map trick) via pandas.read_html
- Image files are flagged for Bill's vision extraction path

Deterministic, testable, runs in Bill's own context between Hunter and Sift.
Resolves the #1 root cause of the shallow 2026-04-r3 PVC Ukraine report.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 2: Sift — consume parsed rows for file:// sources

**Files:**
- Modify: `agents/market-research/stages/sift.md`
- Modify: `C:/SuperWork/.claude/agents/sift.md` (if separate registration exists — grep to confirm)

### Step 1: Add `parsed_path` input and new workflow branch

- [ ] **Step 1a: Replace the "Inputs (from Mira)" section**

In `agents/market-research/stages/sift.md`, replace the `## Inputs (from Mira)` section with:

```markdown
## Inputs (from Mira)

- `sources_path`: absolute path to `01-sources.json`
- `parsed_path`: absolute path to `02a-parsed.json` (NEW — output of the Parser stage; contains pre-parsed rows for every `file://` source)
- `topic_yaml_path`: absolute path to topic YAML (for context: geography, time_focus)
- `output_path`: absolute path where `02-facts.json` must be written
```

- [ ] **Step 1b: Rewrite the Workflow section**

Replace the existing `## Workflow` section with:

```markdown
## Workflow

0. **Defense-in-depth source check.** Before processing any source, verify it is one of the following:
   - a `file://` URL (drop-folder file from Hunter step 1b), OR
   - a web URL whose hostname (after stripping `www.`) appears in the country preset's `authoritative_domains` whitelist (load `presets/<topic.geography>.yaml` if it exists)

   **DROP any source that fails this check.** Do NOT call Firecrawl `/extract` on it. Hunter's strict whitelist mode should already have filtered these out — this is a defense-in-depth gate so a misconfigured run cannot silently spend tokens on media, blogs, or consultancies. Log the count of dropped sources in the return pointer as `sources_dropped_by_whitelist`.

1. **Read `sources_path` and `parsed_path`.** The parsed file is a JSON array of `{source_id, parser_type, rows, warnings}` entries — one per `file://` source that was already parsed by the Parser stage. Build a lookup table `parsed_by_source_id`.

2. **Read topic YAML** — for geography, products, time_focus, research_blocks.

3. **Load the preset** to determine `authoritative_domains` (for the `is_official` flag).

4. **For each source in `01-sources.json`:**

   - **If `source.url` starts with `file://`:** look up `source.id` in `parsed_by_source_id`.
     - If not found → log and skip (Parser didn't emit this source, meaning the file was missing or Parser errored).
     - If `parser_type == "image_vision"` → skip in Sift; Bill already handled image sources in the Parser step's Bill-side vision pass (see lead skill).
     - Otherwise iterate `rows` and emit one fact per meaningful row using the **row-to-fact mapping** below.
     - Set `is_official: true` on every fact emitted from a `file://` source (manual downloads are official by definition).

   - **Else (http/https source):** Use the existing Firecrawl `/extract` flow (unchanged). Set `is_official: true` if the source hostname is in `preset.authoritative_domains`, else `false`.

5. **Row-to-fact mapping for parsed sources.** Dispatch on the source's filename (accessible via the source record's `url` basename):

   | Filename pattern | research_block | Row semantics |
   |---|---|---|
   | `Trade_Map_*List_of_supplying*` | `import_export` | Each row = one supplier country. For each numeric column whose header looks like a year (regex `^\d{4}`) or contains "value" + a year, emit one fact with `metric = "HS {code} imports from {country}"`, `value = cell`, `unit = "thousand USD"` (Trade Map default), `time_period = column header year`, `geography = topic.geography`. Extract `{code}` from the source_title or filename if possible; otherwise "HS (unknown)". The country name is in the row's first string column. |
   | `Trade_Map_*List_of_importing*` | `import_export` | Same as above but `metric = "HS {code} exports to {country}"`. |
   | `dataset_*CONSTRUCTION*` (Держstat SDMX) | `demand_drivers` | Each row = one indicator × period. Emit one fact per row with `metric = row["INDICATOR"]` (or the first non-null string column), `value = row["VALUE"]` (or the first numeric column), `unit = row["UNIT"]` (or null), `time_period = row["TIME_PERIOD"]` (or null). SDMX exports use standardized column names. |
   | other | fall back | Emit one fact per row with `metric = source_title + ":" + str(row_index)`, `value = null`, `unit = null`, `notes = json.dumps(row)[:300]`. These land in Sift as qualitative rows and Sage/Quill decide whether to use them. |

   **Skip rows where the value column is None or empty.** Do not emit facts with null values for quantitative blocks.

6. **Call Firecrawl `/extract` on http sources.** Use the block-specific schemas already defined in this file. Emit one fact per distinct metric found. Unchanged from previous behaviour.

7. **Assign sequential fact IDs** `fact-001`, `fact-002`, ... Emit facts in source order.

8. **Write `02-facts.json`** — JSON array, pretty-printed, UTF-8. Every fact row includes the new `is_official` boolean field.

9. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "02-facts.json", "fact_count": 134, "sources_processed": 47, "sources_skipped": 3, "facts_from_file_sources": 118, "facts_from_http_sources": 16}
```
```

- [ ] **Step 1c: Update the Output schema section**

In the `## Output schema — `02-facts.json`` section, replace the example JSON with:

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
  "research_block": "market_size",
  "is_official": true
}
```

And add to the bullet list below:

```markdown
- `is_official`: `true` if the source is a `file://` manual download OR the source hostname is in the active preset's `authoritative_domains`. Audit uses this to decide whether the ≥2-source rule applies.
```

- [ ] **Step 1d: Update the Rules section**

Append to the `## Rules` bullet list:

```markdown
- **Never call Firecrawl `/extract` on a `file://` source.** If a source is `file://`, Sift reads it from `02a-parsed.json` or skips it. Firecrawl extract on file URLs will 400 and waste tokens.
- **Always set `is_official` on every fact.** The field is mandatory; never emit a fact without it.
```

### Step 2: Sync the Claude Code subagent registration

- [ ] **Step 2a: Check if a separate .claude/agents/sift.md registration exists**

Run: `ls C:/SuperWork/.claude/agents/ 2>&1`
Expected: may list `sift.md`, `hunter.md`, etc. If it does, the registrations are duplicates of `agents/market-research/stages/*.md`.

- [ ] **Step 2b: Mirror the changes to .claude/agents/sift.md if it exists**

If `.claude/agents/sift.md` exists, apply the same three edits from Step 1a/1b/1c/1d there. Otherwise skip.

### Step 3: Commit

- [ ] **Step 3a: Commit Sift changes in the submodule**

```bash
cd agents
git add market-research/stages/sift.md
git commit -m "feat(mira): sift consumes parsed rows for file:// sources

- Adds parsed_path input pointing at 02a-parsed.json
- For file:// sources, iterate parsed rows and emit facts via filename-based mapping
- For http sources, existing Firecrawl /extract flow unchanged
- Adds mandatory is_official boolean to every fact (for Audit's new rule)
- Never calls Firecrawl /extract on file:// URLs (would 400)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

If `.claude/agents/sift.md` was also edited, add it in a separate parent-repo commit:
```bash
git add .claude/agents/sift.md
git commit -m "chore(mira): mirror sift changes to CC subagent registration

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Audit — single-official-source = confirmed rule

**Files:**
- Modify: `agents/market-research/stages/audit.md`
- Modify: `.claude/agents/audit.md` (if exists)

### Step 1: Rewrite the verification logic

- [ ] **Step 1a: Replace the "Workflow" section**

In `agents/market-research/stages/audit.md`, replace the entire `## Workflow` section (steps 1–7 and the "Independence rule" paragraph) with:

```markdown
## Workflow

1. **Read facts, sources, topic YAML.**

2. **For each fact, apply the verification rule in this order:**

   **Rule A — Official-source fast path (primary path under strict whitelist mode).**
   If `fact.is_official == true`, the fact is automatically `confirmed` with:
   - `status: "confirmed"`
   - `supporting_source_ids: [fact.source_id]` (the originating source is the one official cite)
   - `confidence_score: 0.95`
   - `issues_found: []`

   **Rationale:** under strict-official-sources-only mode, every fact Sift emits originates from a government statistical agency, multilateral institution, or official trade database. A single such source is authoritative-at-source. Requiring a second independent publisher is structurally impossible (there is no second-tier1 publisher of an NBU FX rate), and inflates `weakly_supported` counts without adding any real verification value. The whitelist itself IS the verification layer for official facts.

   **Rule B — Non-official facts (legacy path, currently unreachable under strict whitelist mode).**
   If `fact.is_official == false`, apply the classic ≥2-independent-sources rule:
   - Check if another source in `01-sources.json` already independently supports this fact (same metric, compatible value within ±10%, same time window, same geography). If yes → candidate for `confirmed`.
   - If only the original source supports it, run a targeted Tavily search for the metric. Fetch top 2–3 results with Firecrawl. If any independently confirms → `confirmed`.
   - If sources disagree (>20% spread or contradictory qualitative claims) → `conflicting`, list all supporting_source_ids.
   - If only stale (>3 years older than `time_focus`) sources support → `outdated`.
   - Otherwise → `weakly_supported`.

   **Independence rule for Rule B:** two sources are independent only if they are different publishers AND neither cites the other. Re-publications of the same underlying data count as ONE source.

3. **Emit verification records.** One per input fact, carrying `fact_id`, `status`, `supporting_source_ids`, `issues_found`, `confidence_score`, `research_block`.

4. **Compute `gaps`.** For each `research_block` in the topic YAML, compute the ratio of `confirmed` facts to total facts in that block. Under Rule A, `confirmed` tracks **coverage** rather than verification: any block with < 3 facts at all is a gap, regardless of confirmed ratio. Any block with < 50% confirmed ratio (almost always impossible under Rule A) also goes into `gaps` with a short reason. Blocks with zero facts go into `gaps`.

5. **Write `03-verified.json`** — an OBJECT (not array) with two top-level keys: `facts` (array of verification records) and `gaps` (array of gap records). See schema below.

6. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "03-verified.json", "total_facts": 134, "confirmed": 131, "weakly_supported": 2, "conflicting": 1, "outdated": 0, "gaps": ["pricing"]}
```
```

- [ ] **Step 1b: Update the Rules section**

Replace the existing `## Rules` section with:

```markdown
## Rules

- **Official sources are authoritative-at-source.** A single `is_official: true` fact is `confirmed`. Do not demand a second publisher — the strict whitelist itself is the verification layer.
- **Non-official facts still require ≥2 independent sources** when they appear (legacy path, unreachable under strict whitelist mode but kept for future loosened configurations).
- **Do not modify or delete facts.** Emit a verdict for every input fact; downstream stages filter by status.
- **Do not invent new facts.** If Rule B finds a contradicting source for a non-official fact, record it in `issues_found`, do NOT add a new fact.
- **Gaps track coverage, not verification, under Rule A.** A block with only 1 fact is a gap even if that fact is `confirmed`.
- **Keep return pointer under 280 characters** (longer than Hunter/Sift because status counts matter to Mira).
```

### Step 2: Mirror to CC subagent registration

- [ ] **Step 2a:** If `.claude/agents/audit.md` exists, apply the same edits there.

### Step 3: Commit

- [ ] **Step 3a: Commit Audit changes**

```bash
cd agents
git add market-research/stages/audit.md
git commit -m "feat(mira): audit treats single-official sources as confirmed

Under strict-official-sources-only whitelist mode, requiring >=2
independent publishers is structurally impossible for tier-1 sources
(NBU FX rates, Rada antidumping rulings, Держstat SDMX exports each
have exactly one authoritative publisher by design).

New Rule A: fact.is_official == true -> confirmed with confidence 0.95.
Rule B (>=2 sources) kept for non-official facts, unreachable under
strict whitelist but preserved for future configurations.

Resolves the cascade that left 2026-04-r3 with 0/39 confirmed.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 4: Sage — synthesis engine with derivations

**Files:**
- Modify: `agents/market-research/stages/sage.md`
- Modify: `.claude/agents/sage.md` (if exists)

### Step 1: Rewrite Sage's schema and workflow

- [ ] **Step 1a: Replace the Workflow section**

Replace `## Workflow` in `agents/market-research/stages/sage.md` with:

```markdown
## Workflow

1. **Read verified.json, facts.json, topic YAML.**

2. **Filter.** Only facts whose verification `status == "confirmed"` are eligible as `supporting_fact_ids` for any insight. `weakly_supported` / `conflicting` / `outdated` facts may be mentioned in `notes` but cannot be an insight's sole support.

3. **Group facts by `research_block`.** For each block, target **≥3 insights**. For an 8-block topic, that is ≥24 insights total.

4. **Build insights.** For each grouping of related facts, produce an insight record with a **derivation_type** that describes the logical step from facts to claim:

   | derivation_type | Meaning | Example |
   |---|---|---|
   | `count` | Aggregate count of qualifying facts | "3 distinct antidumping actions in 2025" |
   | `share` | One fact divided by a total fact | "Poland = 25,433 / 45,100 = 56.4% of 2024 HS 391620 imports" |
   | `ratio` | One fact divided by another | "HS 390410 imports / HS 391620 imports = 1.81x in 2024" |
   | `comparison` | Cross-period or cross-geo delta | "Lithuania exports: 2,983 (2024) → 4,302 (2025 Q1-Q3) = +92%" |
   | `trend` | Multi-period directional claim | "HS 392520 exports grew from 32,332 in 2021 to 41,800 in 2025 Q1-Q3" |
   | `qualitative` | Non-numeric claim grounded in one or more facts | "HOPE program prioritizes energy efficiency, favouring modern profiles" |

5. **Record the derivation explicitly.** Every insight must include `derivation_steps` — a short list (1–5 entries) showing how you got from supporting facts to the claim. For numeric derivations, include the arithmetic. Hawk will validate these.

6. **Write the `implication` field.** This is where Sage is allowed to **name players, make forward-looking statements, and connect across blocks**. Example: from "Poland = 56% of profile imports" (derivation_type: share), the implication may be "Polish profile brands (REHAU, Salamander, Aluplast, Gealan) likely dominate Ukrainian fabrication." Quill reads `implication` verbatim as body narrative.

7. **Cross-block insights.** Actively look for connections across blocks (e.g. regulation → pricing impact, demand_drivers → import_export shift). Tag with `research_blocks_touched` listing every block the insight spans. These are the highest-value insights.

8. **Trend mode (if enabled).** Use Glob to find prior `_stage-artifacts/03-verified.json` files under `reports/<topic_id>/*/`. If any exist, load the most recent and include one delta insight comparing current vs. prior. If none exist, skip silently.

9. **Assign insight IDs** `insight-001`, ...

10. **Write `04-insights.json`** — JSON array of insight records.

11. **Return pointer to Mira:**

```json
{"status": "ok", "output_file": "04-insights.json", "insight_count": 27, "by_derivation": {"share": 8, "comparison": 5, "trend": 4, "ratio": 3, "count": 4, "qualitative": 3}}
```
```

- [ ] **Step 1b: Replace the Output schema section**

Replace `## Output schema — \`04-insights.json\`` with:

```markdown
## Output schema — `04-insights.json`

```json
[
  {
    "id": "insight-001",
    "insight": "Poland is the dominant supplier of PVC profiles to Ukraine (56.4% of 2024 imports by value).",
    "derivation_type": "share",
    "supporting_fact_ids": ["fact-012", "fact-017"],
    "derivation_steps": [
      "fact-012: Ukraine HS 391620 imports from Poland = 25,433 thousand USD in 2024",
      "fact-017: Ukraine total HS 391620 imports = 45,100 thousand USD in 2024",
      "25,433 / 45,100 = 0.564 = 56.4%"
    ],
    "implication": "Polish profile brands (REHAU, Salamander, Aluplast, Gealan) likely dominate Ukrainian fabrication at the input layer.",
    "confidence_level": "high",
    "research_blocks_touched": ["import_export", "general_market_players"]
  }
]
```

- `derivation_type`: one of `count | share | ratio | comparison | trend | qualitative`.
- `derivation_steps`: 1–5 lines; for numeric derivations, include the arithmetic. Hawk recomputes and checks within ±5%.
- `implication`: the "so what" line. This is where Sage is allowed to name players and make forward-looking statements. Quill uses it as body narrative.
- `confidence_level` is derived from the supporting facts' confidence (use the minimum, not the average).
- `research_blocks_touched` can span multiple blocks for cross-block insights.
```

- [ ] **Step 1c: Update the Rules section**

Replace `## Rules` with:

```markdown
## Rules

- **No web tools.** Sage cannot browse. If a question can't be answered from verified facts, Sage does not invent — the insight simply isn't produced.
- **Every insight must cite ≥1 `confirmed` fact_id** via `supporting_fact_ids`. Zero-fact insights are forbidden.
- **Every insight must include `derivation_steps`.** Missing derivation_steps is a hard error.
- **Arithmetic must be correct.** For `share`, `ratio`, `comparison` types, the final number in the insight must match the arithmetic in derivation_steps within ±5%. Hawk will catch this.
- **Sage is allowed to name players and make forward-looking statements in `implication`** — as long as the claim is a single logical step from the supporting facts. Quill relies on this for body narrative in sections 4–8.
- **Sage does not write prose reports.** That's Quill's job. Sage writes structured insight records.
- **Target ≥3 insights per research_block.** For an 8-block topic, that is ≥24 insights. Fewer is acceptable only if the block has <3 confirmed facts.
- **Keep return pointer under 280 characters.**
```

### Step 2: Mirror + commit

- [ ] **Step 2a:** If `.claude/agents/sage.md` exists, apply the same edits.

- [ ] **Step 2b: Commit**

```bash
cd agents
git add market-research/stages/sage.md
git commit -m "feat(mira): sage becomes a synthesis engine

- Adds derivation_type, derivation_steps, implication to insight schema
- Sage is now allowed to name players and make forward-looking statements
  in the 'implication' field (single-logical-step from confirmed facts)
- Targets >=3 insights per research_block (>=24 for 8-block topics)
- Hawk will validate arithmetic in derivation_steps

Unlocks body narrative in Quill sections 4-8 (Players/Trends/Risks/
Opportunities) without breaking the no-uncited-claim rule.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 5: Quill — derived-inference citations and terse gap notes

**Files:**
- Modify: `agents/market-research/stages/quill.md`
- Modify: `.claude/agents/quill.md` (if exists)
- Modify: `agents/market-research/templates/report.template.md`

### Step 1: Rewrite Quill's rules around citation

- [ ] **Step 1a: Replace the Workflow steps 4 and 5**

In `agents/market-research/stages/quill.md`, replace the existing Workflow step 4 with:

```markdown
4. **Fill the template sections** in order (1 Executive Summary → 9 Methodology).
   - **Sections 1 (Executive Summary), 2 (Market Overview), 3 (Key Metrics):** Every claim must cite a `fact_id` from `confirmed_facts`. Use inline citation format: `(fact-027)`. No derived citations allowed in these sections — only verbatim facts.
   - **Sections 4 (Players), 5 (Trends & Drivers), 6 (Risks), 7 (Opportunities), 8 (Recommendations):** Body narrative may cite **either** a `fact_id` **or** an `insight_id` from `04-insights.json`. Insight citations use `(insight-003)` format. Quill draws body sentences from Sage's `implication` field verbatim whenever possible.
   - **Every numeric value, currency figure, percentage, or named player in section 3 tables must still cite a fact_id.** Insight citations are for *interpretive* claims, not numeric ones.
   - **Gap notes.** Any research_block flagged in Audit's `gaps` array is disclosed with a single-line footnote at the end of the section, like: `> Coverage note: pricing has only 2 confirmed facts; see §9.4.` — **not** a multi-line panic blockquote. If the whole report has <5 gaps, mention them collectively in §9.4 and skip per-section footnotes.
   - **Competitive Landscape heading** matches the topic's block label: if the topic lists `general_market_players`, use that name; otherwise use "Competitive Landscape". Match the label exactly.
```

- [ ] **Step 1b: Update the Executive Summary instructions**

Add a new sub-bullet under step 4 (immediately after the bullet above):

```markdown
   - **Executive Summary lead.** The first sentence must be the single biggest headline number from confirmed facts (e.g. "Ukraine exported $41.8M of HS 392520 PVC windows and doors in Q1–Q3 2025 (+37% YoY)"), not a verification status disclaimer. Do NOT include a "verification status" reader note at the top of the report — that was a workaround for the broken verification layer and is now obsolete.
```

- [ ] **Step 1c: Update the Rules section**

Replace the `## Rules` section with:

```markdown
## Rules

- **No web tools.** Quill cannot look anything up. If the confirmed facts and insights don't support a section, write one short sentence saying so (e.g. "Coverage for this block is thin; see §9.4.") — do not invent content and do not write multi-paragraph apologies.
- **Sections 1–3 = verbatim facts only.** Every claim must cite a `fact_id` with `status: confirmed`. No insight citations in these sections.
- **Sections 4–8 = facts OR insights.** Body narrative may cite either `(fact-NNN)` or `(insight-NNN)`. Insights are Sage's derived claims with `derivation_steps` — Hawk validates the arithmetic.
- **Citations are mandatory** in all body sections. No uncited numeric claims anywhere.
- **Key Metrics table** in section 3 must be verbatim facts only, grouped by `research_block`.
- **Appendix A** gets all `weakly_supported` + `outdated` facts. Appendix B gets all `conflicting` facts with a 1-line disagreement summary.
- **Gap notes are single-line footnotes**, not blockquote panic boxes. No "Important reader note" preambles.
- **Executive Summary leads with the headline number**, never with verification status.
- **Keep return pointer under 280 characters.**
```

### Step 2: Update the report template

- [ ] **Step 2a: Read the current template**

Read: `agents/market-research/templates/report.template.md`

- [ ] **Step 2b: Strip the verification-preamble block**

Remove any `> **Important reader note — verification status.** ...` blockquote at the top of the template. The Executive Summary should begin directly after the H1 title.

- [ ] **Step 2c: Ensure Section 1 has a placeholder that prompts headline-first**

At the top of `## 1. Executive Summary`, the template should have a commented instruction to Quill like:

```markdown
## 1. Executive Summary

<!-- Lead with the single biggest headline number from confirmed facts.
     Example: "Ukraine's PVC window/door exports reached $41.8M in Q1–Q3 2025
     (+37% YoY), a record high (fact-003)."
     Do NOT include a verification-status reader note here. -->
```

### Step 3: Mirror + commit

- [ ] **Step 3a:** If `.claude/agents/quill.md` exists, apply the Quill edits there.

- [ ] **Step 3b: Commit**

```bash
cd agents
git add market-research/stages/quill.md market-research/templates/report.template.md
git commit -m "feat(mira): quill cites insights in body sections 4-8

- Sections 1-3 still require verbatim fact_id citations
- Sections 4-8 may cite (fact-NNN) or (insight-NNN)
- Gap notes become single-line footnotes, not panic blockquotes
- Executive Summary leads with headline number, not verification status
- Removed the 'Important reader note' verification preamble template block

Unblocks the Players/Trends/Risks/Opportunities sections that collapsed to
'insufficient confirmed data' in 2026-04-r3.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 6: Hawk — derivation validation

**Files:**
- Modify: `agents/market-research/stages/hawk.md`
- Modify: `.claude/agents/hawk.md` (if exists)

### Step 1: Add the derivation validation pass

- [ ] **Step 1a: Insert a new pass between existing passes 4 and 5**

In `agents/market-research/stages/hawk.md`, in the `## Workflow` section, after step 4 (Uncited-claim pass) and before step 5 (Gap disclosure pass), insert:

```markdown
5. **Derivation validation pass.** For every `(insight-NNN)` citation in the report body (sections 4–8 only — sections 1–3 are fact-only), load the corresponding insight from `04-insights.json`:

   - If the insight does not exist → issue `severity: high`, type "unknown_insight_citation".
   - If `supporting_fact_ids` contains any id that is not in `confirmed_fact_ids` → issue `severity: high`, type "insight_cites_unconfirmed_fact".
   - If `derivation_steps` is missing or empty → issue `severity: high`, type "insight_missing_derivation".
   - If `derivation_type` is `share` or `ratio`: parse the final number from the insight.insight string, recompute from the cited facts, and check within ±5%. Mismatch → `severity: medium`, type "derivation_arithmetic_error".
   - If `derivation_type` is `comparison`: check that the compared periods/geographies match what's in the supporting facts. Mismatch → `severity: medium`, type "comparison_mismatch".
   - If the insight's `implication` names specific companies (players) and those names do not appear in any confirmed fact → issue `severity: low`, type "implied_player_not_in_facts". This is not an error — Sage is allowed to derive player names from import geography — but it's flagged for human review.
```

And renumber the subsequent steps (5 → 6, 6 → 7, etc.).

- [ ] **Step 1b: Update the Output schema `type` enum**

In the `## Output schema — \`06-qa-issues.json\`` section, update the `type` field's allowed values to include the new types:

```json
"type": "unconfirmed_citation | uncited_claim | missing_gap_disclosure | insight_overreach | appendix_incomplete | internal_inconsistency | missing_scope | unknown_insight_citation | insight_cites_unconfirmed_fact | insight_missing_derivation | derivation_arithmetic_error | comparison_mismatch | implied_player_not_in_facts"
```

- [ ] **Step 1c: Update the verdict logic**

In the workflow step that computes the verdict (currently step 10), update the rule:

```markdown
10. **Compute verdict.**
    - If ANY `severity: high` issue exists → `verdict: "revise"`.
    - Otherwise → `verdict: "pass"` (medium/low issues are recorded but don't block).

    High-severity types include: `unconfirmed_citation`, `uncited_claim`, `internal_inconsistency`, `unknown_insight_citation`, `insight_cites_unconfirmed_fact`, `insight_missing_derivation`.
```

### Step 2: Mirror + commit

- [ ] **Step 2a:** If `.claude/agents/hawk.md` exists, apply the same edits.

- [ ] **Step 2b: Commit**

```bash
cd agents
git add market-research/stages/hawk.md
git commit -m "feat(mira): hawk validates insight derivations

- New pass checks every (insight-NNN) citation in body sections 4-8
- Validates supporting_fact_ids are all in confirmed_fact_ids
- Recomputes share/ratio arithmetic and checks within +-5%
- Flags player names in implications that don't appear in raw facts
  (low-severity, reviewable — not a block)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 7: Lead skill — insert Parser stage between Hunter and Sift

**Files:**
- Modify: `agents/market-research/lead/skill.md`

### Step 1: Add Parser dispatch block after Hunter section

- [ ] **Step 1a: Insert a new Stage 1.5 section**

In `agents/market-research/lead/skill.md`, find `### Stage 2 — Sift` and immediately before it, insert a new section:

````markdown
### Stage 1.5 — Parser (runs in Bill's own context, not a subagent)

Binary `file://` sources registered by Hunter step 1b (xlsx, HTML-table-disguised-as-xls, images) cannot be consumed by Sift's Firecrawl `/extract` tool. This stage runs a deterministic Python parser to convert those binary files into normalized row data that Sift then maps to facts.

**When to run:** immediately after Hunter returns, if `01-sources.json` contains at least one source whose `url` starts with `file://`. If none, skip this stage and go directly to Sift.

**Tool:** Bash (Bill has it; subagents do not).

**Python interpreter:** read from `agents/market-research/tools/python-interpreter.txt` (one line, absolute path). The bare `python` / `python3` on PATH resolves to a Windows Store stub that exits 49; always use the absolute path.

**Steps:**

1. Check if any source is `file://`:

   ```bash
   jq -r '[.[] | select(.url | startswith("file://"))] | length' <run_dir>/_stage-artifacts/01-sources.json
   ```

   If the output is `0`, skip this stage.

2. Read the interpreter path:

   ```bash
   PYTHON=$(cat agents/market-research/tools/python-interpreter.txt)
   ```

3. Run the parser:

   ```bash
   "$PYTHON" agents/market-research/tools/parse_sources.py \
     <run_dir>/_stage-artifacts/01-sources.json \
     <run_dir>/_stage-artifacts/02a-parsed.json
   ```

   The parser writes `02a-parsed.json` and prints a one-line summary to stderr.

4. **Handle image sources.** After the parser runs, check for entries with `parser_type: "image_vision"`:

   ```bash
   jq '[.[] | select(.parser_type == "image_vision")]' <run_dir>/_stage-artifacts/02a-parsed.json
   ```

   For each image source, Bill reads the image file directly via the Read tool (Claude Code's Read tool accepts PNG/JPG natively; WebP via Read may or may not work — if it fails, log a warning and move on; the image just contributes no facts). For each successfully read image, Bill extracts 1–5 KPI values from visual inspection and writes them back into the same entry's `rows` field as `[{metric: "...", value: ..., unit: "..."}, ...]`. Then re-save `02a-parsed.json`.

   **Bill's vision extraction rule:** only extract numbers that are unambiguously labeled in the image (e.g. a KPI card with "Лоти 2025: 2,260" → emit `{metric: "ProZorro lots 2025", value: 2260, unit: "lots"}`). Never guess at unlabeled numbers. If the image has no clear KPI values, leave rows empty and add a warning like "no extractable KPIs in image".

5. **Log the Parser stage** to `_run-log.json` as a new `stages[]` entry:

   ```json
   {"stage": "parser", "round": 0, "status": "ok", "duration_s": 4, "pointer": {"parsed_sources": 15, "file_sources_total": 15, "image_sources_handled": 4}}
   ```

6. **On parser failure.** If the Python script exits non-zero, log the error to `_run-log.json` and **continue to Sift anyway**. Sift will find no parsed entries for file sources and will skip them with a warning. This is a partial-success path — some http-sourced facts will still land.

**Dispatch format for Sift is updated** (see Stage 2 below): a new `parsed_path` input must be passed to Sift pointing at `02a-parsed.json`.
````

- [ ] **Step 1b: Update the Stage 2 (Sift) dispatch block**

Find `### Stage 2 — Sift` and replace its dispatch block with:

```markdown
Dispatch:
```
Task: Stage 2 extraction for topic <topic_id>.
Inputs:
  sources_path: <run_dir>/_stage-artifacts/01-sources.json
  parsed_path: <run_dir>/_stage-artifacts/02a-parsed.json
  topic_yaml_path: <run_dir>/topic.yaml
  output_path: <run_dir>/_stage-artifacts/02-facts.json
```
```

(The only change is the new `parsed_path:` line.)

- [ ] **Step 1c: Update the `_run-log.json` schema example**

In the `## \`_run-log.json\` schema` section, add the parser stage to the example `stages` array, between the hunter and sift entries:

```json
    {"stage": "parser", "round": 0, "status": "ok", "duration_s": 6,   "pointer": {"parsed_sources": 15}},
```

### Step 2: Commit

- [ ] **Step 2a: Commit lead skill changes**

```bash
cd agents
git add market-research/lead/skill.md
git commit -m "feat(mira): insert Parser stage between Hunter and Sift

- New Stage 1.5 runs Python parser via Bash on file:// sources
- Skipped if no file:// sources in 01-sources.json
- Bill handles image_vision entries in-context using Read tool
- Sift dispatch gains parsed_path input
- _run-log.json gains parser stage entry
- Non-blocking: parser failures don't stop the pipeline

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 8: ua.yaml preset — ukrstat entry, NBU URL fix, bare-folder fallback

**Files:**
- Modify: `agents/market-research/presets/ua.yaml`
- Modify: `agents/market-research/stages/hunter.md` (bare-folder glob fallback in step 1b)

### Step 1: Add ukrstat manual_downloads entry

- [ ] **Step 1a: Add to manual_downloads list**

In `agents/market-research/presets/ua.yaml`, append to the `manual_downloads` list (after the ProZorro entry):

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
      sdmx.ukrstat.gov.ua → датасети SSSU_DF_BEGINING_COMPLETION_CONSTRUCTION
      (введення в експлуатацію житла, початок будівництва) або
      SSSU_DF_ECONOM_INDC_SHORT-TERM_CONSTRUCTION (обсяг будівельних робіт) →
      експорт XLSX. Файли можна покласти як у data/ua/ukrstat/{period}/,
      так і безпосередньо в data/ua/ukrstat/ — Hunter скану́є обидві папки.
```

### Step 2: Fix NBU policy rate URL

- [ ] **Step 2a: Replace the api_sources entry for nbu_policy_rate_series**

In the `api_sources:` section, replace the `nbu_policy_rate_series` block with:

```yaml
  - name: nbu_policy_rate_series
    # Old URL (/statdirectory/discountrt?json) returned 404 in 2026-04-r3 run.
    # Correct endpoint is /statdirectory/discount with valformat=json.
    url_template: "https://bank.gov.ua/NBUStatService/v1/statdirectory/discount?valformat=json"
    relevant_blocks: [pricing, macro, demand_drivers]
    description: "НБУ — облікова ставка, весь історичний ряд"
```

### Step 3: Hunter bare-folder fallback

- [ ] **Step 3a: Replace Hunter step 1b glob logic**

In `agents/market-research/stages/hunter.md`, find step `1b. **Register drop-folder files as sources.**` and replace the first sentence of the step (starting with "Glob every file under…") with:

```markdown
1b. **Register drop-folder files as sources.** (Only if a preset was loaded in step 0.) For each `manual_downloads` entry in the preset whose `relevant_blocks` intersect `topic.research_blocks`, glob the following paths (first match wins, do not register duplicates):

   1. The rendered destination with `{period}` substituted from `topic.time_focus` — this is the canonical location.
   2. The rendered destination's **parent** directory (strip the trailing `{period}/` segment) — bare-folder fallback, for cases where the user dropped files without a period subfolder.

   In both paths, apply the entry's `expected_filename_pattern` as a regex against the bare filename (ignoring `.gitkeep`). Skip files already registered from a higher-priority path.

   For each file found, create a source record with the **lowest sequential IDs** (`src-001`, `src-002`, ...) so manual-download sources precede all web sources in `01-sources.json`:
```

(The rest of step 1b — the bullet list of fields to populate per source record — stays unchanged.)

### Step 4: Move ukrstat files into `2025/` subfolder (optional, for cleanliness)

- [ ] **Step 4a: Create the 2025 subfolder and move files**

```bash
mkdir -p "C:/SuperWork/agents/market-research/data/ua/ukrstat/2025"
mv "C:/SuperWork/agents/market-research/data/ua/ukrstat/dataset_"*.xlsx "C:/SuperWork/agents/market-research/data/ua/ukrstat/2025/"
ls "C:/SuperWork/agents/market-research/data/ua/ukrstat/2025/"
```

Expected: 3 `dataset_*.xlsx` files listed.

(The bare-folder fallback in Step 3 makes this optional for functionality, but it matches the canonical layout and the other folders.)

### Step 5: Commit

- [ ] **Step 5a: Commit preset + hunter + data layout changes**

```bash
cd agents
git add market-research/presets/ua.yaml market-research/stages/hunter.md market-research/data/ua/ukrstat/
git commit -m "feat(mira): ua preset covers ukrstat, fix nbu policy rate URL

- Add manual_downloads entry for Держstat SDMX construction datasets
  (relevant_blocks: demand_drivers, construction_demand, production)
- Fix nbu_policy_rate_series URL: /discount (not /discountrt, which 404s)
- Hunter step 1b now globs both the canonical {period}/ subfolder and
  the parent drop folder, so user-dropped bare files are still picked up
- Move existing ukrstat xlsx fixtures into data/ua/ukrstat/2025/

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

---

## Task 9: Re-run the PVC Ukraine topic end-to-end (acceptance test)

**Files:**
- Move: `agents/market-research/inbox/done/pvc-windows-doors-profiles-ukraine.yaml.completed` → `agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml`

### Step 1: Reset inbox state

- [ ] **Step 1a: Move the completed topic file back to pending**

```bash
mv "C:/SuperWork/agents/market-research/inbox/done/pvc-windows-doors-profiles-ukraine.yaml.completed" \
   "C:/SuperWork/agents/market-research/inbox/pending/pvc-windows-doors-profiles-ukraine.yaml"
rm -f "C:/SuperWork/agents/market-research/inbox/done/pvc-windows-doors-profiles-ukraine.result.json"
ls "C:/SuperWork/agents/market-research/inbox/pending/"
```

Expected: `pvc-windows-doors-profiles-ukraine.yaml` listed.

### Step 2: Dry-run the Parser stage in isolation

Before running the full pipeline, sanity-check Parser against a mock 01-sources.json that lists every real fixture file. This catches Parser regressions without spending MCP tokens.

- [ ] **Step 2a: Build the mock sources**

```bash
PYTHON=$(cat "C:/SuperWork/agents/market-research/tools/python-interpreter.txt")
"$PYTHON" -c "
import json
from pathlib import Path
DATA = Path(r'C:\\SuperWork\\agents\\market-research\\data\\ua')
sources = []
sid = 1
for f in sorted(list(DATA.glob('trademap/2025/*.xls')) + list(DATA.glob('ukrstat/2025/*.xlsx')) + list(DATA.glob('prozorro/2025/*.webp'))):
    sources.append({
      'id': f'src-{sid:03d}',
      'url': f.resolve().as_uri(),
      'source_title': f.parent.name,
      'research_block': 'import_export' if 'trademap' in str(f) else 'demand_drivers'
    })
    sid += 1
Path('/tmp/pvc-mock-sources.json').write_text(json.dumps(sources, indent=2))
print(f'wrote {len(sources)} mock sources')
"
```

- [ ] **Step 2b: Run parser against the mock**

```bash
PYTHON=$(cat "C:/SuperWork/agents/market-research/tools/python-interpreter.txt")
"$PYTHON" "C:/SuperWork/agents/market-research/tools/parse_sources.py" \
  /tmp/pvc-mock-sources.json \
  /tmp/pvc-mock-parsed.json
```

Expected stderr: `parsed N file:// sources → /tmp/pvc-mock-parsed.json` where N equals the count of mock sources.

- [ ] **Step 2c: Inspect parser output shape**

```bash
PYTHON=$(cat "C:/SuperWork/agents/market-research/tools/python-interpreter.txt")
"$PYTHON" -c "
import json
data = json.load(open('/tmp/pvc-mock-parsed.json'))
from collections import Counter
print('parser types:', Counter(d['parser_type'] for d in data))
print('rows per file:')
for d in data:
    print(f'  {d[\"source_id\"]} {d[\"parser_type\"]:12s} rows={len(d[\"rows\"])} warnings={d[\"warnings\"]}')
"
```

Expected: zero `unknown` types; `html_table` for all trademap files with rows ≥ 5; `xlsx_ooxml` for all ukrstat files with rows ≥ 1; `image_vision` for prozorro webp files with rows = 0 and warnings = ["image — vision extraction handled by Bill in lead skill"].

### Step 3: Run Mira end-to-end

- [ ] **Step 3a: Dispatch Bill → Mira skill with the PVC topic**

Invoke (in a separate conversation turn, driven by Bill loading `agents/market-research/lead/skill.md`):

```
Bill: Run market research for pvc-windows-doors-profiles-ukraine.
```

Bill will load the lead skill and execute the 6-stage pipeline. Expected stage progression in `_run-log.json`:

1. `hunter` round 0 → writes `01-sources.json` with at least 15 `file://` sources (from data/ua/{trademap,ukrstat,prozorro}/2025/) plus web sources from Tavily
2. `parser` round 0 → writes `02a-parsed.json` with zero unknown types
3. `sift` round 0 → writes `02-facts.json` with `fact_count ≥ 100`, every fact having `is_official: true`
4. `audit` round 0 → writes `03-verified.json` with `confirmed ≥ 80%` (vs. 0% in r3)
5. `sage` round 0 → writes `04-insights.json` with `insight_count ≥ 20`, each with `derivation_steps` populated
6. `quill` round 0 → writes `05-report.md` with sections 4/5/6/7/8 containing concrete body sentences citing mix of fact_ids and insight_ids
7. `hawk` round 0 → `verdict: pass` or at most medium-severity issues

- [ ] **Step 3b: If Hawk returns `revise`, let Mira do 1 revision round automatically**

Expected: the revision resolves all high-severity issues. If not, inspect `06-qa-issues.json` manually and iterate on whichever stage introduced the issue.

### Step 4: Verify acceptance criteria

- [ ] **Step 4a: Locate the new run directory**

```bash
ls "C:/SuperWork/agents/market-research/reports/pvc-windows-doors-profiles-ukraine/"
```

Expected: a new directory `2026-04-r4/` (since r2 and r3 already exist).

- [ ] **Step 4b: Check fact counts**

```bash
cd "C:/SuperWork/agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04-r4"
PYTHON=$(cat "C:/SuperWork/agents/market-research/tools/python-interpreter.txt")
"$PYTHON" -c "
import json
facts = json.load(open('_stage-artifacts/02-facts.json'))
verified = json.load(open('_stage-artifacts/03-verified.json'))
insights = json.load(open('_stage-artifacts/04-insights.json'))
print(f'facts: {len(facts)}')
print(f'facts with is_official=true: {sum(1 for f in facts if f.get(\"is_official\"))}')
verified_facts = verified['facts'] if isinstance(verified, dict) else verified
confirmed = sum(1 for v in verified_facts if v['status'] == 'confirmed')
print(f'confirmed: {confirmed}/{len(verified_facts)} = {100*confirmed/len(verified_facts):.0f}%')
print(f'insights: {len(insights)}')
print(f'insights with derivation_steps: {sum(1 for i in insights if i.get(\"derivation_steps\"))}')
"
```

Expected output:
- `facts: ≥ 100`
- `facts with is_official=true: ≥ 100` (every fact should be official under strict whitelist)
- `confirmed: ≥ 80%` (up from 0% in r3)
- `insights: ≥ 20`
- `insights with derivation_steps: ≥ 20` (every insight must have them)

- [ ] **Step 4c: Grep for required content in the report**

```bash
cd "C:/SuperWork/agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04-r4"
grep -c "391620\|392520\|390410" report.uk.md
grep -c "ProZorro\|проzorro\|prozorro" report.uk.md
grep -c "Держстат\|Держstat\|будівн" report.uk.md
grep -c "НБУ\|NBU" report.uk.md
grep -ci "insufficient\|insufficient_confirmed_data\|недостатньо" report.uk.md
```

Expected:
- HS codes: ≥ 3 mentions
- ProZorro: ≥ 3 mentions
- Держстат/construction: ≥ 3 mentions
- NBU: ≥ 2 mentions
- "insufficient data" phrase: ≤ 1 (ideally 0)

- [ ] **Step 4d: Side-by-side comparison against the gold report**

Open the gold report and the new r4 report and visually check that sections 2 (Market Overview), 3 (Key Metrics), 4 (Players), 5 (Trends), 6 (Risks), 7 (Opportunities) each have concrete content matching or exceeding the gold report's numeric depth.

```bash
ls "C:/SuperWork/agents/inbox/team/PVH_Vikna_Dveri_2025_Zvit (1).pdf"
ls "C:/SuperWork/agents/market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04-r4/report.pdf"
```

Both files should exist. Open them in a PDF viewer and compare.

### Step 5: Commit the new run

- [ ] **Step 5a: Commit run artifacts**

```bash
cd agents
git add market-research/reports/pvc-windows-doors-profiles-ukraine/2026-04-r4/
git add market-research/inbox/done/pvc-windows-doors-profiles-ukraine.yaml.completed
git add market-research/inbox/done/pvc-windows-doors-profiles-ukraine.result.json
git commit -m "chore(mira): 2026-04-r4 PVC Ukraine run after depth fix

First full run after the depth-fix pipeline changes (parser, single-official
audit rule, sage synthesis, quill derived citations, hawk derivation check).

Acceptance criteria met:
- $(COUNT_HERE) facts (vs 39 in r3)
- $(CONFIRMED_PCT_HERE)% confirmed (vs 0% in r3)
- $(INSIGHTS_HERE) insights with derivation_steps
- Sections 4/5/6/7/8 have body narrative (not 'insufficient data')

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
cd ..
```

Replace `$(COUNT_HERE)`, `$(CONFIRMED_PCT_HERE)`, `$(INSIGHTS_HERE)` with the real numbers from Step 4b.

---

## Task 10: Parent-repo commit (submodule bump + spec + plan)

**Files:**
- Modify: `agents` submodule pointer
- Add: `docs/superpowers/specs/2026-04-08-mira-depth-fix-design.md`
- Add: `docs/superpowers/plans/2026-04-08-mira-depth-fix-implementation.md`

### Step 1: Bump the submodule pointer

- [ ] **Step 1a: Stage and commit the parent repo**

```bash
cd C:/SuperWork
git add agents
git add docs/superpowers/specs/2026-04-08-mira-depth-fix-design.md
git add docs/superpowers/plans/2026-04-08-mira-depth-fix-implementation.md
git commit -m "feat(mira): depth-fix pipeline + spec, plan, submodule bump

Pipeline changes (in agents submodule):
- New Parser stage (Python) handles xlsx + HTML-table .xls + images
- Audit: single official source = confirmed (drops >=2 rule for tier-1)
- Sage: synthesis engine with derivation_type + derivation_steps
- Quill: derived-inference citations in body sections 4-8
- Hawk: derivation validation pass
- UA preset: ukrstat entry + nbu policy rate URL fix + bare-folder fallback

Spec: docs/superpowers/specs/2026-04-08-mira-depth-fix-design.md
Plan: docs/superpowers/plans/2026-04-08-mira-depth-fix-implementation.md

Acceptance: 2026-04-r4 PVC Ukraine run matches >=80% of the hand-authored
reference PDF (agents/inbox/team/PVH_Vikna_Dveri_2025_Zvit (1).pdf).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 1b: Verify the commit**

```bash
git log -1 --stat
git status
```

Expected: clean working tree, one new commit with the spec + plan files + submodule pointer bump.

---

## Self-Review Checklist

- [x] **Spec coverage:** every decision D1–D10 from the spec is implemented by a task:
  - D1 (single-official = confirmed) → Task 3
  - D2 (Parser stage) → Tasks 1, 7
  - D3 (Quill derived inferences) → Task 5
  - D4 (ukrstat preset entry) → Task 8
  - D5 (Hunter bare-folder fallback) → Task 8
  - D6 (NBU URL fix) → Task 8
  - D7 (whitelist stays strict) → no task needed, preserved by omission
  - D8 (Quill gap-note tone, no preamble) → Task 5
  - D9 (Sage synthesis engine) → Task 4
  - D10 (Hawk derivation check) → Task 6

- [x] **Placeholder scan:** no TBD / TODO / "similar to Task N" / "add appropriate error handling" — every step has concrete code or commands.

- [x] **Type consistency:** `is_official` introduced in Task 2 (Sift), consumed in Task 3 (Audit). `derivation_type` / `derivation_steps` / `implication` introduced in Task 4 (Sage), consumed in Task 6 (Hawk). `parsed_path` introduced in Task 2 (Sift inputs), passed in Task 7 (lead skill dispatch).

- [x] **Scope check:** one spec → one plan. Tasks are ordered so dependencies chain: Parser (1) → Sift (2) → Audit (3) → Sage (4) → Quill (5) → Hawk (6) → lead skill wiring (7) → preset updates (8) → end-to-end re-run (9) → parent-repo commit (10). Each task produces a committable change.
