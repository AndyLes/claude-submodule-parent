# WinCalc PDF → Google Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Python tool that parses a WinCalc window-quote PDF, crops each window diagram, generates per-window data + Description, and produces a Google Apps Script that inserts the images into a prepared Google Sheet while validating quantities/dimensions against the live sheet.

**Architecture:** Python package handles everything PDF-side (parse → transform → crop → `rows.json` + PNGs + generated `insert.gs`). The generated Apps Script handles everything sheet-side (read live rows, flag dimension/quantity mismatches to a `Control` tab, insert images into column C). No Google API auth — the user runs the bound script in their own account. PDF→sheet mapping is **by document order** (position N → row N), with the position label kept as a verification field.

**Tech Stack:** Python 3.12, PyMuPDF (`fitz`, installed 1.27.2.3), PyYAML, pytest. Google Apps Script (generated, not hand-run).

**Spec:** [2026-06-24-wincalc-pdf-to-sheet-design.md](../specs/2026-06-24-wincalc-pdf-to-sheet-design.md)

---

## File Structure

```
projects/wincalc-to-sheet/
  config.yaml                 # per-project params (paths, sheet id, maps, constants)
  requirements.txt
  README.md
  src/wincalc/
    __init__.py
    parse.py                  # PDF text → position dicts (Task 2)
    transform.py              # mm↔in, sq ft, glazing-type (Task 3)
    describe.py               # Description string builder (Task 4)
    images.py                 # crop 543×543 diagrams → <label>.png (Task 5)
    assemble.py               # merge parse+transform+describe → rows.json + self-checks (Task 6)
    appsscript.py             # render insert.gs from rows + config (Task 7)
    cli.py                    # pipeline entrypoint (Task 8)
    templates/insert.gs.tmpl  # Apps Script template (Task 7)
  tests/
    conftest.py
    fixtures/page_text_A_B.txt   # trimmed 2-block page text
    test_parse.py
    test_transform.py
    test_describe.py
    test_images.py
    test_assemble.py
    test_appsscript.py
  docs/ARCHITECTURE.md  docs/DECISIONS.md
  out/                       # generated: A.png…, rows.json, control_pdf.md, insert.gs
```

Each `src/wincalc/*.py` module has one responsibility and is imported by `assemble.py`/`cli.py`. Pure-logic modules (parse/transform/describe) are fully unit-tested; I/O modules (images/appsscript/cli) get integration tests against the real order PDF.

---

## Task 1: Scaffold project

**Files:**
- Create: `projects/wincalc-to-sheet/config.yaml`
- Create: `projects/wincalc-to-sheet/requirements.txt`
- Create: `projects/wincalc-to-sheet/src/wincalc/__init__.py` (empty)
- Create: `projects/wincalc-to-sheet/tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
pymupdf==1.27.2.3
PyYAML>=6
pytest>=8
```

- [ ] **Step 2: Create `config.yaml`**

```yaml
project: "2663/37 - 33 West Elm Street, Brockton, MA 02301"
pdf_path: "C:/1. Work/Windows US/2026 US Projects/2026-06 33 West Elm Street, Brockton, MA 02301/2663_37_33 West Elm Street, Brockton, MA 02301_клієнт.pdf"
sheet_id: "1RsohmqdBCzzyuBOEGuwFggAdX-qQHFbxtEWNntdGwtg"
tab_gid: 572757771
image_col: 3
type_col: 2
width_in_col: 4
height_in_col: 6
units_col: 12
desc_col: 11
first_data_row: 2
image_px: 120
drive_folder_id: ""        # filled after PNG upload
u_value_btu: 0.15
shgc: 0.40
spacer_mm: 16
color_interior_default: "White"
profile_map:
  "EPSILON 76": "Optima 76 mm"
color_exterior_map:
  "Renolit Антрацит текстура": "Anthracite Grey exterior Renolit"
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pytest, yaml

@pytest.fixture
def cfg():
    return yaml.safe_load((pathlib.Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8"))
```

- [ ] **Step 4: Commit**

```bash
git add projects/wincalc-to-sheet
git commit -m "chore(wincalc): scaffold project + config"
```

---

## Task 2: Parse positions from PDF text

