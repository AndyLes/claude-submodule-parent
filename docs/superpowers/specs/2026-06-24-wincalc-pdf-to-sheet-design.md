# WinCalc PDF → Google Sheet (window schedule) — Design

- **Date:** 2026-06-24
- **Owner (orchestration):** Bill · **Implementation:** Forge (backend)
- **Status:** Draft for user review
- **Trigger order:** 2663/37 — 33 West Elm Street, Brockton, MA 02301

## 1. Goal

Automate the transfer of a **WinCalc** window-quote PDF into a **prepared Google Sheet**
window schedule. Specifically:

1. Extract the **window diagram image** for every position and insert it into the sheet,
   matched to the correct row.
2. Generate / verify the **Description** column from the PDF.
3. **Control quantity and dimensions** — cross-check the PDF against the sheet and report
   any mismatch. Never silently overwrite curated data.

Built as a **reusable, parameterized tool** (any WinCalc PDF + any target sheet), not a
one-off script.

## 2. Background (discovered facts)

### 2.1 Source PDF (WinCalc export)

- Producer: `WinCalc x32 (3.5.46.177)`, VSGroup. PDF 1.5, A4 portrait (596×842 pt).
- For order 2663/37: **13 pages**. Pages 1–12 = position pages, page 13 = order summary.
- **2–3 positions per page** (variable — page 12 had 3). Do **not** assume a fixed count.
- Page summary (p.13): total **€28,822**, area **275.74 m²**, **164 units**.
- Per-position text block (Cyrillic) contains, in order:
  - position number (`1`, `2`, …) then `Конструкція` + system line
    (`EPSILON 76 (Вид з середини) | Siegenia Favorit | …`)
  - `засклення` (glazing formula) + `|| N шт.` (glass-unit count = 2 × window qty)
  - `Колір` (color), `профілі` (profile)
  - **`Виріб`** → next line `W*H` (mm) → next line **quantity** → price/discount/cost
  - options (`Опція` handles, anchor plate), `Шпрос` (muntins), `Спецпрофіль`, anchor plate
  - **`інші умови`** → next line = **position label** (`A`, `B`, …, `G'`, …, `Z`)
  - `Вага / Площа` → `weight кг / area м.кв / perimeter м.пог`
  - `Всього, без ПДВ` → position total

### 2.2 Images in the PDF

- Each page has a **1228×252 px banner** (company logo) at top (bbox y≈23–85) — **skip it**.
- Each position has one **543×543 px square diagram**, left column (x≈14–149), stacked
  vertically. Diagram count per page == position count per page.
- **Mapping rule:** within a page, sort position blocks top-to-bottom and diagrams
  top-to-bottom (by bbox y); pair by order. The block supplies the label. Validate that
  `#diagrams == #blocks` on every page.

### 2.3 Target Google Sheet

- File ID `1RsohmqdBCzzyuBOEGuwFggAdX-qQHFbxtEWNntdGwtg`, tab gid `572757771`.
- 24 data rows (positions A–Z incl. `G'`, skipping S/T/U). Units sum to **164** ✓.
- The order's data is **already filled** except the **image column** (empty) and several
  metric thermal columns (blank by design).
- Column layout (19 cols, 1-indexed):

