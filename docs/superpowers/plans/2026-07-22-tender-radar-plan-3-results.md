# Tender-Radar Plan 3 — Results Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Collect bid results (bidders, amounts, winner) from awarded CT/RI window solicitations into a `bid_results` table, compute competitor & bid-spread stats, and deliver a weekly Telegram report — the competitor/price intelligence the user asked for.

**Architecture:** Extends the modular monolith (`projects/tender-radar/`). New `results/` module (parse → fetch → collect) reuses the existing WebProcure client (SSL fix + `_search_terms`). New `analytics/` module computes aggregates and the weekly report. `bid_results` is a new storage table + repo. Collection runs daily after ingest; the weekly report fires on a configured weekday. Design spec: `docs/superpowers/specs/2026-07-22-tender-radar-plan-3-results-design.md`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, httpx, BeautifulSoup4 (already a dep from DCAMM), pytest. No new dependencies.

**Repo:** `C:\SuperWork\projects\tender-radar` (own git repo, `master`, GitHub AndyLes/tender-radar, cloud daily.yml). All paths relative to it. Suite currently 78 green.

---

### Task 1: Storage — `bid_results` table + `BidResultRepo`

**Files:**
- Modify: `storage/models.py`
- Modify: `storage/repo.py`
- Test: `tests/test_bid_results_repo.py`

- [ ] **Step 1: Write the failing test `tests/test_bid_results_repo.py`**

```python
from datetime import datetime, timezone

from storage.repo import BidResultRepo


def _bid(bidder="Kapiloff's Glass", amount=100000.0, is_winner=False, eid="115686"):
    return dict(source="ctsource", external_id=eid, project_title="AASF Window Replacement",
                bidder_name=bidder, amount=amount, is_winner=is_winner,
                award_date=datetime(2026, 6, 1, tzinfo=timezone.utc))


def test_upsert_inserts_then_dedupes(session):
    repo = BidResultRepo(session)
    r1, created1 = repo.upsert(_bid())
    assert created1 is True
    r2, created2 = repo.upsert(_bid(amount=105000.0))  # same (source, external_id, bidder) -> update
    assert created2 is False
    assert r2.id == r1.id
    assert r2.amount == 105000.0
    assert session.query(type(r1)).count() == 1


def test_distinct_bidders_coexist(session):
    repo = BidResultRepo(session)
    repo.upsert(_bid(bidder="A"))
    repo.upsert(_bid(bidder="B"))
    session.commit()
    assert repo.count() == 2


def test_since_returns_recent(session):
    repo = BidResultRepo(session)
    repo.upsert(_bid(bidder="A"))
    session.commit()
    cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert len(repo.collected_since(cutoff)) == 1
    future = datetime(2999, 1, 1, tzinfo=timezone.utc)
    assert repo.collected_since(future) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_bid_results_repo.py -v`
Expected: FAIL with ImportError (`BidResultRepo`).

- [ ] **Step 3: Add the model to `storage/models.py`** (append after `DigestLog`)

```python
class BidResult(Base):
    __tablename__ = "bid_results"
    __table_args__ = (
        UniqueConstraint("source", "external_id", "bidder_name", name="uq_bidresult_src_ext_bidder"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    project_title: Mapped[str] = mapped_column(Text)
    bidder_name: Mapped[str] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Float, default=None)   # None for RI (no $)
    is_winner: Mapped[bool] = mapped_column(default=False)
    award_date: Mapped[datetime | None] = mapped_column(AwareDateTime, default=None)
    collected_at: Mapped[datetime] = mapped_column(AwareDateTime)
```

(Requires `Boolean` support — SQLAlchemy maps `Mapped[bool]` automatically; no import change needed. `Float`, `String`, `Text`, `UniqueConstraint`, `AwareDateTime` are already imported in this file.)

- [ ] **Step 4: Add `BidResultRepo` to `storage/repo.py`** (append; `update`, `select`, `Session`, `_now` already imported/defined in this file)