PDF text per position block contains `засклення\n<formula>`, `Колір\n<color>`, `Виріб\n<W*H>\n<qty>`, `інші умови\n<label>`, `Вага / Площа\n<… / area м.кв / …>`, and `Шпрос…` when muntins are present. Within a page these markers alternate one-per-block, so we collect each marker list and pair by index, asserting equal counts (the robustness guard the naive regex lacked).

**Files:**
- Create: `src/wincalc/parse.py`
- Create: `tests/fixtures/page_text_A_B.txt`
- Test: `tests/test_parse.py`

- [ ] **Step 1: Create the fixture `tests/fixtures/page_text_A_B.txt`** (trimmed real page-1 text, two blocks)

```
1
Конструкція
EPSILON 76 (Вид з середини) | Siegenia Favorit | Вікна та Двері
засклення
4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG || 14 шт.
Колір
Renolit Антрацит текстура
профілі
6 кам. 76мм
Виріб
1245*2060
7
2 037,90
Шпрос
ламінований
16мм
інші умови
A
Вага / Площа
613,799 кг. / 17,581798 м.кв. / 44,701 м.пог.
Всього, без ПДВ
2
Конструкція
EPSILON 76 (Вид з середини) | Siegenia Favorit | Вікна та Двері
засклення
4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG || 8 шт.
Колір
Renolit Антрацит текстура
профілі
6 кам. 76мм
Виріб
508*2021
4
600,06
інші умови
B
Вага / Площа
154,230 кг. / 4,048137 м.кв. / 19,674 м.пог.
Всього, без ПДВ
```

- [ ] **Step 2: Write the failing test `tests/test_parse.py`**

```python
from wincalc.parse import parse_page_text

def test_parse_two_blocks():
    text = open("tests/fixtures/page_text_A_B.txt", encoding="utf-8").read()
    rows = parse_page_text(text, page=1)
    assert [r["label"] for r in rows] == ["A", "B"]
    a, b = rows
    assert (a["w_mm"], a["h_mm"], a["qty"]) == (1245, 2060, 7)
    assert a["muntins"] is True and b["muntins"] is False
    assert a["glazing"].startswith("4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG")
    assert a["system"] == "EPSILON 76"
    assert a["color"] == "Renolit Антрацит текстура"
    assert round(a["area_m2"], 3) == 17.582
    assert b["w_mm"] == 508 and b["h_mm"] == 2021
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wincalc.parse'`

- [ ] **Step 4: Implement `src/wincalc/parse.py`**

```python
import re
import fitz

_PROD = re.compile(r"Виріб\s*\n\s*(\d+)\*(\d+)\s*\n\s*(\d+)")
_LABEL = re.compile(r"інші умови\s*\n\s*([^\n]+)")
_GLAZ = re.compile(r"засклення\s*\n\s*([^\n]+)")
_SYS = re.compile(r"\n([A-ZЄ][^\n|]*?)\s*\(Вид")
_COLOR = re.compile(r"Колір\s*\n\s*([^\n]+)")
_AREA = re.compile(r"/\s*([\d ,]+)\s*м\.кв")


def _num(s):
    return float(s.replace(" ", "").replace(",", "."))


def parse_page_text(text, page):
    prods = [(int(w), int(h), int(q)) for w, h, q in _PROD.findall(text)]
    labels = [s.strip() for s in _LABEL.findall(text)]
    glaz = [s.strip() for s in _GLAZ.findall(text)]
    colors = [s.strip() for s in _COLOR.findall(text)]
    areas = [_num(s) for s in _AREA.findall(text)]
    systems = [s.strip() for s in _SYS.findall(text)]
    # muntins: a "Шпрос" between this Виріб and the next
    blocks = re.split(r"Виріб\s*\n", text)[1:]
    muntins = ["Шпрос" in b.split("Виріб")[0] for b in blocks]
    assert len(prods) == len(labels), f"page {page}: {len(prods)} products vs {len(labels)} labels"
    out = []
    for k, (w, h, q) in enumerate(prods):
        if w <= 0 or h <= 0:
            continue
        out.append({
            "page": page, "order": None, "label": labels[k],
            "w_mm": w, "h_mm": h, "qty": q,
            "glazing": glaz[k] if k < len(glaz) else None,
            "color": colors[k] if k < len(colors) else None,
            "system": systems[k] if k < len(systems) else None,
            "area_m2": areas[k] if k < len(areas) else None,
            "muntins": muntins[k] if k < len(muntins) else False,
        })
    return out


def parse_pdf(path):
    doc = fitz.open(path)
    rows = []
    for pno in range(doc.page_count):
        rows.extend(parse_page_text(doc[pno].get_text(), pno + 1))
    for i, r in enumerate(rows):
        r["order"] = i + 1
    return rows
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_parse.py -v`
Expected: PASS

