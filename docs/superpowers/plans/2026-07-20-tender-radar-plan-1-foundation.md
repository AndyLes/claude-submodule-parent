# Tender-Radar Plan 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working Tender-Radar core: PostgreSQL storage, config-driven relevance filter, one real source adapter (NYC Socrata), daily Telegram digest, APScheduler wiring — runnable on the local Windows machine.

**Architecture:** Modular monolith (spec: `docs/superpowers/specs/2026-07-20-tender-radar-design.md`). Modules `ingest / notify / storage` in this plan; `results / analytics` come in Plans 3–4; the other six adapters come in Plan 2 after HTML recon. Modules talk only через storage repositories.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, PostgreSQL 16 (Docker), APScheduler, httpx, pytest (SQLite in-memory for tests — models stay type-portable).

**Repo:** new separate git repo at `C:\SuperWork\projects\tender-radar\` (per SuperWork convention: has `docs/`). All paths below relative to it.

---

### Task 1: Repo scaffold

**Files:**
- Create: `.gitignore`, `requirements.txt`, `docker-compose.yml`, `config.py`, `config/relevance.json`, `docs/ARCHITECTURE.md`, `docs/DATA-MODEL.md`, `docs/DECISIONS.md`, `README.md`

- [ ] **Step 1: Init repo and dirs**

```powershell
mkdir C:\SuperWork\projects\tender-radar; cd C:\SuperWork\projects\tender-radar
git init
mkdir ingest, notify, storage, tests, config, docs, reports
```

- [ ] **Step 2: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
reports/*.csv
reports/*.md
```

- [ ] **Step 3: Write `requirements.txt`**