| # | Header | Source / formula |
|---|--------|------------------|
| 1 | `#` | sequential 1..N |
| 2 | `Type` | PDF `інші умови` label (join key) |
| 3 | `<project address>` | **IMAGE** (window diagram). Identify by **position (col 3)**, not header text — header is the project address and changes per project. |
| 4 | `Width, in` | `round(W_mm / 25.4)` |
| 5 | `Height 1, in` | blank (second height for arched/trapezoid; rectangular ⇒ empty) |
| 6 | `Height, in` | `round(H_mm / 25.4)` |
| 7 | `Window Width, in` | = col 4 |
| 8 | `Window Height, in` | = col 6 |
| 9 | `Window Width, mm` | `round(W_mm/25.4) * 25.4` (inch-rounded back to mm) |
| 10 | `Window Height, mm` | `round(H_mm/25.4) * 25.4` |
| 11 | `Description` | generated template — see §4 |
| 12 | `Units` | PDF quantity (on `Виріб` row) |
| 13 | `sq ft` | `round(W_in * H_in / 144 * Units, 2)` |
| 14 | `kg` | blank (PDF weight available but unused) |
| 15–16 | `R m2K/W`, `U W/(m2K)` | blank |
| 17 | `R hrft2F/Btu` | blank |
| 18 | `U Btu/hrft2F` | constant `0.15` (config) |
| 19 | `SHGC` | constant `0.40` (config) |

**Key transformation insight:** dimensions are quoted to the US client in **inches,
rounded from the PDF mm**; the `mm` columns are then inches×25.4 (re-derived, *not* the raw
PDF mm). The validator must compare on the **inch-rounded** value, not raw mm.

## 3. Architecture — 3-stage pipeline

```
WinCalc PDF ──▶ [1] Parse & Extract (Python/PyMuPDF) ──▶ rows.json + A.png…Z.png + control.md
                                                              │
                          ┌───────────────────────────────────┤
                          ▼                                   ▼
            [2] Image insertion (Drive upload          [3] Control report
                + generated Apps Script)                (qty / dims / area / desc)
                          │
                          ▼
                Google Sheet (images in col 3)
```

Each stage is independently runnable and testable. Stage 1 produces a clean intermediate
(`rows.json` + cropped PNGs + report) that stages 2–3 consume.

## 4. Description generation (§ "опис")

Template (matches existing sheet format), produced per position:

```
Profile: {profile}  Color interior: {color_int}  Color exterior: {color_ext}
Glazing: {glazing_type}  Anchor plate: {anchor}  {glass_formula} {glass_codes} {tempered}
```

Field sources for this order (configurable map in §7):

| Field | Value | From |
|-------|-------|------|
| `profile` | `Optima 76 mm` | PDF `EPSILON 76` / `6 кам. 76мм` → config map |
| `color_int` | `White` | config default (PDF states exterior only) |
| `color_ext` | `Anthracite Grey exterior Renolit` | PDF `Renolit Антрацит текстура` → map |
| `glazing_type` | `triple glass` | derived from formula (3 panes `4-…-4-…-4`) |
| `anchor` | `Pre-installed` | PDF `Анкерна пластина попередньо встановлена` |
| `glass_formula` | `4CG1.0-16CUGRAr-4-16CUGRAr-4CG1.0 ESG` | PDF `засклення` (verbatim) |
| `glass_codes` | short normalized code, `-G` suffix when muntins present | **see Open Item O1** |
| `tempered` | `Tempered` (ESG ⇒ tempered) | PDF `ESG` marker |

Policy for this run: **generate + compare to existing Description, flag differences, do not
overwrite** (consistent with the dimension policy). For future empty sheets: generate and fill.

## 5. Stage 1 — Parse & Extract (Forge)

- **Lib:** PyMuPDF (`fitz`), already installed (1.27.2.3). Force UTF-8 I/O.
- Iterate pages; for each, parse position blocks (state machine over text lines, anchored on
  `Виріб` and `інші умови`; **do not** rely on a single brittle regex — the naive
  `findall` pairing mis-assigned label R→Q on p.10 and produced a phantom `0×0` on the
  summary page). Robust approach: per page, collect `Виріб` blocks and `інші умови` labels in
  document order, assert equal counts, pair by order, drop any `0×0`.
- For each position emit: `{label, w_mm, h_mm, w_in, h_in, qty, area_m2, glazing, color,
  profile, has_muntins, page}`.
- **Crop diagrams:** render/extract the 543×543 images (exclude the 1228×252 banner), map to
  blocks by y-order, save as `<label>.png` (sanitize `G'` → `G_prime.png`). Optionally
  auto-trim surrounding whitespace; default = keep the square as-is.