- [ ] **Step 6: Add a real-PDF integration test, then commit**

Append to `tests/test_parse.py`:

```python
import os, yaml, pytest
from wincalc.parse import parse_pdf

def test_parse_real_pdf(cfg):
    if not os.path.exists(cfg["pdf_path"]):
        pytest.skip("order PDF not present")
    rows = parse_pdf(cfg["pdf_path"])
    rows = [r for r in rows if r["w_mm"] > 0]
    assert len(rows) == 24
    assert sum(r["qty"] for r in rows) == 164
```

Run: `python -m pytest tests/test_parse.py -v` → Expected: PASS (or 1 skip if PDF absent)

```bash
git add src/wincalc/parse.py tests/test_parse.py tests/fixtures/page_text_A_B.txt
git commit -m "feat(wincalc): parse positions from WinCalc PDF text"
```

---

## Task 3: Dimension & area transforms

**Files:**
- Create: `src/wincalc/transform.py`
- Test: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test `tests/test_transform.py`**

```python
from wincalc.transform import mm_to_in, in_to_mm, sq_ft, glazing_type

def test_mm_inch_roundtrip():
    assert mm_to_in(1245) == 49
    assert mm_to_in(2057) == 81
    assert mm_to_in(2021) == 80        # B: 79.6" rounds to 80, not the sheet's 81
    assert in_to_mm(81) == 2057
    assert in_to_mm(49) == 1245

def test_sq_ft():
    assert sq_ft(49, 81, 7) == 192.94
    assert sq_ft(36, 68, 27) == 459.0

def test_glazing_type():
    assert glazing_type("4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG", 16) == "triple glass"
    assert glazing_type("4-16-4", 16) == "double glass"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transform.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/wincalc/transform.py`**

```python
_PANES = {1: "single glass", 2: "double glass", 3: "triple glass", 4: "quad glass"}


def mm_to_in(mm):
    return round(mm / 25.4)


def in_to_mm(inch):
    return round(inch * 25.4)


def sq_ft(w_in, h_in, qty):
    return round(w_in * h_in / 144 * qty, 2)


def glazing_type(formula, spacer_mm):
    spacers = formula.count(str(spacer_mm))
    return _PANES.get(spacers + 1, f"{spacers + 1}-pane glass")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transform.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wincalc/transform.py tests/test_transform.py
git commit -m "feat(wincalc): mm/inch + sq ft + glazing-type transforms"
```

---

## Task 4: Description builder

Produces the canonical Description fields. The trailing short glass-codes (spec Open Item O1) are **excluded** — validation compares the canonical prefix only, so O1 is non-blocking.

**Files:**
- Create: `src/wincalc/describe.py`
- Test: `tests/test_describe.py`

- [ ] **Step 1: Write the failing test `tests/test_describe.py`**

```python
from wincalc.describe import build_description

def test_build_description(cfg):
    pos = {"system": "EPSILON 76", "color": "Renolit Антрацит текстура",
           "glazing": "4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG"}
    d = build_description(pos, cfg)
    assert d == ("Profile: Optima 76 mm  Color interior: White  "
                 "Color exterior: Anthracite Grey exterior Renolit  "
                 "Glazing: triple glass  Anchor plate: Pre-installed  "
                 "4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_describe.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/wincalc/describe.py`**