```python
from storage.models import BidResult  # add to the existing storage.models import line


class BidResultRepo:
    def __init__(self, session: Session):
        self.s = session

    def upsert(self, b: dict) -> tuple[BidResult, bool]:
        existing = self.s.scalar(
            select(BidResult).where(
                BidResult.source == b["source"],
                BidResult.external_id == b["external_id"],
                BidResult.bidder_name == b["bidder_name"],
            )
        )
        if existing:
            existing.amount = b.get("amount") if b.get("amount") is not None else existing.amount
            existing.is_winner = b.get("is_winner", existing.is_winner)
            existing.project_title = b.get("project_title") or existing.project_title
            existing.award_date = b.get("award_date") or existing.award_date
            return existing, False
        r = BidResult(
            source=b["source"], external_id=b["external_id"], project_title=b["project_title"],
            bidder_name=b["bidder_name"], amount=b.get("amount"), is_winner=b.get("is_winner", False),
            award_date=b.get("award_date"), collected_at=_now(),
        )
        self.s.add(r)
        self.s.flush()
        return r, True

    def count(self) -> int:
        return self.s.scalar(select(func.count()).select_from(BidResult)) or 0

    def collected_since(self, cutoff: datetime) -> list[BidResult]:
        return list(self.s.scalars(
            select(BidResult).where(BidResult.collected_at >= cutoff).order_by(BidResult.external_id)
        ))

    def all_results(self) -> list[BidResult]:
        return list(self.s.scalars(select(BidResult)))
```

Add `func` to the top-of-file sqlalchemy import: change `from sqlalchemy import select, update` → `from sqlalchemy import func, select, update`. Add `from datetime import datetime` if not already imported (it is used via `_now`; confirm `datetime` is importable — add `from datetime import datetime` to the imports if absent).

- [ ] **Step 5: Run to verify it passes**

Run: `.venv\Scripts\pytest tests/test_bid_results_repo.py -v`
Expected: 3 PASS. Then full suite `.venv\Scripts\pytest -v` → all green (81).

- [ ] **Step 6: Commit**

```powershell
git add -A; git commit -m "feat(storage): bid_results table + BidResultRepo"
```

---

### Task 2: `results/parse.py` — customReport HTML parser

**Files:**
- Create: `results/__init__.py` (empty), `results/parse.py`
- Test: `tests/test_results_parse.py`
- Fixtures (already committed): `research/recon/fixtures/ctsource_bidtab.html` (CT priced tabulation — 5 vendors, base/supplemental/total $), `research/recon/fixtures/ri_osp_bidopening.html` (RI Bid Opening / Tentative / Final Award — vendors + winner, NO $)

**Spec:** `research/recon/ctsource.md` §3 (priced-table flavor + `$` regex `\$\s*[\d,]+\.\d{2}`, nbsp/U+FFFD mojibake), `research/recon/ri_osp.md` §3 (vendor-list flavor: "Awarded Vendors" / "Responded Vendors"; no amounts).

**Interface:**
```python
from dataclasses import dataclass

@dataclass
class ParsedBid:
    bidder_name: str
    amount: float | None      # None when the report carries no $ (RI, CT vendor-list towns)
    is_winner: bool

def parse_custom_report(html: str) -> list[ParsedBid]:
    """Parse a WebProcure bidAwardPublish[].customReport HTML string into bids.
    Two flavors auto-detected: a priced <table> (vendors + $ totals) or a vendor-list
    ('Awarded Vendors' / 'Responded Vendors' <ul>s). is_winner=True ONLY for names in an
    explicit 'Awarded Vendors' section; never inferred from lowest amount."""
```

- [ ] **Step 1: Read BOTH fixtures** to derive exact expectations (vendor names, totals, which section marks the winner). Your assertions must match the real fixture content, not the recon paraphrase.

- [ ] **Step 2: Write `tests/test_results_parse.py`** asserting, from the REAL fixtures:
  - CT priced (`ctsource_bidtab.html`): returns 5 ParsedBid; each has a positive float `amount` (the vendor TOTAL, last `$` column); e.g. Redwood Construction total 785270.0 (verify exact value in fixture); mojibake around `$` is stripped so amounts parse cleanly.
  - RI vendor-list (`ri_osp_bidopening.html`): returns the responded vendors (e.g. "Napco, Inc", "Krystal Glass LLC", "Dubon Masonry Construction, LLC" — verify) with `amount is None`; exactly the awarded vendor ("Napco, Inc") has `is_winner=True`, the others `is_winner=False`.
  - A malformed/empty html string → returns `[]` (no exception).