- **Self-checks:** Σqty == p.13 total (164); #positions == #diagrams == sheet row count;
  every label resolves to a sheet `Type`.

## 6. Stage 2 — Image insertion via Apps Script

Rationale: the available Google Drive integration can **read** the sheet but cannot **write**
cells/images; the Sheets API has no in-cell-image write. Apps Script is the reliable path and
runs in the user's own account (no external OAuth app).

- Upload the cropped PNGs to a Drive folder (via Drive `create_file`, or user drag-drop).
  **Confirm with user before writing to their Drive.**
- Generate a bound Apps Script that:
  - reads the image folder, matches each PNG to a row by `Type` label,
  - inserts into column 3 with `sheet.insertImage(blob, 3, row)` (embedded bytes; anchored
    over the cell), sized to the row height (default ~120 px, config),
  - is idempotent: clears prior inserted images in col 3 before re-inserting.
- User pastes the script (Extensions → Apps Script), runs once, authorizes.
- Trade-off noted: `insertImage` is an over-cell overlay, not a true in-cell `CellImage`
  (which would need a hosted URL). Overlay is acceptable for a schedule; revisit only if the
  user needs images to move with sort/filter.

## 7. Reusability & configuration

A `config.yaml` (or CLI flags) parameterizes per project:
`pdf_path`, `sheet_id`, `tab_gid`, `image_col` (default 3), `first_data_row`,
`profile_map` (`EPSILON 76 → Optima 76 mm`), `color_map`, `color_interior_default`,
`u_value`, `shgc`, `image_px`. New WinCalc order ⇒ new config row, same pipeline.

## 8. This-order run plan (2663/37)

1. Run Stage 1 → 24 PNGs + `rows.json` + `control.md`.
2. Deliver control report (see §9 findings).
3. On user OK: upload PNGs to Drive, generate Apps Script, user runs it → images land in col 3.
4. Generate Description per row, diff vs existing, report (do not overwrite).
   Data columns already present ⇒ no data writes this run.

## 9. Control findings (already computed)

- 24 windows parsed; Σqty **164** = PDF summary = sheet ✓.
- **2 dimension discrepancies** (PDF vs sheet, inch-rounded):
  - **B** — PDF `20×80″` (508×2021 mm) vs sheet `20×81″`. Height off 1″.
  - **P** — PDF `36×52″` (914×1321) vs sheet `52×36″` — **W↔H transposed** (likely a
    deliberate orientation fix; confirm).
- Other 22 positions: exact match. Policy: **flag only, no overwrite.**

## 10. Edge cases & robustness

- Label normalization: apostrophe variants in `G'`; letters skipped (S/T/U).
- Page with position count ≠ diagram count ⇒ hard error with page number.
- Label in PDF not found in sheet (or vice-versa) ⇒ listed in report, image still saved.
- Non-rectangular windows (two heights) ⇒ `Height 1` handling (none in this order; flag if seen).
- Re-run safety: Stage 2 clears prior col-3 images before inserting.

## 11. Open items for user review

- **O1 — `glass_codes` derivation.** The short variant codes
  (`4CG10-16-4-16-4CG10T-G … Tempered`) aren't fully derivable from one example. For this
  order Description is verify-only, so non-blocking; for future auto-fill we need the rule
  (when `-G`? when two codes vs one?).
- **O2 — Image size/style** in cell (default ~120 px overlay) — confirm preferred size.
- **O3 — Code location.** Propose `C:\SuperWork\projects\wincalc-to-sheet\` (own repo +
  `docs/`), per project convention.

## 12. Out of scope (YAGNI)

- Writing thermal metric columns (R/U SI) — left blank as in the sheet.
- True in-cell `CellImage` via hosted URLs.
- Price/cost transfer (not in the schedule's purpose).
- Reading non-WinCalc PDFs.