```python
from wincalc.transform import glazing_type


def build_description(pos, cfg):
    profile = cfg["profile_map"].get(pos["system"], pos["system"])
    color_ext = cfg["color_exterior_map"].get(pos["color"], pos["color"])
    gt = glazing_type(pos["glazing"], cfg["spacer_mm"])
    parts = [
        f"Profile: {profile}",
        f"Color interior: {cfg['color_interior_default']}",
        f"Color exterior: {color_ext}",
        f"Glazing: {gt}",
        "Anchor plate: Pre-installed",
        pos["glazing"],
    ]
    return "  ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_describe.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wincalc/describe.py tests/test_describe.py
git commit -m "feat(wincalc): canonical Description builder"
```

---

## Task 5: Crop window diagrams

The window diagram is the only ~square image per position (≈543×543 px); the page banner is 1228×252 (aspect > 2). Map diagrams to positions by **vertical (y) order within the page** — same order parse emits blocks. Filename uses the label, `'` → `_prime`.

**Files:**
- Create: `src/wincalc/images.py`
- Test: `tests/test_images.py`

- [ ] **Step 1: Write the failing integration test `tests/test_images.py`**

```python
import os, pytest
from wincalc.images import extract_diagrams

def test_extract_real_pdf(cfg, tmp_path):
    if not os.path.exists(cfg["pdf_path"]):
        pytest.skip("order PDF not present")
    mapping = extract_diagrams(cfg["pdf_path"], tmp_path)
    assert len(mapping) == 24
    assert "A" in mapping and "G'" in mapping
    for label, path in mapping.items():
        assert os.path.getsize(path) > 1000   # non-empty PNG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_images.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/wincalc/images.py`**

```python
import pathlib
import fitz
from wincalc.parse import parse_page_text


def _safe(label):
    return label.replace("'", "_prime")


def extract_diagrams(pdf_path, out_dir):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    mapping = {}
    for pno in range(doc.page_count):
        page = doc[pno]
        positions = [p for p in parse_page_text(page.get_text(), pno + 1) if p["w_mm"] > 0]
        if not positions:
            continue
        infos = [im for im in page.get_image_info(xrefs=True)
                 if 0.8 <= im["width"] / im["height"] <= 1.25]   # square ⇒ diagram
        infos.sort(key=lambda im: im["bbox"][1])                  # top→bottom
        assert len(infos) == len(positions), \
            f"page {pno+1}: {len(infos)} diagrams vs {len(positions)} positions"
        for pos, im in zip(positions, infos):
            pix = fitz.Pixmap(doc, im["xref"])
            if pix.n - pix.alpha >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            fp = out_dir / f"{_safe(pos['label'])}.png"
            pix.save(fp)
            mapping[pos["label"]] = str(fp)
    return mapping
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_images.py -v`
Expected: PASS (or skip if PDF absent)

- [ ] **Step 5: Commit**

```bash
git add src/wincalc/images.py tests/test_images.py
git commit -m "feat(wincalc): crop window diagrams mapped by y-order"
```

---

## Task 6: Assemble rows + self-checks

Merges parse + transform + describe into the final per-row records, attaches `sq_ft`, and runs PDF-side consistency checks (total qty, unique labels). Writes `out/rows.json` and `out/control_pdf.md`.

**Files:**
- Create: `src/wincalc/assemble.py`
- Test: `tests/test_assemble.py`

- [ ] **Step 1: Write the failing test `tests/test_assemble.py`**

```python
from wincalc.assemble import assemble_rows, self_check

def test_assemble(cfg):
    positions = [
        {"order":1,"label":"A","w_mm":1245,"h_mm":2060,"qty":7,"page":1,
         "system":"EPSILON 76","color":"Renolit Антрацит текстура",
         "glazing":"4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG","muntins":True,"area_m2":17.58},
    ]
    rows = assemble_rows(positions, cfg)
    r = rows[0]
    assert r["w_in"] == 49 and r["h_in"] == 81
    assert r["w_mm_out"] == 1245 and r["h_mm_out"] == 2057
    assert r["sq_ft"] == 192.94
    assert r["description"].startswith("Profile: Optima 76 mm")

def test_self_check_flags_total(cfg):
    rows = [{"label":"A","qty":7},{"label":"B","qty":4}]
    issues = self_check(rows, expected_total=164)
    assert any("total qty" in i for i in issues)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_assemble.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/wincalc/assemble.py`**