- [ ] **Step 3: Run → FAIL** (ImportError). **Step 4: Implement `results/parse.py`** (bs4 `"lxml"`, the `$` regex above, section detection for "Awarded Vendors"). **Step 5: Run → PASS.** Full suite green.

- [ ] **Step 6: Commit**

```powershell
git add -A; git commit -m "feat(results): customReport parser (priced-table + vendor-list flavors)"
```

---

### Task 3: `results/webprocure_results.py` — fetch awarded records + detail

**Files:**
- Create: `results/webprocure_results.py`
- Test: `tests/test_webprocure_results.py`

Reuse from `ingest/sources/webprocure.py`: `_build_ssl_context`, `_USER_AGENT`, `SEARCH_URL`, `PAGE_SIZE`, `HARD_CAP`, `_search_terms`. Detail endpoint (recon ri_osp.md §6): `https://webprocure.proactiscloud.com/wp-full-text-search/soldetail/{bidid}?customerid={cid}`.

- [ ] **Step 1: Write the failing test `tests/test_webprocure_results.py`**

```python
import httpx

from results.webprocure_results import ResultsFetcher

AWARDED_PAGE = {  # minimal shape mirroring the real search/sols response
    "hits": 1,
    "records": [{
        "bidid": 115686, "bidNumber": "RFB 7635", "title": "AASF Window Replacement",
        "bidAwardPublish": [{"title": "Award Report", "pubDate": 1750000000000,
                             "customReport": "<table><tr><td>1</td><td>Kapiloff</td><td>$100,000.00</td></tr></table>"}],
    }],
}
DETAIL = {"hits": 1, "records": [AWARDED_PAGE["records"][0]]}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_awarded_returns_records_with_awards():
    def handler(request):
        params = dict(request.url.params)
        if "soldetail" in str(request.url):
            return httpx.Response(200, json=DETAIL)
        if int(params.get("from", "0")) > 0:
            return httpx.Response(200, json={"hits": 1, "records": []})
        assert params["f"] == "ps=Awarded"
        return httpx.Response(200, json=AWARDED_PAGE)

    f = ResultsFetcher(customer_id="51", client=_client(handler))
    recs = f.fetch_awarded()
    assert len(recs) == 1
    assert recs[0]["bidid"] == 115686
    assert recs[0]["bidAwardPublish"]


def test_fetch_detail_returns_single_record():
    def handler(request):
        return httpx.Response(200, json=DETAIL)

    f = ResultsFetcher(customer_id="51", client=_client(handler))
    rec = f.fetch_detail(115686)
    assert rec["bidid"] == 115686
```

- [ ] **Step 2: Run → FAIL** (ImportError).

- [ ] **Step 3: Implement `results/webprocure_results.py`**

