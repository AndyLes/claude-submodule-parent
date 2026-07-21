# Tender-Radar Plan 2 — MA Source Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add the two Massachusetts httpx sources — DCAMM (Bid Express) and COMMBUYS — to Tender-Radar, plus a relevance-filter fix, so the daily cloud run covers MA filed sub-bids (the project's core value), not just NYC.

**Architecture:** Each adapter implements `BaseSource.fetch() -> list[RawTender]` (contract in `ingest/base.py`), registered in `main.py`'s `SOURCES`. Reference implementation: `ingest/sources/nyc_socrata.py`. Adapters are httpx-only (no firecrawl/Playwright) — BidDocs/NH DAS (firecrawl-dependent) are deferred to a later plan. Tests are fixture-driven (real captured pages in `research/recon/fixtures/`), zero network.

**Tech Stack:** Python 3.12, httpx, BeautifulSoup4+lxml (new — DCAMM/COMMBUYS parse HTML/XML), pytest.

**Detailed portal specs (READ THESE — they are the source of truth for selectors/endpoints):**
- DCAMM: `research/recon/dcamm.md` + fixture `research/recon/fixtures/dcamm_listing.html`
- COMMBUYS: `research/recon/commbuys.md` + fixtures `research/recon/fixtures/commbuys_openbids_plain.html`, `post_classid_30-17.xml`, `post_keyword_window.xml`

**Repo:** `C:\SuperWork\projects\tender-radar` (own git repo, on `master`, pushed to GitHub AndyLes/tender-radar). Cloud secrets already set; these two sources need NO new secrets.

---

### Task 1: Relevance-filter fix — exclude window treatments/blinds/shades

**Why:** The live cloud smoke ingested false positives ("Blanket Order for Window Treatment", "HRA Window Blinds & Shades Replacement") — these are soft goods (UNSPSC 52-13), not structural glazing. Tighten `exclude_keywords`.

**Files:**
- Modify: `config/relevance.json`
- Test: `tests/test_filter.py`

- [ ] **Step 1: Add failing test** to `tests/test_filter.py`:

```python
def test_window_treatments_excluded():
    import config
    f = RelevanceFilter(config.load_relevance())
    assert not f.is_relevant(title="Blanket Order for Window Treatment BX & QNS", trade_classes=[])
    assert not f.is_relevant(title="HRA Window Blinds & Shades Replacement Services", trade_classes=[])
    assert not f.is_relevant(title="Roller Shades and Drapery Installation", trade_classes=[])
    # genuine glazing still passes:
    assert f.is_relevant(title="Police Station Window Replacement", trade_classes=[])
    assert f.is_relevant(title="Facade Repairs", trade_classes=["Glass and Glazing"])
```

- [ ] **Step 2: Run** `.venv\Scripts\pytest tests/test_filter.py::test_window_treatments_excluded -v` → FAIL (treatments currently pass).

- [ ] **Step 3:** Add to `config/relevance.json` `exclude_keywords` (keep existing entries): `"window treatment"`, `"window blind"`, `"window shade"`, `"blinds & shades"`, `"blinds and shades"`, `"roller shade"`, `"drapery"`, `"window film"`. (Note: bare "shades"/"blinds" would be too broad; use the phrases above.)

- [ ] **Step 4: Run** the test → PASS. Then full suite `.venv\Scripts\pytest -v` → all green (still 41+).

- [ ] **Step 5: Commit** `fix(ingest): exclude window treatments/blinds/shades from relevance`.

---

### Task 2: DCAMM (Bid Express) adapter

**Files:**
- Create: `ingest/sources/dcamm.py`
- Modify: `requirements.txt` (add `beautifulsoup4>=4.12`, `lxml>=5.0`)
- Test: `tests/test_dcamm.py`
- Fixture (already committed): `research/recon/fixtures/dcamm_listing.html`