```python
import json
import pathlib
from collections import Counter
from wincalc.transform import mm_to_in, in_to_mm, sq_ft
from wincalc.describe import build_description


def assemble_rows(positions, cfg):
    rows = []
    for p in positions:
        w_in, h_in = mm_to_in(p["w_mm"]), mm_to_in(p["h_mm"])
        rows.append({
            "order": p["order"], "label": p["label"],
            "w_mm": p["w_mm"], "h_mm": p["h_mm"],
            "w_in": w_in, "h_in": h_in,
            "w_mm_out": in_to_mm(w_in), "h_mm_out": in_to_mm(h_in),
            "qty": p["qty"], "sq_ft": sq_ft(w_in, h_in, p["qty"]),
            "muntins": p.get("muntins", False),
            "description": build_description(p, cfg),
        })
    return rows


def self_check(rows, expected_total):
    issues = []
    total = sum(r["qty"] for r in rows)
    if total != expected_total:
        issues.append(f"total qty {total} != expected {expected_total}")
    dups = [l for l, c in Counter(r["label"] for r in rows).items() if c > 1]
    if dups:
        issues.append(f"duplicate labels: {dups}")
    return issues


def write_outputs(rows, issues, out_dir):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# PDF-side control report", "", f"Positions: {len(rows)}",
             f"Total qty: {sum(r['qty'] for r in rows)}", ""]
    lines += ["## Self-check issues"] + ([f"- {i}" for i in issues] or ["- none"])
    (out / "control_pdf.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_assemble.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wincalc/assemble.py tests/test_assemble.py
git commit -m "feat(wincalc): assemble rows.json + PDF-side self-checks"
```

---

## Task 7: Generate the Apps Script

Renders `out/insert.gs` from `rows.json` + config. The script (run by the user in their sheet) reads images from the Drive folder, maps PDF rows to sheet rows **by order** (label kept for the report), flags qty/dim mismatches to a `Control` tab, and inserts each image into the image column. Mapping by order avoids the label-mismatch fragility (e.g. the R/Q case).

**Files:**
- Create: `src/wincalc/templates/insert.gs.tmpl`
- Create: `src/wincalc/appsscript.py`
- Test: `tests/test_appsscript.py`

- [ ] **Step 1: Create `src/wincalc/templates/insert.gs.tmpl`**

```javascript
// AUTO-GENERATED by wincalc-to-sheet. Run run() from the Apps Script editor.
const ROWS = __ROWS_JSON__;
const CFG = __CFG_JSON__;

function run() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(__TAB_NAME__) || ss.getActiveSheet();
  const folder = DriveApp.getFolderById(CFG.drive_folder_id);
  const images = {};
  const it = folder.getFiles();
  while (it.hasNext()) { const f = it.next(); images[f.getName().replace(/\.[^.]+$/, "")] = f; }

  sheet.getImages().forEach(function (img) {
    if (img.getAnchorCell().getColumn() === CFG.image_col) img.remove();
  });

  const issues = [];
  for (let i = 0; i < ROWS.length; i++) {
    const p = ROWS[i];
    const row = CFG.first_data_row + i;                 // map BY ORDER
    const liveType = String(sheet.getRange(row, CFG.type_col).getValue()).trim();
    if (liveType && liveType !== p.label) issues.push([p.label, "label≠sheet", liveType, p.label]);
    const units = Number(sheet.getRange(row, CFG.units_col).getValue());
    if (units !== p.qty) issues.push([p.label, "qty", units, p.qty]);
    const wIn = Number(sheet.getRange(row, CFG.width_in_col).getValue());
    const hIn = Number(sheet.getRange(row, CFG.height_in_col).getValue());
    if (wIn !== p.w_in || hIn !== p.h_in)
      issues.push([p.label, "dims", wIn + "x" + hIn, p.w_in + "x" + p.h_in]);

    const key = p.label.replace("'", "_prime");
    const f = images[key] || images[p.label];
    if (!f) { issues.push([p.label, "image missing", "", ""]); continue; }
    sheet.setRowHeight(row, CFG.image_px + 8);
    sheet.insertImage(f.getBlob(), CFG.image_col, row).setWidth(CFG.image_px).setHeight(CFG.image_px);
  }
  writeControl(ss, issues);
}

function writeControl(ss, issues) {
  let s = ss.getSheetByName("Control");
  if (s) s.clear(); else s = ss.insertSheet("Control");
  s.getRange(1, 1, 1, 4).setValues([["Type", "Issue", "Sheet", "PDF"]]);
  if (issues.length) s.getRange(2, 1, issues.length, 4).setValues(issues);
  else s.getRange(2, 1).setValue("All checks passed.");
}
```