```python
"""Fetch awarded/closed WebProcure records (their bidAwardPublish[] carries the customReport
results HTML). Reuses ingest.sources.webprocure's client/SSL/search constants; differs only
in f=ps=Awarded (vs the tender feed's ps=Open) + a per-bidid soldetail lookup for follow-up."""
import logging

import httpx

from ingest.sources.webprocure import (
    HARD_CAP, PAGE_SIZE, SEARCH_URL, _USER_AGENT, _build_ssl_context, _search_terms,
)

log = logging.getLogger(__name__)

DETAIL_URL = "https://webprocure.proactiscloud.com/wp-full-text-search/soldetail/{bidid}"


class ResultsFetcher:
    def __init__(self, customer_id: str, client: httpx.Client | None = None):
        self.customer_id = customer_id
        self.client = client or httpx.Client(timeout=30, verify=_build_ssl_context())

    def fetch_awarded(self) -> list[dict]:
        """Awarded window records across the config search terms (deduped by bidid). Only
        records that actually carry bidAwardPublish are returned."""
        by_id: dict[int, dict] = {}
        errors = 0
        terms = _search_terms()
        for term in terms:
            try:
                recs = self._paginate(term)
            except Exception as e:  # noqa: BLE001 -- degrade, don't lose the source
                errors += 1
                log.warning("results(%s) term %r failed: %s", self.customer_id, term, e)
                continue
            for rec in recs:
                bidid = rec.get("bidid")
                if bidid is None or not rec.get("bidAwardPublish"):
                    continue
                by_id.setdefault(bidid, rec)
        if errors == len(terms):
            raise RuntimeError(f"results({self.customer_id}): all {errors} term queries failed")
        return list(by_id.values())

    def _paginate(self, term: str) -> list[dict]:
        out: list[dict] = []
        frm = 0
        while True:
            resp = self.client.get(SEARCH_URL, params={
                "customerid": self.customer_id, "q": term, "from": str(frm),
                "sort": "r", "f": "ps=Awarded", "oids": "",
            }, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            data = resp.json()
            out.extend(data.get("records", []))
            frm += PAGE_SIZE
            if frm >= data.get("hits", 0) or frm >= HARD_CAP:
                break
        return out

    def fetch_detail(self, bidid: int | str) -> dict | None:
        resp = self.client.get(DETAIL_URL.format(bidid=bidid),
                               params={"customerid": self.customer_id},
                               headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        records = resp.json().get("records", [])
        return records[0] if records else None
```

- [ ] **Step 4: Run → PASS.** Full suite green.
- [ ] **Step 5: Commit** `git add -A; git commit -m "feat(results): WebProcure awarded/detail fetcher"`

---

### Task 4: `results/collector.py` — orchestrate collection

**Files:**
- Create: `results/collector.py`
- Test: `tests/test_results_collector.py`

Maps a WebProcure record's `bidAwardPublish[]` (newest by `pubDate`) → parse → upsert `bid_results`. Runs backfill (awarded) + follow-up (our closed tenders), per-source isolated.

- [ ] **Step 1: Write the failing test `tests/test_results_collector.py`**

```python
from datetime import datetime, timezone

from ingest.base import RawTender
from results.collector import collect_from_records
from storage.models import BidResult
from storage.repo import BidResultRepo, TenderRepo


def _rec(bidid=115686, html='<ul><strong>Awarded Vendors:</strong><li>Napco, Inc</li></ul>'):
    return {"bidid": bidid, "title": "RIC Window Replacement",
            "bidAwardPublish": [{"title": "Final Award Report", "pubDate": 1750000000000,
                                 "customReport": html}]}


def test_collect_upserts_bid_results(session):
    n = collect_from_records(session, "ri_osp", [_rec()])
    assert n == 1  # one bid parsed+stored
    repo = BidResultRepo(session)
    assert repo.count() == 1
    r = repo.all_results()[0]
    assert r.source == "ri_osp" and r.external_id == "115686"
    assert r.bidder_name == "Napco, Inc" and r.is_winner is True and r.award_date is not None


def test_collect_marks_tracked_tender_results_collected(session):
    # a tracked closed tender with the same (source, external_id)
    t, _ = TenderRepo(session).upsert(RawTender(source="ri_osp", external_id="115686",
        title="RIC Window Replacement", owner="State of Rhode Island", state="RI",
        listing_url="https://example.org/x"))
    t.status = "closed"
    session.commit()
    collect_from_records(session, "ri_osp", [_rec()])
    session.refresh(t)
    assert t.status == "results_collected"


def test_collect_dedupes_on_rerun(session):
    collect_from_records(session, "ri_osp", [_rec()])
    collect_from_records(session, "ri_osp", [_rec()])
    assert BidResultRepo(session).count() == 1
```

- [ ] **Step 2: Run → FAIL** (ImportError).

- [ ] **Step 3: Implement `results/collector.py`**