**Full spec:** `research/recon/dcamm.md`. Key facts the implementer MUST honor:
- One `GET https://www.bidexpress.com/businesses/10279/home` with a browser-like User-Agent. httpx-only, no login. Parse the OPEN table `table#solicitations tbody tr[id^="Solicitation_"]` (the `id^=` filter skips the junk `tr.flash` row). Do NOT parse `#closed_solicitation_list` (that's archive; ignore pagination entirely for live monitoring).
- Per row → RawTender: `external_id` = `tr["id"]` minus `"Solicitation_"`; `title` = `td[id$="_Number"] > a` text; `bid_deadline` = `td[id$="_Deadline"]` text parsed `"%m/%d/%Y %I:%M %p"` after stripping `" UTC"`, `tzinfo=timezone.utc`; `listing_url` = `https://www.bidexpress.com/solicitations/{external_id}`; `owner` = `"DCAMM"`; `state` = `"MA"`; `source` = `"dcamm_bidexpress"`; `plans_url=None`.
- **CRITICAL — `trade_classes` from the description, not the title.** Titles are often bare codes ("HCC2301 Trade RFB"); trades live in `td[id$="_Number"] > div.desc-dialog` (attribute `data-popup-content` OR `.get_text()` — read ONE). Parse the trade list that follows `"Trade Categor(y|ies):"` / `"Filed Sub-Bid(s):"` / `"Trade Contractor Packages:"`, split on `;`, strip each and any trailing `($amount)`. Normalize `&amp;`→`&` and treat `&`≡`and` so "Glass & Glazing" and "Glass and Glazing" both match. If no trade-list phrasing is found, set `trade_classes=[]` (the row will be dropped by the relevance filter — correct for non-construction MMP maintenance rows).
- `est_value`: opportunistic — regex per-trade `Trade ($amount)` in the description; `None` when absent (classic filed sub-bids have none). See dcamm.md §2b.

- [ ] **Step 1: Write failing test `tests/test_dcamm.py`** using the committed fixture. Mock httpx with `MockTransport` returning the fixture HTML for the business-home GET. Assertions (verify exact expectations against the fixture content first):
  - `fetch()` returns the OPEN solicitations only (footer count in fixture = "10 Solicitations"), not closed-archive rows.
  - The `tr.flash` junk row is not ingested.
  - STC2202 (`external_id` "47767") → `trade_classes` contains a "Glass and Glazing"-normalized entry; `title` starts "STC2202"; `bid_deadline` is tz-aware UTC.
  - MIL2201 → `est_value` parsed for its Glass & Glazing package (`32500.0` per recon) — or whichever trade the test targets; assert a non-None float.
  - A row whose description has no trade phrasing (e.g. an "MMP" maintenance contract, if present in the open set) → `trade_classes == []`.
  - `source == "dcamm_bidexpress"`, `state == "MA"`, `owner == "DCAMM"` for all.

- [ ] **Step 2: Run** → FAIL (ImportError).
- [ ] **Step 3: Add** `beautifulsoup4>=4.12` + `lxml>=5.0` to `requirements.txt`; `.venv\Scripts\pip install -r requirements.txt`.
- [ ] **Step 4: Implement** `ingest/sources/dcamm.py` per dcamm.md. Wrap the GET in the adapter; on any parse/HTTP error let it raise (runner isolates per BaseSource contract). bs4 with `"lxml"` parser.
- [ ] **Step 5: Run** `tests/test_dcamm.py` → PASS.
- [ ] **Step 6: Live smoke** (network, not in suite): `.venv\Scripts\python -c "from ingest.sources.dcamm import DcammSource; rs=DcammSource().fetch(); print(len(rs)); [print(r.external_id, r.trade_classes, r.title[:40]) for r in rs[:8]]"` → prints the current open set. Report count + a couple rows. (If bidexpress returns 403 to the httpx UA, set a browser UA per recon §6.)
- [ ] **Step 7: Commit** `feat(ingest): DCAMM Bid Express adapter (trades-from-description)`.

---

### Task 3: COMMBUYS adapter

**Files:**
- Create: `ingest/sources/commbuys.py`
- Test: `tests/test_commbuys.py`
- Fixtures (already committed): `research/recon/fixtures/commbuys_openbids_plain.html`, `post_classid_30-17.xml`, `post_keyword_window.xml`

**Full spec:** `research/recon/commbuys.md` (§2 mechanics, §3 field map, §8 pseudocode). Key facts:
- Bootstrap `GET /bso/view/search/external/advancedSearchBid.xhtml?openBids=true` (browser UA, cookie jar). Scrape from the HTML: `javax.faces.ViewState` value, `_csrf` value, and the search source component id via regex `searchNew.*?s:"(bidSearchForm:j_idt\d+)"` (do NOT hardcode `j_idt381` — it shifts on redeploy).
- Then JSF-AJAX POSTs to the same URL (headers `Faces-Request: partial/ajax`, `X-Requested-With: XMLHttpRequest`, form body per commbuys.md §2b): one POST with `classId=30-17` (UNSPSC family "Doors and windows and glass"), plus one POST per keyword in `["window","glazing","glass","curtain wall","storefront","fenestration"]` with `desc=<kw>`. Union all results, dedupe by docId. Each set is <25 rows → no pagination.
- Parse each response as XML `<partial-response>`, extract the `advSearchResults` `<update>` CDATA, parse that inner HTML, select `tbody[id="bidSearchResultsForm:bidResultId_data"] > tr[data-ri]`. Per-row tds (see §3 table): td0 anchor → `docId` (external_id) + href → listing_url (`https://www.commbuys.com`+href); td2 = Organization (owner); td6 = Description (title); td7 = Bid Opening Date parsed `"%m/%d/%Y %H:%M:%S"` as America/New_York → bid_deadline (store tz-aware; use `zoneinfo.ZoneInfo("America/New_York")`); td10 = status (informational). `source="commbuys"`, `state="MA"`.
- Refresh ViewState from each response's tail `<update id="…ViewState…">` if chaining on one session (or just reuse the bootstrap ViewState per POST — simplest; verify against fixture behavior).

- [ ] **Step 1: Write failing test `tests/test_commbuys.py`.** Use `MockTransport` keyed on request: the bootstrap GET → `commbuys_openbids_plain.html`; a POST whose body contains `classId=30-17` → `post_classid_30-17.xml`; a POST whose body contains `desc=window` → `post_keyword_window.xml`; any other POST (other keywords) → a minimal empty `<partial-response>` (no rows). Assertions (verify counts against fixtures first): classId pass yields 6 rows, `desc=window` yields 7; union dedupes by docId (some overlap possible); a known docId (e.g. `BD-21-1576-TYN01-TYN01-131377`, Tyngsborough Police Station Window Replacement) maps to `title` "Police Station Window Replacement", `owner` "Town of Tyngsborough", tz-aware `bid_deadline`, `listing_url` starting `https://www.commbuys.com/bso/external/bidDetail.sda?docId=`. All `source=="commbuys"`, `state=="MA"`.
- [ ] **Step 2: Run** → FAIL (ImportError).
- [ ] **Step 3: Implement** `ingest/sources/commbuys.py` per commbuys.md §8. Reuse bs4 (Task 2 added it). Parse partial-response XML with `lxml.etree` or bs4 `features="xml"`; CDATA inner HTML with bs4 lxml. Bootstrap-once-then-POSTs on a single `httpx.Client` with cookie jar; browser UA. On error raise (runner isolates).
- [ ] **Step 4: Run** `tests/test_commbuys.py` → PASS.
- [ ] **Step 5: Live smoke** (network): `.venv\Scripts\python -c "from ingest.sources.commbuys import CommbuysSource; rs=CommbuysSource().fetch(); print(len(rs)); [print(r.external_id, r.title[:45]) for r in rs[:8]]"` → report count + rows. (COMMBUYS open board shifts daily; expect a handful of window/door/glass bids.)
- [ ] **Step 6: Commit** `feat(ingest): COMMBUYS adapter (JSF bootstrap + UNSPSC 30-17 + keyword union)`.

---

### Task 4: Register MA sources + integration verify

**Files:**
- Modify: `main.py` (`SOURCES` list)
- Test: `tests/test_run_once.py` or a small integration assertion

- [ ] **Step 1:** In `main.py`, extend `SOURCES` to `[NycSocrataSource(), DcammSource(), CommbuysSource()]` (import both). Keep the comment noting BidDocs/NH deferred.
- [ ] **Step 2:** Full suite `.venv\Scripts\pytest -v` → all green.
- [ ] **Step 3: Local smoke against Supabase** (real end-to-end, all 3 sources) — set `TR_DATABASE_URL` env to the Supabase session-pooler URL (ask the controller for it; do NOT hardcode/commit it), run `run_once.py`, confirm `ingest stats` shows all three sources with `fetched/relevant/new` and no source errored (per-source isolation means one failure won't abort — check the stats dict for any `{"error":...}`). Report the stats line.
- [ ] **Step 4: Commit** `feat(ingest): register DCAMM + COMMBUYS in SOURCES`. Push to GitHub (`git push`), and note the next daily cron (or a manual `workflow_dispatch`) will run all three in the cloud.

---

## Out of scope (later plans)
- BidDocs (Vaadin — firecrawl render) + NH DAS (Akamai — firecrawl-stealth CSV): need a firecrawl fetch layer + `FIRECRAWL_API_KEY` secret. Introduce an injectable fetcher then.
- CTsource + RI OSP (shared WebProcure JSON API, customerid 51/46): next httpx batch after MA — includes bid-results/price data (feeds Plan 3 analytics).
- Bid-results/award collection (Plan 3), analytics/price normalization (Plan 4).

## Self-review notes
- Spec coverage: relevance fix + DCAMM + COMMBUYS + registration all tasked; selectors/endpoints delegated to committed recon docs (source of truth) rather than duplicated. Fixtures already committed.
- DCAMM's critical divergence (trades-from-description, not title) is called out explicitly in Task 2.
- COMMBUYS statefulness (ViewState/_csrf/cookies, runtime j_idt discovery) captured in Task 3.
- No new secrets needed (both httpx). Cloud picks them up automatically after push.