- [ ] **Step 2: Write the failing test `tests/test_appsscript.py`**

```python
import json
from wincalc.appsscript import render_script

def test_render(cfg):
    rows = [{"label": "A", "w_in": 49, "h_in": 81, "qty": 7}]
    cfg = {**cfg, "drive_folder_id": "FOLDER123"}
    gs = render_script(rows, cfg, tab_name="Sheet1")
    assert "FOLDER123" in gs
    assert '"label": "A"' in gs or '"label":"A"' in gs
    assert "__ROWS_JSON__" not in gs and "__CFG_JSON__" not in gs and "__TAB_NAME__" not in gs
    assert "insertImage" in gs
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_appsscript.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement `src/wincalc/appsscript.py`**

```python
import json
import pathlib

_TMPL = pathlib.Path(__file__).with_name("templates") / "insert.gs.tmpl"
_KEYS = ["image_col", "type_col", "width_in_col", "height_in_col", "units_col",
         "desc_col", "first_data_row", "image_px", "drive_folder_id"]


def render_script(rows, cfg, tab_name):
    slim = [{"label": r["label"], "w_in": r["w_in"], "h_in": r["h_in"], "qty": r["qty"]}
            for r in rows]
    cfg_js = {k: cfg[k] for k in _KEYS}
    tmpl = _TMPL.read_text(encoding="utf-8")
    return (tmpl
            .replace("__ROWS_JSON__", json.dumps(slim, ensure_ascii=False))
            .replace("__CFG_JSON__", json.dumps(cfg_js, ensure_ascii=False))
            .replace("__TAB_NAME__", json.dumps(tab_name)))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_appsscript.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/wincalc/appsscript.py src/wincalc/templates/insert.gs.tmpl tests/test_appsscript.py
git commit -m "feat(wincalc): generate Apps Script (order-mapped insert + control)"
```

---

## Task 8: CLI pipeline

Wires the stages: parse → assemble → write rows.json/report → crop images → render insert.gs. `--expected-total` defaults to 164 for this order; configurable.

**Files:**
- Create: `src/wincalc/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing integration test `tests/test_cli.py`**

```python
import os, json, pytest
from wincalc.cli import run_pipeline

def test_pipeline_real(cfg, tmp_path):
    if not os.path.exists(cfg["pdf_path"]):
        pytest.skip("order PDF not present")
    res = run_pipeline(cfg, out_dir=tmp_path, expected_total=164)
    rows = json.loads((tmp_path / "rows.json").read_text(encoding="utf-8"))
    assert len(rows) == 24
    assert (tmp_path / "insert.gs").exists()
    assert (tmp_path / "control_pdf.md").exists()
    assert len([f for f in os.listdir(tmp_path) if f.endswith(".png")]) == 24
    assert res["png_count"] == 24
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/wincalc/cli.py`**