```python
"""Turn WebProcure awarded records into bid_results rows, and advance tracked tenders to
status='results_collected'. Pure DB+parse orchestration; fetching is the fetcher's job."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from results.parse import parse_custom_report
from storage.models import Tender
from storage.repo import BidResultRepo

log = logging.getLogger(__name__)


def _award_date(pub_ms: int | None) -> datetime | None:
    if not pub_ms:
        return None
    return datetime.fromtimestamp(pub_ms / 1000, tz=timezone.utc)


def _newest_report(rec: dict) -> dict | None:
    pubs = rec.get("bidAwardPublish") or []
    if not pubs:
        return None
    return max(pubs, key=lambda p: p.get("pubDate") or 0)


def collect_from_records(session: Session, source: str, records: list[dict]) -> int:
    """Parse each record's newest award report → upsert bid_results. Returns bids stored.
    Marks any tracked tender with matching (source, external_id) as results_collected."""
    repo = BidResultRepo(session)
    stored = 0
    for rec in records:
        bidid = rec.get("bidid")
        report = _newest_report(rec)
        if bidid is None or report is None:
            continue
        try:
            bids = parse_custom_report(report.get("customReport") or "")
        except Exception:  # noqa: BLE001 -- one bad report never aborts the batch
            log.exception("results: failed to parse report for %s/%s", source, bidid)
            continue
        award_dt = _award_date(report.get("pubDate"))
        title = (rec.get("title") or "").strip() or "(untitled)"
        for b in bids:
            repo.upsert(dict(source=source, external_id=str(bidid), project_title=title,
                             bidder_name=b.bidder_name, amount=b.amount,
                             is_winner=b.is_winner, award_date=award_dt))
            stored += 1
        if bids:
            _mark_results_collected(session, source, str(bidid))
    session.commit()
    return stored


def _mark_results_collected(session: Session, source: str, external_id: str) -> None:
    t = session.scalar(select(Tender).where(Tender.source == source,
                                            Tender.external_id == external_id))
    if t is not None and t.status in ("closed", "notified", "new"):
        t.status = "results_collected"
```

- [ ] **Step 4: Run → PASS.** Full suite green.
- [ ] **Step 5: Commit** `git add -A; git commit -m "feat(results): collector (records -> bid_results, status advance)"`

---

### Task 5: `analytics/competitors.py` + `analytics/report.py`

**Files:**
- Create: `analytics/__init__.py` (empty), `analytics/competitors.py`, `analytics/report.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing test `tests/test_analytics.py`**

```python
from datetime import datetime, timezone

from analytics.competitors import competitor_stats, project_spreads
from analytics.report import build_weekly_report
from storage.repo import BidResultRepo


def _seed(session):
    repo = BidResultRepo(session)
    # project X: A wins @100k, B @150k  -> spread 50%
    repo.upsert(dict(source="ctsource", external_id="X", project_title="Job X",
                     bidder_name="A", amount=100000.0, is_winner=True,
                     award_date=datetime(2026, 7, 20, tzinfo=timezone.utc)))
    repo.upsert(dict(source="ctsource", external_id="X", project_title="Job X",
                     bidder_name="B", amount=150000.0, is_winner=False,
                     award_date=datetime(2026, 7, 20, tzinfo=timezone.utc)))
    # project Y: A loses, C wins (no amounts, RI-style)
    repo.upsert(dict(source="ri_osp", external_id="Y", project_title="Job Y",
                     bidder_name="A", amount=None, is_winner=False, award_date=None))
    repo.upsert(dict(source="ri_osp", external_id="Y", project_title="Job Y",
                     bidder_name="C", amount=None, is_winner=True, award_date=None))
    session.commit()


def test_competitor_stats(session):
    _seed(session)
    stats = {s["bidder"]: s for s in competitor_stats(session)}
    assert stats["A"]["bids"] == 2 and stats["A"]["wins"] == 1
    assert stats["C"]["wins"] == 1


def test_project_spreads(session):
    _seed(session)
    spreads = {s["external_id"]: s for s in project_spreads(session)}
    assert spreads["X"]["low"] == 100000.0 and spreads["X"]["high"] == 150000.0
    assert abs(spreads["X"]["spread_pct"] - 50.0) < 0.1
    assert "Y" not in spreads  # no amounts -> no spread


def test_weekly_report_text(session):
    _seed(session)
    cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
    text = build_weekly_report(session, cutoff)
    assert "Job X" in text and "A" in text
```

- [ ] **Step 2: Run → FAIL** (ImportError).

- [ ] **Step 3: Implement `analytics/competitors.py`**

```python
"""Aggregates over bid_results — competitors (bids/wins/win-rate) and per-project spreads.
Computed on the fly; no materialized table (design spec)."""
from collections import defaultdict