```
sqlalchemy>=2.0
psycopg[binary]>=3.1
apscheduler>=3.10,<4
httpx>=0.27
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 4: Write `docker-compose.yml`** (port 5433 to avoid collisions with other local PGs)

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: tender
      POSTGRES_PASSWORD: tender
      POSTGRES_DB: tender_radar
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

- [ ] **Step 5: Write `config.py`**

```python
"""Central config. Env vars override defaults; domain params live in config/*.json (editable, not code)."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DATABASE_URL = os.getenv(
    "TR_DATABASE_URL",
    "postgresql+psycopg://tender:tender@localhost:5433/tender_radar",
)
TELEGRAM_BOT_TOKEN = os.getenv("TR_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TR_TELEGRAM_CHAT_ID", "")
INGEST_HOUR = int(os.getenv("TR_INGEST_HOUR", "14"))  # local time, daily

NYC_SOCRATA_DATASET = os.getenv("TR_NYC_SOCRATA_DATASET", "dg92-zbpx")  # City Record Online
NYC_SOCRATA_APP_TOKEN = os.getenv("TR_NYC_SOCRATA_APP_TOKEN", "")  # optional, raises rate limits


def load_relevance() -> dict:
    return json.loads((BASE_DIR / "config" / "relevance.json").read_text(encoding="utf-8"))
```

- [ ] **Step 6: Write `config/relevance.json`** (domain params editable per user preference — never hardcode)

```json
{
  "keywords": ["window", "windows", "glazing", "curtain wall", "curtainwall", "storefront", "fenestration", "glass and glazing", "metal windows"],
  "exclude_keywords": ["window cleaning", "window washing", "windows server", "microsoft windows", "window tint"]
}
```

- [ ] **Step 7: Write docs stubs.** `docs/ARCHITECTURE.md`:

```markdown
# Tender-Radar Architecture

Modular monolith. Modules communicate only via `storage` repositories.

- `ingest/` — source adapters (`BaseSource.fetch() -> list[RawTender]`), relevance filter, dedup.
- `notify/` — Telegram digests, dedup via `digest_log`.
- `storage/` — SQLAlchemy models + repositories. The only inter-module seam.
- `results/`, `analytics/` — Plans 3–4.
- `main.py` — APScheduler wiring.

Design spec: SuperWork `docs/superpowers/specs/2026-07-20-tender-radar-design.md`.
```

`docs/DATA-MODEL.md`:

```markdown
# Data Model

- `tenders` — unique (source, external_id); status: new → notified → closed → results_collected.
- `source_health` — per-source last_success/last_error/consecutive_failures.
- `digest_log` — (tender_id, kind) rows; a tender appears in a daily digest once.
- `bid_results`, `price_points`, `competitors` — Plans 3–4.
```

`docs/DECISIONS.md`:

```markdown
# Decisions

- 2026-07-20: Modular monolith, not microservices (no load/team driver; module seams allow later extraction).
- 2026-07-20: Tests on SQLite in-memory → models use portable types only (no JSONB/ARRAY).
- 2026-07-20: PG on port 5433 (collision avoidance). Relevance params in config/relevance.json, not code.
- 2026-07-20: v1 sources are free/open only. NYC first (true API); 6 scraped portals follow in Plan 2 after HTML recon.
```

`README.md`:

```markdown
# Tender-Radar

Window/glazing tender monitoring (MA/NY/CT/RI/NH) + bid-results price intelligence.

Setup: `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`, `docker compose up -d db`, copy `.env.example` → `.env`, run `python main.py`.
```

- [ ] **Step 8: Write `.env.example`**

```
TR_DATABASE_URL=postgresql+psycopg://tender:tender@localhost:5433/tender_radar
TR_TELEGRAM_BOT_TOKEN=
TR_TELEGRAM_CHAT_ID=
TR_INGEST_HOUR=14
TR_NYC_SOCRATA_APP_TOKEN=
```

- [ ] **Step 9: Commit**

```powershell
git add -A; git commit -m "chore: scaffold tender-radar (config, compose, docs)"
```

---

### Task 2: Storage — models

**Files:**
- Create: `storage/__init__.py`, `storage/models.py`, `storage/db.py`
- Test: `tests/test_models.py`, `tests/conftest.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from storage.models import Base


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
```

- [ ] **Step 2: Write the failing test `tests/test_models.py`**

```python
from datetime import datetime, timezone

from storage.models import Tender


def test_tender_unique_per_source(session):
    t1 = Tender(source="nyc_socrata", external_id="X1", title="Window replacement PS 12",
                state="NY", listing_url="https://example.org/x1",
                first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc))
    session.add(t1)
    session.commit()
    assert t1.id is not None
    assert t1.status == "new"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'storage'` (or ImportError)

- [ ] **Step 4: Write `storage/__init__.py`** (empty file), then `storage/models.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(Text, default=None)
    state: Mapped[str] = mapped_column(String(2))
    trade_classes: Mapped[str | None] = mapped_column(Text, default=None)  # comma-joined
    est_value: Mapped[float | None] = mapped_column(Float, default=None)
    bid_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    listing_url: Mapped[str] = mapped_column(Text)
    plans_url: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceHealth(Base):
    __tablename__ = "source_health"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    consecutive_failures: Mapped[int] = mapped_column(default=0)


class DigestLog(Base):
    __tablename__ = "digest_log"
    __table_args__ = (UniqueConstraint("tender_id", "kind", name="uq_digest_tender_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(16))  # "daily"
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 5: Write `storage/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from storage.models import Base


def make_engine(url: str | None = None):
    return create_engine(url or config.DATABASE_URL, pool_pre_ping=True)


def make_session_factory(engine):
    Base.metadata.create_all(engine)  # v1: create_all instead of migrations (see DECISIONS)
    return sessionmaker(bind=engine)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 7: Append to `docs/DECISIONS.md`**: `- 2026-07-20: v1 schema via create_all, no Alembic until schema churn hurts.`

- [ ] **Step 8: Commit**

```powershell
git add -A; git commit -m "feat(storage): models Tender/SourceHealth/DigestLog + engine factory"
```

---

### Task 3: Storage — repositories (upsert/dedup, digest queries, health)

**Files:**
- Create: `storage/repo.py`
- Test: `tests/test_repo.py`

- [ ] **Step 1: Write the failing test `tests/test_repo.py`**

```python
from datetime import datetime, timezone

from storage.repo import DigestRepo, HealthRepo, TenderRepo
from ingest.base import RawTender


def raw(eid="A1", title="School window replacement"):
    return RawTender(source="nyc_socrata", external_id=eid, title=title,
                     owner="NYC SCA", state="NY", trade_classes=[],
                     est_value=None, bid_deadline=None,
                     listing_url=f"https://example.org/{eid}", plans_url=None)


def test_upsert_inserts_then_updates_last_seen(session):
    repo = TenderRepo(session)
    t1 = repo.upsert(raw())
    first = t1.last_seen
    t2 = repo.upsert(raw())
    assert t2.id == t1.id
    assert t2.last_seen >= first
    assert session.query(type(t1)).count() == 1


def test_undigested_and_mark(session):
    repo = TenderRepo(session)
    d = DigestRepo(session)
    t = repo.upsert(raw())
    session.commit()
    fresh = d.undigested_tenders(kind="daily")
    assert [x.id for x in fresh] == [t.id]
    d.mark_sent([t.id], kind="daily")
    session.commit()
    assert d.undigested_tenders(kind="daily") == []


def test_health_success_resets_failures(session):
    h = HealthRepo(session)
    h.record_failure("nyc_socrata", "boom")
    h.record_failure("nyc_socrata", "boom2")
    assert h.get("nyc_socrata").consecutive_failures == 2
    h.record_success("nyc_socrata")
    assert h.get("nyc_socrata").consecutive_failures == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_repo.py -v`
Expected: FAIL with ImportError (`storage.repo`, `ingest.base` don't exist)

- [ ] **Step 3: Write `ingest/__init__.py`** (empty) **and `ingest/base.py`** (RawTender + BaseSource contract — needed by repo test)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RawTender:
    source: str
    external_id: str
    title: str
    owner: str | None
    state: str
    trade_classes: list[str] = field(default_factory=list)
    est_value: float | None = None
    bid_deadline: datetime | None = None
    listing_url: str = ""
    plans_url: str | None = None


class BaseSource(Protocol):
    name: str

    def fetch(self) -> list[RawTender]:
        """Return current candidate tenders. Raise on failure — the runner isolates it."""
        ...
```

- [ ] **Step 4: Write `storage/repo.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingest.base import RawTender
from storage.models import DigestLog, SourceHealth, Tender


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TenderRepo:
    def __init__(self, session: Session):
        self.s = session

    def upsert(self, r: RawTender) -> Tender:
        existing = self.s.scalar(
            select(Tender).where(Tender.source == r.source, Tender.external_id == r.external_id)
        )
        if existing:
            existing.last_seen = _now()
            existing.title = r.title or existing.title
            existing.bid_deadline = r.bid_deadline or existing.bid_deadline
            existing.est_value = r.est_value if r.est_value is not None else existing.est_value
            return existing
        t = Tender(
            source=r.source, external_id=r.external_id, title=r.title, owner=r.owner,
            state=r.state, trade_classes=",".join(r.trade_classes) or None,
            est_value=r.est_value, bid_deadline=r.bid_deadline,
            listing_url=r.listing_url, plans_url=r.plans_url,
            first_seen=_now(), last_seen=_now(),
        )
        self.s.add(t)
        self.s.flush()
        return t


class DigestRepo:
    def __init__(self, session: Session):
        self.s = session

    def undigested_tenders(self, kind: str) -> list[Tender]:
        sent = select(DigestLog.tender_id).where(DigestLog.kind == kind)
        return list(self.s.scalars(select(Tender).where(Tender.id.not_in(sent)).order_by(Tender.id)))

    def mark_sent(self, tender_ids: list[int], kind: str) -> None:
        for tid in tender_ids:
            self.s.add(DigestLog(tender_id=tid, kind=kind, sent_at=_now()))
        self.s.flush()


class HealthRepo:
    def __init__(self, session: Session):
        self.s = session

    def get(self, source: str) -> SourceHealth:
        h = self.s.get(SourceHealth, source)
        if h is None:
            h = SourceHealth(source=source)
            self.s.add(h)
            self.s.flush()
        return h

    def record_success(self, source: str) -> None:
        h = self.get(source)
        h.last_success = _now()
        h.consecutive_failures = 0

    def record_failure(self, source: str, error: str) -> None:
        h = self.get(source)
        h.last_error = error[:2000]
        h.last_error_at = _now()
        h.consecutive_failures += 1

    def silent_sources(self, min_failures: int = 3) -> list[SourceHealth]:
        return list(self.s.scalars(
            select(SourceHealth).where(SourceHealth.consecutive_failures >= min_failures)
        ))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_repo.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```powershell
git add -A; git commit -m "feat(storage): repositories (upsert dedup, digest queries, source health)"
```

---

### Task 4: Ingest — relevance filter + runner with per-source isolation

**Files:**
- Create: `ingest/filter.py`, `ingest/runner.py`
- Test: `tests/test_filter.py`, `tests/test_runner.py`

- [ ] **Step 1: Write the failing test `tests/test_filter.py`**

```python
from ingest.filter import RelevanceFilter

CFG = {
    "keywords": ["window", "glazing", "curtain wall"],
    "exclude_keywords": ["window cleaning", "microsoft windows"],
}


def test_matches_keyword_in_title():
    f = RelevanceFilter(CFG)
    assert f.is_relevant(title="PS 118 Window Replacement", trade_classes=[])


def test_exclude_beats_include():
    f = RelevanceFilter(CFG)
    assert not f.is_relevant(title="Window cleaning services citywide", trade_classes=[])


def test_trade_class_match_without_title_keyword():
    f = RelevanceFilter(CFG)
    assert f.is_relevant(title="Roxbury school modernization", trade_classes=["Metal Windows"])


def test_irrelevant():
    f = RelevanceFilter(CFG)
    assert not f.is_relevant(title="HVAC upgrade phase 2", trade_classes=["Plumbing"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_filter.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write `ingest/filter.py`**

```python
class RelevanceFilter:
    """Metadata-level relevance. Keyword/class params come from config/relevance.json — editable, not code."""

    def __init__(self, cfg: dict):
        self.keywords = [k.lower() for k in cfg["keywords"]]
        self.exclude = [k.lower() for k in cfg.get("exclude_keywords", [])]

    def is_relevant(self, title: str, trade_classes: list[str]) -> bool:
        text = " ".join([title, *trade_classes]).lower()
        if any(x in text for x in self.exclude):
            return False
        return any(k in text for k in self.keywords)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_filter.py -v`
Expected: 4 PASS

- [ ] **Step 5: Write the failing test `tests/test_runner.py`**

```python
from ingest.base import RawTender
from ingest.runner import run_ingest


class GoodSource:
    name = "good"

    def fetch(self):
        return [RawTender(source="good", external_id="G1", title="Window replacement",
                          owner=None, state="MA", listing_url="https://example.org/g1"),
                RawTender(source="good", external_id="G2", title="HVAC only",
                          owner=None, state="MA", listing_url="https://example.org/g2")]


class BadSource:
    name = "bad"

    def fetch(self):
        raise RuntimeError("portal down")


CFG = {"keywords": ["window"], "exclude_keywords": []}


def test_runner_isolates_failures_and_filters(session):
    stats = run_ingest(session, [GoodSource(), BadSource()], CFG)
    assert stats == {"good": {"fetched": 2, "relevant": 1, "new": 1}, "bad": {"error": "portal down"}}
    # second run: same tender is an update, not new
    stats2 = run_ingest(session, [GoodSource()], CFG)
    assert stats2["good"]["new"] == 0
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_runner.py -v`
Expected: FAIL with ImportError (`ingest.runner`)

- [ ] **Step 7: Write `ingest/runner.py`**

```python
import logging

from sqlalchemy.orm import Session

from ingest.base import BaseSource
from ingest.filter import RelevanceFilter
from storage.repo import HealthRepo, TenderRepo

log = logging.getLogger(__name__)


def run_ingest(session: Session, sources: list[BaseSource], relevance_cfg: dict) -> dict:
    """One ingest pass. A failing source never aborts the run (per-source isolation)."""
    f = RelevanceFilter(relevance_cfg)
    tenders = TenderRepo(session)
    health = HealthRepo(session)
    stats: dict = {}
    for src in sources:
        try:
            raws = src.fetch()
            relevant = [r for r in raws if f.is_relevant(r.title, r.trade_classes)]
            new = 0
            for r in relevant:
                before = tenders.upsert(r)
                if before.first_seen == before.last_seen:
                    new += 1
            health.record_success(src.name)
            stats[src.name] = {"fetched": len(raws), "relevant": len(relevant), "new": new}
        except Exception as e:  # noqa: BLE001 — isolation boundary by design
            log.exception("source %s failed", src.name)
            health.record_failure(src.name, str(e))
            stats[src.name] = {"error": str(e)}
        session.commit()
    return stats
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_runner.py tests/test_filter.py -v`
Expected: all PASS. (If the `new` count is off because `first_seen == last_seen` comparison is flaky on fast machines, change `upsert` to return a `(tender, created)` tuple instead — adjust test accordingly. Prefer the tuple if any doubt.)

- [ ] **Step 9: Commit**

```powershell
git add -A; git commit -m "feat(ingest): relevance filter + isolated multi-source runner"
```

---

### Task 5: NYC Socrata adapter (first real source)

**Files:**
- Create: `ingest/sources/__init__.py`, `ingest/sources/nyc_socrata.py`
- Test: `tests/test_nyc_socrata.py`, `tests/fixtures/nyc_socrata_sample.json`

- [ ] **Step 1: Verify dataset id against the live API** (one manual command; the id `dg92-zbpx` = City Record Online, per research report 01 — re-verify before coding)

```powershell
curl.exe -s "https://data.cityofnewyork.us/resource/dg92-zbpx.json?`$limit=1"
```

Expected: JSON array with one record containing fields like `request_id`, `short_title`, `agency_name`, `section_name`, `due_date`. If 404 → find the current City Record Online dataset id at https://data.cityofnewyork.us (search "City Record Online"), update `TR_NYC_SOCRATA_DATASET` default in `config.py`, and use the real field names you see in the response everywhere below.

- [ ] **Step 2: Save a real sample as fixture** (redact nothing — it's public data). Take ~5 records matching windows:

```powershell
curl.exe -s "https://data.cityofnewyork.us/resource/dg92-zbpx.json?`$q=window&`$limit=5" | Out-File -Encoding utf8 tests\fixtures\nyc_socrata_sample.json
```

If the live field names differ from the fixture assumptions below, adjust adapter + test together — the fixture is the source of truth.

- [ ] **Step 3: Write the failing test `tests/test_nyc_socrata.py`**

```python
import json
from pathlib import Path

import httpx

from ingest.sources.nyc_socrata import NycSocrataSource

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "nyc_socrata_sample.json").read_text(encoding="utf-8"))


def make_source():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "$q" in dict(request.url.params) or "%24q" in str(request.url)
        return httpx.Response(200, json=FIXTURE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return NycSocrataSource(client=client, dataset="dg92-zbpx")


def test_fetch_maps_fields():
    src = make_source()
    raws = src.fetch()
    assert len(raws) == len(FIXTURE)
    r = raws[0]
    assert r.source == "nyc_socrata"
    assert r.state == "NY"
    assert r.external_id  # request_id present
    assert r.title
    assert r.listing_url.startswith("https://a856-cityrecord.nyc.gov")
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_nyc_socrata.py -v`
Expected: FAIL with ImportError

- [ ] **Step 5: Write `ingest/sources/__init__.py`** (empty) **and `ingest/sources/nyc_socrata.py`**

```python
"""NYC City Record Online via Socrata SODA API — solicitations full-text matching window terms.