```python
import argparse
import pathlib
import yaml
from wincalc.parse import parse_pdf
from wincalc.assemble import assemble_rows, self_check, write_outputs
from wincalc.images import extract_diagrams
from wincalc.appsscript import render_script


def run_pipeline(cfg, out_dir, expected_total=164, tab_name="Sheet1"):
    out_dir = pathlib.Path(out_dir)
    positions = [p for p in parse_pdf(cfg["pdf_path"]) if p["w_mm"] > 0]
    rows = assemble_rows(positions, cfg)
    issues = self_check(rows, expected_total)
    write_outputs(rows, issues, out_dir)
    mapping = extract_diagrams(cfg["pdf_path"], out_dir)
    gs = render_script(rows, cfg, tab_name)
    (out_dir / "insert.gs").write_text(gs, encoding="utf-8")
    return {"rows": len(rows), "png_count": len(mapping), "issues": issues}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="out")
    ap.add_argument("--expected-total", type=int, default=164)
    ap.add_argument("--tab-name", default="Sheet1")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    res = run_pipeline(cfg, a.out, a.expected_total, a.tab_name)
    print(res)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (or skip if PDF absent)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: all PASS (PDF-dependent tests may skip if the file is absent)

- [ ] **Step 6: Commit**

```bash
git add src/wincalc/cli.py tests/test_cli.py
git commit -m "feat(wincalc): CLI pipeline wiring all stages"
```

---

## Task 9: Project docs

**Files:**
- Create: `projects/wincalc-to-sheet/README.md`
- Create: `projects/wincalc-to-sheet/docs/ARCHITECTURE.md`
- Create: `projects/wincalc-to-sheet/docs/DECISIONS.md`

- [ ] **Step 1: Write `README.md`** (usage)

````markdown
# wincalc-to-sheet

Parse a WinCalc window-quote PDF, crop window diagrams, and generate an Apps Script
that inserts the images into a prepared Google Sheet while validating qty/dimensions.

## Run
```bash
pip install -r requirements.txt
python -m wincalc.cli --config config.yaml --out out --expected-total 164
```
Outputs to `out/`: `rows.json`, `control_pdf.md`, `<label>.png` ×24, `insert.gs`.

## Insert images into the sheet
1. Upload the `out/*.png` files to a Google Drive folder; put its id in `config.yaml`
   (`drive_folder_id`) and re-run (regenerates `insert.gs`).
2. Open the target sheet → Extensions → Apps Script → paste `out/insert.gs` → Run `run()`.
3. Review the `Control` tab for any qty/dimension/label flags.
````

- [ ] **Step 2: Write `docs/ARCHITECTURE.md`** (the §3 diagram from the spec + module table) and `docs/DECISIONS.md` (record: order-based mapping over label-join; Apps Script over Sheets API; flag-don't-overwrite; canonical-prefix Description compare).

```markdown
# Decisions
- PDF→sheet mapping is by document order; label is a verification field only
  (PDF label R parsed as Q on p.10 — order-join is robust to this).
- Image insertion via bound Apps Script (no Google API auth); over-cell insertImage.
- Validation flags discrepancies to a Control tab; never overwrites curated data.
- Description compared on canonical prefix; trailing glass-codes (O1) excluded.
```

- [ ] **Step 3: Commit**

```bash
git add projects/wincalc-to-sheet/README.md projects/wincalc-to-sheet/docs
git commit -m "docs(wincalc): README + architecture + decisions"
```

---

## Self-Review

**Spec coverage:**
- §1 goals (images, Description, control) → Tasks 5, 4, 7 ✓
- §2.1 PDF parse → Task 2 ✓
- §2.2 image y-mapping → Task 5 ✓
- §2.3 column contract (mm↔in, sq ft) → Tasks 3, 6 ✓
- §4 Description → Task 4 ✓
- §5 self-checks → Task 6 ✓
- §6 Apps Script insertion → Task 7 ✓
- §7 reusable config → Task 1 ✓
- §9 control findings (B, P) → Task 7 (live flags) + Task 3 test asserts B=80″ ✓
- §10 edge cases (count mismatch, label normalize, re-run clear) → Tasks 5, 7 ✓

**Placeholder scan:** No TBD/TODO; every code step is complete. O1 explicitly scoped out of validation (canonical-prefix compare), not left as a gap.

**Type consistency:** `parse_page_text`/`parse_pdf` emit dicts with `label,w_mm,h_mm,qty,glazing,color,system,muntins,area_m2,order`; `assemble_rows` consumes those + emits `w_in,h_in,w_mm_out,h_mm_out,sq_ft,description`; `render_script` consumes `label,w_in,h_in,qty`. `extract_diagrams` returns `{label: path}`. Config keys used in `appsscript._KEYS` all exist in `config.yaml`. Consistent.

---

## Execution Handoff

Per Bill's operating model the **build is delegated to Forge** (backend). Two ways to drive it:

1. **Subagent-Driven (recommended)** — dispatch Forge per task with review between tasks.
2. **Inline Execution** — execute tasks in-session with checkpoints.

Note: the image-upload-to-Drive step (between Task 8 run and Apps Script run) writes PNGs to the user's Drive — **confirm with the user before that write**.