from sqlalchemy.orm import Session

from storage.repo import BidResultRepo


def competitor_stats(session: Session) -> list[dict]:
    agg: dict[str, dict] = defaultdict(lambda: {"bids": 0, "wins": 0})
    for r in BidResultRepo(session).all_results():
        a = agg[r.bidder_name]
        a["bids"] += 1
        if r.is_winner:
            a["wins"] += 1
    out = []
    for bidder, a in agg.items():
        win_rate = (a["wins"] / a["bids"]) if a["bids"] else 0.0
        out.append({"bidder": bidder, "bids": a["bids"], "wins": a["wins"], "win_rate": win_rate})
    return sorted(out, key=lambda x: (-x["wins"], -x["bids"]))


def project_spreads(session: Session) -> list[dict]:
    """Per project (source, external_id) low/high/spread% — only projects with >=2 priced bids."""
    by_proj: dict[tuple, dict] = {}
    amounts: dict[tuple, list[float]] = defaultdict(list)
    for r in BidResultRepo(session).all_results():
        key = (r.source, r.external_id)
        by_proj.setdefault(key, {"source": r.source, "external_id": r.external_id,
                                 "project_title": r.project_title})
        if r.amount is not None:
            amounts[key].append(r.amount)
    out = []
    for key, vals in amounts.items():
        if len(vals) < 2:
            continue
        low, high = min(vals), max(vals)
        spread_pct = ((high - low) / low * 100.0) if low else 0.0
        out.append({**by_proj[key], "low": low, "high": high, "n_bidders": len(vals),
                    "spread_pct": spread_pct})
    return sorted(out, key=lambda x: -x["spread_pct"])
```

- [ ] **Step 4: Implement `analytics/report.py`**

```python
"""Weekly competitor/spread report (markdown) from bid_results collected since a cutoff."""
from datetime import datetime

from sqlalchemy.orm import Session

from analytics.competitors import competitor_stats, project_spreads
from storage.repo import BidResultRepo


def build_weekly_report(session: Session, since: datetime) -> str:
    fresh = BidResultRepo(session).collected_since(since)
    lines = ["Tender-Radar — тижневий звіт результатів"]
    if not fresh:
        lines.append("\nНових результатів за тиждень немає.")
    else:
        projects: dict[tuple, dict] = {}
        for r in fresh:
            key = (r.source, r.external_id)
            p = projects.setdefault(key, {"title": r.project_title, "source": r.source,
                                          "winner": None, "n": 0})
            p["n"] += 1
            if r.is_winner:
                p["winner"] = r.bidder_name
        lines.append(f"\nНові результати ({len(projects)} проєктів):")
        for p in projects.values():
            win = p["winner"] or "?"
            lines.append(f"• {p['title']} [{p['source']}] — переможець: {win}, учасників: {p['n']}")

    spreads = project_spreads(session)[:5]
    if spreads:
        lines.append("\nНайбільші цінові спреди (low→high):")
        for s in spreads:
            lines.append(f"• {s['project_title']}: ${s['low']:,.0f} → ${s['high']:,.0f} "
                         f"(+{s['spread_pct']:.0f}%, {s['n_bidders']} бідерів)")

    top = competitor_stats(session)[:5]
    if top:
        lines.append("\nТоп-конкуренти (перемоги/біди):")
        for c in top:
            lines.append(f"• {c['bidder']}: {c['wins']}W / {c['bids']}B ({c['win_rate']*100:.0f}%)")
    return "\n".join(lines)
```

- [ ] **Step 5: Run → PASS.** Full suite green.
- [ ] **Step 6: Commit** `git add -A; git commit -m "feat(analytics): competitor stats, spreads, weekly report"`

---

### Task 6: Wire into `run_once` / `main` — daily collection + weekly report

**Files:**
- Modify: `main.py`
- Modify: `config.py` (add `WEEKLY_REPORT_WEEKDAY`)
- Test: `tests/test_results_wiring.py`

- [ ] **Step 1: Add config** to `config.py`:

```python
WEEKLY_REPORT_WEEKDAY = int(os.getenv("TR_WEEKLY_REPORT_WEEKDAY", "0"))  # 0=Monday
RESULTS_SOURCES = {"ctsource": "51", "ri_osp": "46"}  # source name -> WebProcure customerid
```

- [ ] **Step 2: Write the failing test `tests/test_results_wiring.py`**

```python
import main