Field names verified against tests/fixtures/nyc_socrata_sample.json (live sample).
"""
from datetime import datetime

import httpx

import config
from ingest.base import RawTender

CITY_RECORD_URL = "https://a856-cityrecord.nyc.gov/RequestDetail/{rid}"


class NycSocrataSource:
    name = "nyc_socrata"

    def __init__(self, client: httpx.Client | None = None, dataset: str | None = None):
        self.client = client or httpx.Client(timeout=30)
        self.dataset = dataset or config.NYC_SOCRATA_DATASET

    def fetch(self) -> list[RawTender]:
        params = {"$q": "window glazing curtain wall", "$limit": "200", "$order": ":id DESC"}
        headers = {}
        if config.NYC_SOCRATA_APP_TOKEN:
            headers["X-App-Token"] = config.NYC_SOCRATA_APP_TOKEN
        resp = self.client.get(
            f"https://data.cityofnewyork.us/resource/{self.dataset}.json",
            params=params, headers=headers,
        )
        resp.raise_for_status()
        out = []
        for rec in resp.json():
            rid = rec.get("request_id") or rec.get("requestid")
            if not rid:
                continue
            out.append(RawTender(
                source=self.name,
                external_id=str(rid),
                title=rec.get("short_title", "").strip() or "(untitled)",
                owner=rec.get("agency_name"),
                state="NY",
                trade_classes=[],
                est_value=None,
                bid_deadline=_parse_dt(rec.get("due_date")),
                listing_url=CITY_RECORD_URL.format(rid=rid),
                plans_url=None,
            ))
        return out


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None
```

- [ ] **Step 6: Run test to verify it passes** (adjust field names to the real fixture if needed — fixture wins)

Run: `.venv\Scripts\pytest tests/test_nyc_socrata.py -v`
Expected: PASS

- [ ] **Step 7: One live smoke run** (network, not part of test suite)

```powershell
.venv\Scripts\python -c "from ingest.sources.nyc_socrata import NycSocrataSource; rs = NycSocrataSource().fetch(); print(len(rs), rs[0] if rs else 'EMPTY')"
```

Expected: a count > 0 and a plausible RawTender printed. If EMPTY, loosen `$q` to just `window` and re-check.

- [ ] **Step 8: Commit**

```powershell
git add -A; git commit -m "feat(ingest): NYC Socrata (City Record) adapter with live-sample fixture"
```

---

### Task 6: Notify — Telegram daily digest

**Files:**
- Create: `notify/__init__.py`, `notify/digest.py`, `notify/telegram.py`
- Test: `tests/test_digest.py`

- [ ] **Step 1: Write the failing test `tests/test_digest.py`**

```python
import httpx

from ingest.base import RawTender
from notify.digest import build_daily_text, send_daily_digest
from notify.telegram import TelegramClient
from storage.repo import DigestRepo, HealthRepo, TenderRepo


def _seed(session, n=2):
    repo = TenderRepo(session)
    for i in range(n):
        repo.upsert(RawTender(source="good", external_id=f"S{i}", title=f"Window project {i}",
                              owner="Town of Lexington", state="MA",
                              listing_url=f"https://example.org/s{i}"))
    session.commit()


def test_build_daily_text_groups_by_state(session):
    _seed(session)
    HealthRepo(session).record_failure("nh_das", "403")
    HealthRepo(session).record_failure("nh_das", "403")
    HealthRepo(session).record_failure("nh_das", "403")
    text = build_daily_text(session)
    assert "MA" in text and "Window project 0" in text
    assert "nh_das" in text  # 3+ failures → alert line


def test_send_marks_digested_and_skips_when_empty(session):
    _seed(session)
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    tg = TelegramClient(token="t", chat_id="c",
                        client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert send_daily_digest(session, tg) == 2
    assert len(sent) == 1
    # all digested now → second call sends nothing
    assert send_daily_digest(session, tg) == 0
    assert len(sent) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_digest.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write `notify/__init__.py`** (empty), **`notify/telegram.py`**

```python
import logging

import httpx

log = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, token: str, chat_id: str, client: httpx.Client | None = None):
        self.token = token
        self.chat_id = chat_id
        self.client = client or httpx.Client(timeout=30)

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> None:
        if not self.enabled:
            log.info("telegram disabled (no token/chat id); message skipped")
            return
        resp = self.client.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
        )
        resp.raise_for_status()
```

**and `notify/digest.py`**

```python
from itertools import groupby

from sqlalchemy.orm import Session

from notify.telegram import TelegramClient
from storage.repo import DigestRepo, HealthRepo


def build_daily_text(session: Session) -> str:
    fresh = DigestRepo(session).undigested_tenders(kind="daily")
    lines = ["Tender-Radar — нові тендери" if fresh else "Tender-Radar: нових тендерів немає"]
    for state, group in groupby(sorted(fresh, key=lambda t: t.state), key=lambda t: t.state):
        lines.append(f"\n[{state}]")
        for t in group:
            deadline = t.bid_deadline.strftime("%m/%d") if t.bid_deadline else "—"
            owner = t.owner or "?"
            lines.append(f"• {t.title} | {owner} | до {deadline}\n  {t.listing_url}")
    silent = HealthRepo(session).silent_sources(min_failures=3)
    if silent:
        lines.append("\n⚠ Джерела мовчать: " + ", ".join(h.source for h in silent))
    return "\n".join(lines)


def send_daily_digest(session: Session, tg: TelegramClient) -> int:
    """Returns number of tenders included. Sends nothing when there are no fresh tenders."""
    d = DigestRepo(session)
    fresh = d.undigested_tenders(kind="daily")
    if not fresh:
        return 0
    tg.send(build_daily_text(session))
    d.mark_sent([t.id for t in fresh], kind="daily")
    session.commit()
    return len(fresh)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_digest.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```powershell
git add -A; git commit -m "feat(notify): telegram client + daily digest with source-silence alerts"
```

---

### Task 7: main.py — scheduler wiring + e2e fixture test

**Files:**
- Create: `main.py`
- Test: `tests/test_e2e.py`

- [ ] **Step 1: Write the failing test `tests/test_e2e.py`** (full pipeline over fakes — no network)

```python
import httpx

from ingest.base import RawTender
from ingest.runner import run_ingest
from notify.digest import send_daily_digest
from notify.telegram import TelegramClient


class FakePortal:
    name = "fake"

    def fetch(self):
        return [RawTender(source="fake", external_id="F1", title="Curtain wall replacement, City Hall",
                          owner="City of Hartford", state="CT",
                          listing_url="https://example.org/f1")]


def test_ingest_then_digest_end_to_end(session):
    msgs = []

    def handler(request: httpx.Request) -> httpx.Response:
        msgs.append(request.read().decode())
        return httpx.Response(200, json={"ok": True})

    stats = run_ingest(session, [FakePortal()], {"keywords": ["curtain wall"], "exclude_keywords": []})
    assert stats["fake"]["new"] == 1
    tg = TelegramClient("t", "c", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert send_daily_digest(session, tg) == 1
    assert "Curtain wall replacement" in msgs[0]
```

- [ ] **Step 2: Run test to verify it fails / passes**

Run: `.venv\Scripts\pytest tests/test_e2e.py -v`
Expected: PASS immediately (it composes already-built parts). If it fails, fix the seam it exposes before continuing — do not skip.

- [ ] **Step 3: Write `main.py`**

```python
"""Tender-Radar entrypoint: daily ingest + digest on APScheduler. Ctrl+C to stop."""
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from ingest.runner import run_ingest
from ingest.sources.nyc_socrata import NycSocrataSource
from notify.digest import send_daily_digest
from notify.telegram import TelegramClient
from storage.db import make_engine, make_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("main")

SOURCES = [NycSocrataSource()]  # Plan 2 appends the six scraped portals here


def job_ingest_and_digest(session_factory):
    with session_factory() as session:
        stats = run_ingest(session, SOURCES, config.load_relevance())
        log.info("ingest stats: %s", stats)
        sent = send_daily_digest(session, TelegramClient(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID))
        log.info("digest sent for %d tenders", sent)


def main() -> int:
    engine = make_engine()
    try:
        engine.connect().close()  # env guard: fail fast with a clear message
    except Exception as e:  # noqa: BLE001
        log.error("DB unreachable at %s — is `docker compose up -d db` running? (%s)", config.DATABASE_URL, e)
        return 1
    session_factory = make_session_factory(engine)
    sched = BlockingScheduler()
    sched.add_job(job_ingest_and_digest, "cron", hour=config.INGEST_HOUR, minute=0,
                  args=[session_factory], max_instances=1, coalesce=True, misfire_grace_time=3600)
    log.info("scheduled daily ingest at %02d:00 local; running startup pass now", config.INGEST_HOUR)
    job_ingest_and_digest(session_factory)  # immediate pass on start
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("shutting down")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Live smoke run** (needs `docker compose up -d db` first; Telegram env unset → digest logs "disabled", that's fine)

```powershell
docker compose up -d db
.venv\Scripts\python main.py
```

Expected: "ingest stats: {'nyc_socrata': {...}}" with fetched > 0, then scheduler waiting. Ctrl+C stops cleanly.

- [ ] **Step 5: Run full test suite**

Run: `.venv\Scripts\pytest -v`
Expected: all tests PASS

- [ ] **Step 6: Update `docs/ARCHITECTURE.md`** — append: `main.py runs an immediate pass at startup, then daily at TR_INGEST_HOUR. Windows autostart: schtasks below.` And add to `README.md`:

```markdown
## Autostart (Windows)

schtasks /Create /TN "TenderRadar" /TR "C:\SuperWork\projects\tender-radar\.venv\Scripts\python.exe C:\SuperWork\projects\tender-radar\main.py" /SC ONLOGON /RL LIMITED
```

- [ ] **Step 7: Commit**

```powershell
git add -A; git commit -m "feat: main scheduler wiring, e2e test, autostart docs"
```

---

## Out of scope for Plan 1 (explicitly)

- Plan 2: adapters `ma_dcamm`, `ma_commbuys`, `nyscr`, `ctsource`, `ri_osp`, `nh_das` (playwright) — **written only after HTML recon captures real pages as fixtures** (wohnung-radar precedent).
- Plan 3: `results` module (bid tabs/awards parsing).
- Plan 4: `analytics` module (`price_points`, `competitors`, weekly report) — its tables are deliberately not created in Task 2 to avoid dead schema.

## Self-review notes

- Spec coverage: storage/ingest/notify/main covered; results/analytics deferred by declared plan split; per-source isolation (Task 4), digest dedup (Task 6), env guard + clean shutdown (Task 7), configurable relevance (Task 1/4) all present.
- No placeholders; fixture-first rule stated for the one live-API dependency (Task 5 steps 1-2).
- Type consistency: `RawTender` defined once (Task 3) and reused in Tasks 4-7; repo API (`upsert`, `undigested_tenders`, `mark_sent`, `record_*`, `silent_sources`) used consistently.
