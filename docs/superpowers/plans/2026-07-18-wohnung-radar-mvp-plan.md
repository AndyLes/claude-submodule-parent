# Wohnung-Radar MVP (Plan 1: Spine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working monitoring spine — poll Kleinanzeigen Leipzig, filter by criteria.yaml, dedupe, send Telegram cards with a Skip button, with dry-run mode.

**Architecture:** Single Python 3.12 async process: APScheduler triggers per-source fetch → normalize → SQLite insert-if-new → filter engine → cross-source dedup → Telegram notifier. Source adapters are isolated; one failing never stops others. Spec: `docs/superpowers/specs/2026-07-18-wohnung-radar-design.md`.

**Tech Stack:** Python 3.12, httpx, BeautifulSoup4, python-telegram-bot v21, APScheduler, SQLite (stdlib sqlite3), PyYAML, rapidfuzz, python-dotenv, pytest + pytest-asyncio.

**Scope:** Plan 1 of 3. NOT here (later plans): other portals/coops/TG-channels, Google Routes travel time, applications, calendar. Geo filter in Plan 1 = district whitelist only.

**File structure (new repo `C:\SuperWork\projects\wohnung-radar\`):**

```
pyproject.toml            # deps + pytest config
.env.example              # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DRY_RUN
config/criteria.yaml      # all search criteria (editable, never hardcoded)
src/radar/__init__.py
src/radar/models.py       # Listing dataclass
src/radar/config.py       # Criteria loader
src/radar/filters.py      # filter engine (violations vs unknown)
src/radar/db.py           # SQLite schema + insert_if_new/set_status
src/radar/dedup.py        # cross-source fuzzy dedup
src/radar/sources/__init__.py
src/radar/sources/base.py           # Source protocol
src/radar/sources/kleinanzeigen.py  # first adapter
src/radar/notify.py       # card text + keyboard + TelegramNotifier
src/radar/pipeline.py     # run_source orchestration + failure alerts
src/radar/main.py         # wiring: scheduler + bot polling
tests/test_filters.py, test_db.py, test_dedup.py, test_kleinanzeigen.py, test_notify.py, test_pipeline.py
docs/ARCHITECTURE.md, docs/DECISIONS.md
```

---

### Task 1: Repo scaffold

**Files:**
- Create: `projects/wohnung-radar/pyproject.toml`, `.gitignore`, `.env.example`, `src/radar/__init__.py`, `src/radar/sources/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create repo and scaffold**

```powershell
mkdir C:\SuperWork\projects\wohnung-radar; cd C:\SuperWork\projects\wohnung-radar
git init
mkdir src\radar\sources, tests, config, docs
```

`pyproject.toml`:

```toml
[project]
name = "wohnung-radar"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "python-telegram-bot>=21.0",
    "apscheduler>=3.10",
    "pyyaml>=6.0",
    "rapidfuzz>=3.6",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`.gitignore`:

```
__pycache__/
*.db
.env
.venv/
```

`.env.example`:

```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DRY_RUN=1
```

Create empty `src/radar/__init__.py`, `src/radar/sources/__init__.py`, `tests/__init__.py`.

- [ ] **Step 2: Install and verify pytest runs**

```powershell
python -m venv .venv; .venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m pytest
```

Expected: `no tests ran`.

- [ ] **Step 3: Commit**

```powershell
git add -A; git commit -m "chore: scaffold wohnung-radar"
```

---

### Task 2: Listing model + criteria config

**Files:**
- Create: `src/radar/models.py`, `src/radar/config.py`, `config/criteria.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

`tests/test_config.py`:

```python
from pathlib import Path
from radar.config import load_criteria

def test_load_criteria():
    c = load_criteria(Path(__file__).parents[1] / "config" / "criteria.yaml")
    assert c.min_rooms == 3
    assert c.min_area_m2 == 60
    assert c.max_rent_warm == 1000
    assert "kitchen" in c.required_features and "shower" in c.required_features
    assert "Schleußig" in c.district_whitelist
    assert c.max_travel_min == 15
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v` → FAIL (`ModuleNotFoundError: radar.config`).

- [ ] **Step 3: Implement**

`src/radar/models.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str
    district: str | None = None
    address: str | None = None
    rooms: float | None = None
    area_m2: float | None = None
    rent_warm: float | None = None
    rent_cold: float | None = None
    features_text: str = ""
    photos: list[str] = field(default_factory=list)
    posted_at: datetime | None = None
```

`src/radar/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class Criteria:
    min_rooms: float
    min_area_m2: float
    max_rent_warm: float
    required_features: list[str]
    district_whitelist: list[str]
    max_travel_min: int

def load_criteria(path: Path | str) -> Criteria:
    with open(path, encoding="utf-8") as f:
        return Criteria(**yaml.safe_load(f))
```

`config/criteria.yaml`:

```yaml
min_rooms: 3
min_area_m2: 60
max_rent_warm: 1000
required_features: [kitchen, shower]
district_whitelist:
  - Schleußig
  - Plagwitz
  - Lindenau
  - Südvorstadt
  - Waldstraßenviertel
  - Musikviertel
  - Zentrum-West
  - Zentrum-Süd
max_travel_min: 15
```

- [ ] **Step 4: Run test** → PASS. **Step 5: Commit** `git add -A; git commit -m "feat: Listing model + criteria config"`

---

### Task 3: Filter engine

**Files:**
- Create: `src/radar/filters.py`
- Test: `tests/test_filters.py`

Semantics: known value violating a limit → **violation** (hard fail); missing/unmentioned value → **unknown** (still passes, card flags it for manual check). Never silently drop for missing data (spec: error handling).

- [ ] **Step 1: Write failing tests**

`tests/test_filters.py`:

```python
import pytest
from radar.models import Listing
from radar.config import Criteria
from radar.filters import evaluate

@pytest.fixture
def crit():
    return Criteria(min_rooms=3, min_area_m2=60, max_rent_warm=1000,
                    required_features=["kitchen", "shower"],
                    district_whitelist=["Schleußig", "Plagwitz"], max_travel_min=15)

def make(**kw):
    base = dict(source="s", source_id="1", url="u", title="t",
                district="Schleußig", rooms=3, area_m2=65, rent_warm=950,
                features_text="EBK, Bad mit Dusche")
    base.update(kw)
    return Listing(**base)

def test_good_listing_passes(crit):
    r = evaluate(make(), crit)
    assert r.passed and not r.unknown

def test_boundary_values_pass(crit):
    r = evaluate(make(rooms=3, area_m2=60, rent_warm=1000), crit)
    assert r.passed

def test_too_expensive_fails(crit):
    r = evaluate(make(rent_warm=1001), crit)
    assert not r.passed and any("rent_warm" in v for v in r.violations)

def test_too_small_fails(crit):
    assert not evaluate(make(area_m2=59), crit).passed

def test_too_few_rooms_fails(crit):
    assert not evaluate(make(rooms=2), crit).passed

def test_wrong_district_fails(crit):
    assert not evaluate(make(district="Grünau"), crit).passed

def test_unknown_rent_flagged_not_dropped(crit):
    r = evaluate(make(rent_warm=None), crit)
    assert r.passed and "rent_warm" in r.unknown and r.needs_review

def test_unknown_district_flagged(crit):
    r = evaluate(make(district=None), crit)
    assert r.passed and "district" in r.unknown

def test_missing_shower_mention_flagged(crit):
    r = evaluate(make(features_text="EBK vorhanden"), crit)
    assert r.passed and "feature:shower" in r.unknown
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_filters.py -v` → FAIL (no module).

- [ ] **Step 3: Implement**

`src/radar/filters.py`:

```python
from dataclasses import dataclass, field
from .config import Criteria
from .models import Listing

FEATURE_KEYWORDS = {
    "kitchen": ["küche", "ebk", "einbauküche", "kochnische"],
    "shower": ["dusche", "duschbad"],
}

@dataclass
class FilterResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.passed and bool(self.unknown)

def evaluate(listing: Listing, c: Criteria) -> FilterResult:
    violations: list[str] = []
    unknown: list[str] = []

    def check_min(value, minimum, name):
        if value is None:
            unknown.append(name)
        elif value < minimum:
            violations.append(f"{name}={value} < {minimum}")

    check_min(listing.rooms, c.min_rooms, "rooms")
    check_min(listing.area_m2, c.min_area_m2, "area_m2")

    if listing.rent_warm is None:
        unknown.append("rent_warm")
    elif listing.rent_warm > c.max_rent_warm:
        violations.append(f"rent_warm={listing.rent_warm} > {c.max_rent_warm}")

    text = listing.features_text.lower()
    for feat in c.required_features:
        if not any(kw in text for kw in FEATURE_KEYWORDS.get(feat, [feat])):
            unknown.append(f"feature:{feat}")  # not mentioned != absent

    if listing.district is None:
        unknown.append("district")
    elif listing.district.lower() not in (d.lower() for d in c.district_whitelist):
        violations.append(f"district={listing.district} not in whitelist")

    return FilterResult(passed=not violations, violations=violations, unknown=unknown)
```

- [ ] **Step 4: Run tests** → all PASS. **Step 5: Commit** `git add -A; git commit -m "feat: filter engine with violations/unknown semantics"`

---

### Task 4: SQLite layer

**Files:**
- Create: `src/radar/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

`tests/test_db.py`:

```python
from radar import db as dbm
from radar.models import Listing

def make(sid="a1"):
    return Listing(source="kleinanzeigen", source_id=sid, url="http://x/" + sid,
                   title="3-Zi Schleußig", district="Schleußig",
                   rooms=3, area_m2=70, rent_warm=900)

def test_insert_if_new_returns_id_then_none(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    row_id = dbm.insert_if_new(conn, make())
    assert isinstance(row_id, int)
    assert dbm.insert_if_new(conn, make()) is None  # same (source, source_id)

def test_set_status_and_recent(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    row_id = dbm.insert_if_new(conn, make())
    dbm.set_status(conn, row_id, "notified")
    rows = dbm.recent_listings(conn)
    assert rows[0]["status"] == "notified"
    assert rows[0]["title"] == "3-Zi Schleußig"
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**

`src/radar/db.py`:

```python
import json
import sqlite3
from dataclasses import asdict
from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    district TEXT,
    rooms REAL,
    area_m2 REAL,
    rent_warm REAL,
    status TEXT NOT NULL DEFAULT 'new',
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (source, source_id)
);
"""

def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def insert_if_new(conn: sqlite3.Connection, listing: Listing) -> int | None:
    """Row id if new, None if (source, source_id) already seen."""
    payload = json.dumps(asdict(listing), default=str, ensure_ascii=False)
    try:
        cur = conn.execute(
            "INSERT INTO listings (source, source_id, url, title, district,"
            " rooms, area_m2, rent_warm, payload_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (listing.source, listing.source_id, listing.url, listing.title,
             listing.district, listing.rooms, listing.area_m2,
             listing.rent_warm, payload))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def set_status(conn: sqlite3.Connection, listing_id: int, status: str) -> None:
    conn.execute("UPDATE listings SET status = ? WHERE id = ?", (status, listing_id))
    conn.commit()

def recent_listings(conn: sqlite3.Connection, limit: int = 200) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM listings ORDER BY id DESC LIMIT ?",
                        (limit,)).fetchall()
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git add -A; git commit -m "feat: sqlite layer with insert_if_new dedup key"`

---

### Task 5: Cross-source dedup

**Files:**
- Create: `src/radar/dedup.py`
- Test: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

`tests/test_dedup.py`:

```python
from radar import db as dbm
from radar.dedup import is_cross_source_duplicate
from radar.models import Listing

def seed(conn, source, title, rent, area):
    dbm.insert_if_new(conn, Listing(source=source, source_id="x1", url="u",
                                    title=title, rent_warm=rent, area_m2=area))

def test_same_flat_other_source_is_duplicate(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    seed(conn, "immowelt", "Schöne 3-Zimmer-Wohnung in Schleußig mit Balkon", 950, 72)
    cand = Listing(source="kleinanzeigen", source_id="y2", url="u2",
                   title="3 Zimmer Wohnung Schleußig Balkon", rent_warm=950, area_m2=72)
    assert is_cross_source_duplicate(cand, dbm.recent_listings(conn))

def test_same_source_never_duplicate(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    seed(conn, "kleinanzeigen", "3 Zimmer Wohnung Schleußig", 950, 72)
    cand = Listing(source="kleinanzeigen", source_id="y2", url="u2",
                   title="3 Zimmer Wohnung Schleußig", rent_warm=950, area_m2=72)
    assert not is_cross_source_duplicate(cand, dbm.recent_listings(conn))

def test_different_rent_not_duplicate(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    seed(conn, "immowelt", "3 Zimmer Wohnung Schleußig", 700, 72)
    cand = Listing(source="kleinanzeigen", source_id="y2", url="u2",
                   title="3 Zimmer Wohnung Schleußig", rent_warm=950, area_m2=72)
    assert not is_cross_source_duplicate(cand, dbm.recent_listings(conn))
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**

`src/radar/dedup.py`:

```python
from rapidfuzz import fuzz, utils
from .models import Listing

def is_cross_source_duplicate(listing: Listing, rows) -> bool:
    """True if a listing from ANOTHER source looks like the same flat."""
    for row in rows:
        if row["source"] == listing.source:
            continue
        if (listing.rent_warm is not None and row["rent_warm"] is not None
                and abs(listing.rent_warm - row["rent_warm"]) > 20):
            continue
        if (listing.area_m2 is not None and row["area_m2"] is not None
                and abs(listing.area_m2 - row["area_m2"]) > 2):
            continue
        if fuzz.token_set_ratio(listing.title, row["title"] or "",
                                processor=utils.default_process) >= 90:
            return True
    return False
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git add -A; git commit -m "feat: cross-source fuzzy dedup"`

---

### Task 6: Kleinanzeigen adapter

**Files:**
- Create: `src/radar/sources/base.py`, `src/radar/sources/kleinanzeigen.py`
- Test: `tests/test_kleinanzeigen.py`

Kleinanzeigen search results = `article.aditem` elements. The listed price is usually **Kaltmiete** → map to `rent_cold`, leave `rent_warm=None` (filter flags it `unknown` → card says "перевірити"). Parser is tested on a synthetic fixture mirroring real markup; markup drift is caught by the failure-alert in Task 8.

- [ ] **Step 1: Write failing tests**

`tests/test_kleinanzeigen.py`:

```python
from radar.sources.kleinanzeigen import parse_search_page

FIXTURE = """
<html><body>
<article class="aditem" data-adid="111222333">
  <div class="aditem-main--top--left">04229 Leipzig - Schleußig</div>
  <a class="ellipsis" href="/s-anzeige/3-zi-whg/111222333">Helle 3-Zimmer-Wohnung mit EBK</a>
  <p class="aditem-main--middle--description">Schöne Wohnung, Bad mit Dusche, Balkon.</p>
  <p class="aditem-main--middle--price-shipping--price">850 €</p>
  <span class="simpletag">72 m²</span>
  <span class="simpletag">3 Zimmer</span>
</article>
<article class="aditem" data-adid="444555666">
  <div class="aditem-main--top--left">04277 Leipzig</div>
  <a class="ellipsis" href="/s-anzeige/whg/444555666">Wohnung zur Miete</a>
  <p class="aditem-main--middle--price-shipping--price">1.100 €</p>
</article>
</body></html>
"""

def test_parses_full_ad():
    ads = parse_search_page(FIXTURE)
    ad = ads[0]
    assert ad.source == "kleinanzeigen"
    assert ad.source_id == "111222333"
    assert ad.url == "https://www.kleinanzeigen.de/s-anzeige/3-zi-whg/111222333"
    assert ad.title == "Helle 3-Zimmer-Wohnung mit EBK"
    assert ad.district == "Schleußig"
    assert ad.rooms == 3 and ad.area_m2 == 72
    assert ad.rent_cold == 850 and ad.rent_warm is None
    assert "Dusche" in ad.features_text and "EBK" in ad.title

def test_parses_sparse_ad_without_crashing():
    ad = parse_search_page(FIXTURE)[1]
    assert ad.rent_cold == 1100
    assert ad.district is None and ad.rooms is None and ad.area_m2 is None

def test_empty_page():
    assert parse_search_page("<html></html>") == []
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**

`src/radar/sources/base.py`:

```python
from typing import Protocol
from ..models import Listing

class Source(Protocol):
    name: str
    async def fetch(self) -> list[Listing]: ...
```

`src/radar/sources/kleinanzeigen.py`:

```python
import re
import httpx
from bs4 import BeautifulSoup
from ..models import Listing

# rooms>=3, area>=60, price<=1000 encoded in the KA search URL
SEARCH_URL = ("https://www.kleinanzeigen.de/s-wohnung-mieten/leipzig/"
              "preis::1000/c203l4066+wohnung_mieten.qm_von:60"
              "+wohnung_mieten.zimmer_von:3")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

def _num(text: str | None) -> float | None:
    m = re.search(r"[\d.,]+", text or "")
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))

def _district(location: str) -> str | None:
    # "04229 Leipzig - Schleußig" -> "Schleußig"; "04277 Leipzig" -> None
    # split on " - " so hyphenated districts (Zentrum-Süd) stay intact
    if " - " in location:
        return location.split(" - ", 1)[1].strip() or None
    return None

def parse_search_page(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    for ad in soup.select("article.aditem[data-adid]"):
        # per-ad fault isolation: one malformed promoted-slot ad must not kill the page
        link = ad.select_one("a.ellipsis")
        if link is None or link.get("href") is None:
            continue
        loc = ad.select_one(".aditem-main--top--left")
        price = ad.select_one(".aditem-main--middle--price-shipping--price")
        desc = ad.select_one(".aditem-main--middle--description")
        tags = [t.get_text(strip=True) for t in ad.select(".simpletag")]
        area = rooms = None
        for t in tags:
            if "m²" in t:
                area = _num(t)
            elif "Zimmer" in t:
                rooms = _num(t)
        out.append(Listing(
            source="kleinanzeigen",
            source_id=ad["data-adid"],
            url="https://www.kleinanzeigen.de" + link["href"],
            title=link.get_text(strip=True),
            district=_district(loc.get_text(strip=True) if loc else ""),
            rooms=rooms,
            area_m2=area,
            rent_cold=_num(price.get_text() if price else None),
            features_text=" ".join(
                [desc.get_text(" ", strip=True) if desc else ""] + tags),
        ))
    return out

class KleinanzeigenSource:
    name = "kleinanzeigen"

    async def fetch(self) -> list[Listing]:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30,
                                     follow_redirects=True) as client:
            resp = await client.get(SEARCH_URL)
            resp.raise_for_status()
        return parse_search_page(resp.text)
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git add -A; git commit -m "feat: kleinanzeigen adapter"`

---

### Task 7: Telegram notifier

**Files:**
- Create: `src/radar/notify.py`
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write failing tests**

`tests/test_notify.py`:

```python
from radar.filters import FilterResult
from radar.models import Listing
from radar.notify import build_card_text, build_keyboard

def make():
    return Listing(source="kleinanzeigen", source_id="1", url="http://x",
                   title="3-Zi Schleußig", district="Schleußig",
                   rooms=3, area_m2=72, rent_cold=850)

def test_card_contains_key_facts():
    text = build_card_text(make(), FilterResult(passed=True, unknown=["rent_warm"]))
    assert "3-Zi Schleußig" in text
    assert "850" in text and "72" in text
    assert "http://x" in text
    assert "rent_warm" in text  # unknown flagged, not hidden

def test_card_without_unknowns_has_no_warning():
    text = build_card_text(make(), FilterResult(passed=True))
    assert "Перевірити" not in text

def test_keyboard_carries_listing_id():
    kb = build_keyboard(42)
    assert kb.inline_keyboard[0][0].callback_data == "skip:42"
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**

`src/radar/notify.py`:

```python
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from .filters import FilterResult
from .models import Listing

def build_card_text(listing: Listing, result: FilterResult) -> str:
    rent = listing.rent_warm or listing.rent_cold or "?"
    warm = "warm" if listing.rent_warm else "kalt" if listing.rent_cold else ""
    lines = [
        f"🏠 {listing.title}",
        f"💶 {rent} € {warm} | 📐 {listing.area_m2 or '?'} м² | 🚪 {listing.rooms or '?'} кімн.",
        f"📍 {listing.district or 'район невідомий'} · {listing.source}",
    ]
    if result.unknown:
        lines.append("⚠️ Перевірити: " + ", ".join(result.unknown))
    lines.append(listing.url)
    return "\n".join(lines)

def build_keyboard(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Пропустити", callback_data=f"skip:{listing_id}")]])

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, dry_run: bool = False):
        self.bot = Bot(token)
        self.chat_id = chat_id
        self.dry_run = dry_run

    async def notify(self, listing_id: int, listing: Listing,
                     result: FilterResult) -> None:
        text = build_card_text(listing, result)
        if self.dry_run:
            print(f"[DRY-RUN notify]\n{text}\n")
            return
        await self.bot.send_message(chat_id=self.chat_id, text=text,
                                    reply_markup=build_keyboard(listing_id))

    async def alert(self, text: str) -> None:
        if self.dry_run:
            print(f"[DRY-RUN alert] {text}")
            return
        await self.bot.send_message(chat_id=self.chat_id, text=text)
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git add -A; git commit -m "feat: telegram notifier with dry-run"`

---

### Task 8: Pipeline (orchestration + failure alerts)

**Files:**
- Create: `src/radar/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

`tests/test_pipeline.py`:

```python
import pytest
from radar import db as dbm
from radar.config import Criteria
from radar.models import Listing
from radar.pipeline import Pipeline

class FakeNotifier:
    def __init__(self):
        self.notified, self.alerts = [], []
    async def notify(self, listing_id, listing, result):
        self.notified.append(listing.source_id)
    async def alert(self, text):
        self.alerts.append(text)

class FakeSource:
    name = "fake"
    def __init__(self, listings=None, fail=False):
        self.listings, self.fail = listings or [], fail
    async def fetch(self):
        if self.fail:
            raise RuntimeError("boom")
        return self.listings

def crit():
    return Criteria(min_rooms=3, min_area_m2=60, max_rent_warm=1000,
                    required_features=[], district_whitelist=["Schleußig"],
                    max_travel_min=15)

def good(sid="g1"):
    return Listing(source="fake", source_id=sid, url="u" + sid, title="T" + sid,
                   district="Schleußig", rooms=3, area_m2=70, rent_warm=900)

async def test_new_passing_listing_notified_once(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    p = Pipeline(conn, crit(), n)
    src = FakeSource([good()])
    await p.run_source(src)
    await p.run_source(src)  # second cycle: already seen
    assert n.notified == ["g1"]
    assert dbm.recent_listings(conn)[0]["status"] == "notified"

async def test_failing_listing_stored_filtered_out(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    bad = good("b1"); bad.rent_warm = 2000
    await Pipeline(conn, crit(), n).run_source(FakeSource([bad]))
    assert n.notified == []
    assert dbm.recent_listings(conn)[0]["status"] == "filtered_out"

async def test_source_failure_alerts_after_threshold(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    p = Pipeline(conn, crit(), n, alert_after=3)
    src = FakeSource(fail=True)
    for _ in range(4):
        await p.run_source(src)   # must not raise
    assert len(n.alerts) == 1     # alert exactly once at threshold
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**

`src/radar/pipeline.py`:

```python
import logging
from . import db as dbm
from .dedup import is_cross_source_duplicate
from .filters import evaluate

log = logging.getLogger("radar")

class Pipeline:
    def __init__(self, conn, criteria, notifier, alert_after: int = 3):
        self.conn = conn
        self.criteria = criteria
        self.notifier = notifier
        self.alert_after = alert_after
        self.failures: dict[str, int] = {}

    async def run_source(self, source) -> None:
        try:
            listings = await source.fetch()
            self.failures[source.name] = 0
        except Exception as exc:
            n = self.failures.get(source.name, 0) + 1
            self.failures[source.name] = n
            log.warning("source %s failed (%d): %s", source.name, n, exc)
            if n == self.alert_after:
                await self.notifier.alert(
                    f"⚠️ Джерело {source.name} не відповідає {n} циклів поспіль")
            return
        existing = dbm.recent_listings(self.conn)
        for listing in listings:
            # per-listing isolation: one bad listing or a Telegram outage must not
            # drop the rest of the batch; notify failures stay visible via status
            try:
                row_id = dbm.insert_if_new(self.conn, listing)
                if row_id is None:
                    continue
                result = evaluate(listing, self.criteria)
                if not result.passed:
                    dbm.set_status(self.conn, row_id, "filtered_out")
                    continue
                if is_cross_source_duplicate(listing, existing):
                    dbm.set_status(self.conn, row_id, "duplicate")
                    continue
                try:
                    await self.notifier.notify(row_id, listing, result)
                except Exception:
                    log.warning("notify failed for %s:%s", listing.source,
                                listing.source_id, exc_info=True)
                    dbm.set_status(self.conn, row_id, "notify_failed")
                    continue
                dbm.set_status(self.conn, row_id, "notified")
            except Exception:
                log.warning("listing processing failed for %s:%s", listing.source,
                            getattr(listing, "source_id", "?"), exc_info=True)
                continue
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git add -A; git commit -m "feat: pipeline with isolated source failures + alerts"`

---

### Task 9: Main wiring (scheduler + bot polling + skip button)

**Files:**
- Create: `src/radar/main.py`

No unit test (pure wiring); verified by dry-run in Task 10.

- [ ] **Step 1: Implement**

`src/radar/main.py`:

```python
import asyncio
import logging
import os
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram.ext import Application, CallbackQueryHandler

from . import db as dbm
from .config import load_criteria
from .notify import TelegramNotifier
from .pipeline import Pipeline
from .sources.kleinanzeigen import KleinanzeigenSource

POLL_MINUTES = 7  # portals; staggered by jitter

async def on_skip(update, context):
    query = update.callback_query
    listing_id = int(query.data.split(":")[1])
    dbm.set_status(context.bot_data["conn"], listing_id, "skipped")
    await query.answer("Пропущено")
    await query.edit_message_reply_markup(None)

async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    root = Path(__file__).resolve().parents[2]
    conn = dbm.connect(str(root / "radar.db"))
    criteria = load_criteria(root / "config" / "criteria.yaml")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (see .env.example)")
    notifier = TelegramNotifier(token, chat_id,
                                dry_run=os.getenv("DRY_RUN", "0") == "1")
    pipeline = Pipeline(conn, criteria, notifier)
    sources = [KleinanzeigenSource()]

    app = Application.builder().token(token).build()
    app.bot_data["conn"] = conn
    app.add_handler(CallbackQueryHandler(on_skip, pattern=r"^skip:"))

    scheduler = AsyncIOScheduler()
    for source in sources:
        scheduler.add_job(pipeline.run_source, "interval",
                          minutes=POLL_MINUTES, jitter=60, args=[source])
    scheduler.start()

    async with app:
        await app.start()
        await app.updater.start_polling()
        for source in sources:
            await pipeline.run_source(source)  # immediate first cycle
        try:
            await asyncio.Event().wait()
        finally:
            # PTB __aexit__ raises if app is still running — stop cleanly first
            await app.updater.stop()
            await app.stop()
            scheduler.shutdown(wait=False)

def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Full test suite** `.venv\Scripts\python -m pytest -v` → all PASS.
- [ ] **Step 3: Commit** `git add -A; git commit -m "feat: main wiring — scheduler + bot + skip"`

---

### Task 10: Dry-run verification + docs

**Files:**
- Create: `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `README.md`

- [ ] **Step 1: Dry-run against live Kleinanzeigen**

Create `.env` from `.env.example` with real `TELEGRAM_BOT_TOKEN` (from @BotFather) + `TELEGRAM_CHAT_ID`, keep `DRY_RUN=1`. Run:

```powershell
.venv\Scripts\python -m radar.main
```

Expected: log of first cycle; `[DRY-RUN notify]` cards printed for any matching live listings (or none if no matches right now — verify via `radar.db` that rows were inserted). If KA blocks (HTTP 403): failure counter increments — this is the known best-effort path; note it in DECISIONS.md.

- [ ] **Step 2: Live smoke test** — set `DRY_RUN=0`, run once, confirm a card with Skip button arrives in Telegram and Skip updates status to `skipped` in DB (`SELECT status FROM listings`). Stop the process.

- [ ] **Step 3: Write docs**

`docs/ARCHITECTURE.md` — the pipeline diagram (source → normalize → insert_if_new → filter → dedup → notify), component list, file map from this plan's header.
`docs/DECISIONS.md` — record: KA price = Kaltmiete → unknown rent_warm flagged not dropped; district whitelist as geo stage 1 (Routes API in Plan 2); dry-run mode; alert_after=3; no alert on notify failures (Telegram down → alert undeliverable too; visibility via notify_failed status); Plan-2 landmines: dedup snapshot is taken once per run_source (concurrent multi-source cycles could miss same-window cross-source dups) and recent_listings limit=200 bounds the dedup window.
`README.md` — setup (venv, .env, BotFather), run command, Windows autostart via Task Scheduler: `schtasks /create /tn WohnungRadar /tr "C:\SuperWork\projects\wohnung-radar\.venv\Scripts\pythonw.exe -m radar.main" /sc onstart` (note: run from repo dir).

- [ ] **Step 4: Commit** `git add -A; git commit -m "docs: architecture, decisions, setup"`

---

## Follow-up plans (not in this document)

- **Plan 2 — sources + geo:** Immowelt, IS24 (Flathunter-adapted), coop adapters (LWB, Lipsia, UNITAS, Kontakt, VLW, Wogetra, BGL), Telegram channels via Telethon, WhatsApp-forward parsing (rule-based + Haiku fallback), Nominatim geocoding + Google Routes ≤15-min check to Könneritzstraße 47.
- **Plan 3 — applications + calendar:** tenant profile, German draft generation, approve-to-send email, landlord-reply forward → date extraction → Google Calendar event, `/status` + daily digest.