def test_run_results_and_maybe_report_is_callable():
    assert hasattr(main, "run_results_and_maybe_report")
```

(Keep it minimal — the heavy logic is already unit-tested in Tasks 3–5; this just asserts wiring exists. A deeper integration test would need to mock the network fetcher, which the collector tests already cover.)

- [ ] **Step 3: Add the wiring to `main.py`.** Add imports:

```python
from datetime import datetime, timezone, timedelta
from analytics.report import build_weekly_report
from results.collector import collect_from_records
from results.webprocure_results import ResultsFetcher
from storage.models import Tender
from sqlalchemy import select
```

Add the function and call it from `job_ingest_and_digest` after the digest:

```python
def run_results_and_maybe_report(session, now):
    """Daily: collect awarded results (backfill + follow-up) per WebProcure source, isolated.
    Weekly (on WEEKLY_REPORT_WEEKDAY): send the competitor/spread report to Telegram."""
    for source, cid in config.RESULTS_SOURCES.items():
        try:
            fetcher = ResultsFetcher(customer_id=cid)
            records = fetcher.fetch_awarded()
            # follow-up: our closed tenders for this source not yet resolved
            closed = session.scalars(select(Tender).where(
                Tender.source == source, Tender.status == "closed")).all()
            for t in closed:
                rec = fetcher.fetch_detail(t.external_id)
                if rec:
                    records.append(rec)
            n = collect_from_records(session, source, records)
            log.info("results %s: %d bids stored", source, n)
        except Exception:  # noqa: BLE001 -- per-source isolation
            log.exception("results source %s failed", source)
    if now.weekday() == config.WEEKLY_REPORT_WEEKDAY:
        since = now - timedelta(days=7)
        text = build_weekly_report(session, since)
        TELEGRAM.send(text)
        log.info("weekly results report sent")


# in job_ingest_and_digest, after `send_daily_digest(session, TELEGRAM, now)`:
        run_results_and_maybe_report(session, now)
```

- [ ] **Step 4: Run → PASS.** Full suite green (`.venv\Scripts\pytest -v`).

- [ ] **Step 5: Local sqlite smoke of the wiring shape** (no live network — collector/fetcher are unit-tested; here just confirm import + run_once composes). Confirm `.venv\Scripts\python -c "import run_once, main; print('ok', hasattr(main,'run_results_and_maybe_report'))"` prints `ok True`.

- [ ] **Step 6: Commit** `git add -A; git commit -m "feat: wire daily results collection + weekly report into run_once"`

---

## Out of scope (this plan)
- NYC/DCAMM/COMMBUYS results (deferred / not accessible).
- $/window normalization (needs takeoff).
- Materialized competitors/price_points tables.
- A separate weekly cron (the in-run weekday check reuses the daily entrypoint).

## Post-plan (controller handles, like Plan 2)
- Push; trigger a cloud run; confirm `bid_results` populates in Supabase (CT priced rows with amounts, RI vendor rows) and no source errored. A backfill on first cloud run will populate history.

## Self-review notes
- Spec coverage: bid_results storage (T1), parse both flavors (T2), fetch awarded+detail (T3), collector+status advance (T4), competitor/spread analytics + weekly report (T5), daily-collection + weekly-report wiring (T6). All spec sections mapped.
- Reuses WebProcure SSL/client/`_search_terms` (T3) — no duplication, no new deps.
- Types consistent: `ParsedBid` (T2) consumed by collector (T4); `BidResultRepo.upsert(dict)` (T1) used by collector (T4); `collect_from_records(session, source, records)` (T4) used by wiring (T6); analytics read via `BidResultRepo.all_results`/`collected_since` (T1).
- No placeholders; parser (T2) is fixture-driven (implementer reads the two committed fixtures, matching the Plan 2 adapter precedent) since exact HTML shapes live in the fixtures.
