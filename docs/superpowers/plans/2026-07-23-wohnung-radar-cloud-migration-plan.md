# Wohnung-Radar Cloud Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Wohnung-Radar 24/7 for free on GitHub Actions (30-min cron) + Supabase Postgres, with no dependency on the user's local PC.

**Architecture:** A new `python -m radar.cycle` entrypoint runs ONE stateless pass (poll sources → notify + drain Telegram `getUpdates` → dispatch button/forward handlers) and exits. `db.py` is rewritten from SQLite to Postgres (`psycopg` v3) against Supabase; in-memory bot state moves to Postgres tables; the persistent PTB Application is replaced by a `dispatch_update` switch driven by `getUpdates`. All pure-logic modules (sources, filters, geo, draft, appointment, msgparse, contact, mailer, calendar_api, report, notify, config, profile, models) stay unchanged.

**Tech Stack:** Python 3.12, psycopg[binary]>=3.2 (Postgres), Supabase (managed Postgres, session pooler), python-telegram-bot 22.x (`telegram.Bot` only, no `Application`), GitHub Actions, pytest.

**Repo/spec:** `C:\SuperWork\projects\wohnung-radar\` (own git repo). Spec: `docs/superpowers/specs/2026-07-23-wohnung-radar-cloud-migration-design.md` (in the parent `C:\SuperWork` repo).

**Testing DB:** Tasks that touch Postgres run against a **local Postgres** the implementer starts via Docker:
```powershell
docker run -d --name radar-pg -e POSTGRES_PASSWORD=radar -e POSTGRES_DB=radar_test -p 55432:5432 postgres:16
```
Test DSN: `postgresql://postgres:radar@localhost:55432/radar_test`. Tests read `TEST_DATABASE_URL` env (default that DSN). If Docker is unavailable, report BLOCKED — do NOT fall back to the user's real Supabase for tests.

**File map:**

```
pyproject.toml                    # +psycopg[binary]; drop apscheduler/telethon from runtime deps (keep as optional)
src/radar/db.py                   # REWRITE: psycopg/Postgres, same signatures + new pending/bot_state tables
src/radar/botclient.py            # NEW: thin Bot wrapper (send_message, get_updates, answer_callback) + Notifier
src/radar/dispatch.py             # NEW: dispatch_update(update, deps) — switch reusing existing handlers
src/radar/handlers.py             # NEW: handler fns moved out of main.py (draft/applied/send_email/forward/cal/callisting/status), framework-free
src/radar/cycle.py                # NEW: entrypoint — one poll+drain pass; --digest mode
src/radar/pipeline.py             # MODIFY: notifier is botclient.Notifier; pending_drafts/appointments read/write via db
src/radar/main.py                 # KEEP for local runs but no longer the cloud path (or delete — decided in Task 9)
.github/workflows/poll.yml        # NEW: */30 cron -> radar.cycle
.github/workflows/digest.yml      # NEW: daily -> radar.cycle --digest
.env.example                      # +DATABASE_URL, +GOOGLE_CALENDAR_TOKEN
README.md, docs/ARCHITECTURE.md, docs/DECISIONS.md
tests/test_db_pg.py, test_dispatch.py, test_cycle.py, conftest.py (pg fixture)
```

**Scope note:** This plan produces a working cloud deployment. It does NOT migrate historical `radar.db` rows (fresh start) and does NOT port the Telethon TG-group reader (dropped in cloud). The existing `tests/test_tg_groups.py` and `test_main_startup.py` (APScheduler/PTB-Application specific) may be deleted or skipped in Task 9 — decided there.

---

### Task 1: Postgres deps + test fixture

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py` (pg fixture)
- Test: `tests/test_pg_smoke.py`

- [ ] **Step 1: Add dependency** — in `pyproject.toml` `[project] dependencies`, add `"psycopg[binary]>=3.2"`. Install: `.venv\Scripts\pip install -e ".[dev]"`.

- [ ] **Step 2: Write the failing smoke test** `tests/test_pg_smoke.py`:

```python
import os
import psycopg

def test_pg_reachable():
    dsn = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:radar@localhost:55432/radar_test")
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
```

- [ ] **Step 3: Start Postgres and run** — start the Docker container (see plan header), then `.venv\Scripts\python -m pytest tests/test_pg_smoke.py -v`. Expected: PASS. If it errors "connection refused", the container isn't up → start it; if Docker itself is missing → report BLOCKED.

- [ ] **Step 4: Add the shared pg fixture** to `tests/conftest.py`:

```python
import os
import psycopg
import pytest

TEST_DSN = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:radar@localhost:55432/radar_test")

@pytest.fixture
def pg_conn():
    """A clean Postgres connection with the radar schema, dropped after each test."""
    from radar import db as dbm
    conn = dbm.connect(TEST_DSN)
    yield conn
    # drop all radar tables so tests are isolated
    conn.execute("DROP TABLE IF EXISTS listings, geocode_cache, pending_drafts, "
                 "pending_appointments, bot_state CASCADE")
    conn.commit()
    conn.close()
```

(This fixture imports `radar.db.connect`, which Task 2 rewrites — it will error until Task 2. That's fine; no test uses `pg_conn` yet.)

- [ ] **Step 5: Commit** — `git add -A; git commit -m "chore: postgres dep + test fixture"`

---

### Task 2: Rewrite db.py on Postgres — schema + connect + insert_if_new

**Files:**
- Modify: `src/radar/db.py` (full rewrite)
- Test: `tests/test_db_pg.py`

The existing SQLite `db.py` public API must be preserved so unchanged callers keep working. This task ports schema + `connect` + `insert_if_new`; later tasks port the rest.

- [ ] **Step 1: Write failing tests** `tests/test_db_pg.py`:

```python
from radar import db as dbm
from radar.models import Listing

def make(sid="a1"):
    return Listing(source="kleinanzeigen", source_id=sid, url="http://x/" + sid,
                   title="3-Zi Schleußig", district="Schleußig",
                   rooms=3, area_m2=70, rent_warm=900, rent_cold=None)

def test_connect_creates_schema(pg_conn):
    cols = {r[0] for r in pg_conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='listings'").fetchall()}
    assert {"id","source","source_id","url","title","district","rooms","area_m2",
            "rent_warm","rent_cold","status","payload_json","created_at"} <= cols

def test_insert_if_new_returns_id_then_none(pg_conn):
    row_id = dbm.insert_if_new(pg_conn, make())
    assert isinstance(row_id, int)
    assert dbm.insert_if_new(pg_conn, make()) is None  # same (source, source_id)

def test_insert_constraint_violation_raises(pg_conn):
    import psycopg
    bad = make(); bad.url = None
    import pytest
    with pytest.raises(psycopg.errors.NotNullViolation):
        dbm.insert_if_new(pg_conn, bad)
```

- [ ] **Step 2: Run → FAIL** (`radar.db` still SQLite / no `connect(dsn)` semantics). `.venv\Scripts\python -m pytest tests/test_db_pg.py -v`.

- [ ] **Step 3: Rewrite `src/radar/db.py`** (schema + connect + insert_if_new):

```python
import json
from dataclasses import asdict
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    district TEXT,
    rooms DOUBLE PRECISION,
    area_m2 DOUBLE PRECISION,
    rent_warm DOUBLE PRECISION,
    rent_cold DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'new',
    payload_json TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, source_id)
);
CREATE TABLE IF NOT EXISTS geocode_cache (
    address TEXT PRIMARY KEY, verdict TEXT, minutes INTEGER
);
CREATE TABLE IF NOT EXISTS pending_drafts (
    listing_id BIGINT PRIMARY KEY, version TEXT, draft_text TEXT, email TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pending_appointments (
    token TEXT PRIMARY KEY, appointment_json JSONB, orig_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT);
"""

def connect(dsn: str) -> psycopg.Connection:
    conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)
    conn.execute(SCHEMA)
    conn.commit()
    return conn

def insert_if_new(conn: psycopg.Connection, listing: Listing) -> int | None:
    """Row id if new, None if (source, source_id) already seen.
    Non-UNIQUE constraint violations (e.g. NOT NULL) propagate."""
    payload = json.dumps(asdict(listing), default=str, ensure_ascii=False)
    try:
        with conn.transaction():
            row = conn.execute(
                "INSERT INTO listings (source, source_id, url, title, district,"
                " rooms, area_m2, rent_warm, rent_cold, payload_json)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (source, source_id) DO NOTHING RETURNING id",
                (listing.source, listing.source_id, listing.url, listing.title,
                 listing.district, listing.rooms, listing.area_m2,
                 listing.rent_warm, listing.rent_cold, payload)).fetchone()
        return row["id"] if row else None
    except psycopg.errors.NotNullViolation:
        raise
```

Note: `conn.transaction()` scopes the INSERT so a NotNullViolation rolls back cleanly without poisoning the connection (Postgres aborts the whole tx on error, unlike SQLite). `ON CONFLICT DO NOTHING RETURNING id` yields no row on a duplicate → `fetchone()` returns `None`.

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `git add -A; git commit -m "feat: postgres db schema + insert_if_new"`

---

### Task 3: db.py — status, listing reads, listing_from_row

**Files:**
- Modify: `src/radar/db.py`
- Test: `tests/test_db_pg.py`

- [ ] **Step 1: Append failing tests** to `tests/test_db_pg.py`:

```python
def test_set_status_and_recent(pg_conn):
    row_id = dbm.insert_if_new(pg_conn, make())
    dbm.set_status(pg_conn, row_id, "notified")
    rows = dbm.recent_listings(pg_conn)
    assert rows[0]["status"] == "notified" and rows[0]["title"] == "3-Zi Schleußig"

def test_get_listing_and_from_row(pg_conn):
    row_id = dbm.insert_if_new(pg_conn, make("b2"))
    row = dbm.get_listing(pg_conn, row_id)
    listing = dbm.listing_from_row(row)
    assert listing.source_id == "b2" and listing.rooms == 3

def test_listings_by_status(pg_conn):
    a = dbm.insert_if_new(pg_conn, make("s1")); dbm.set_status(pg_conn, a, "applied")
    dbm.insert_if_new(pg_conn, make("s2"))  # stays 'new'
    applied = dbm.listings_by_status(pg_conn, "applied")
    assert [r["source_id"] for r in applied] == ["s1"]

def test_pending_listings_new_and_notify_failed(pg_conn):
    a = dbm.insert_if_new(pg_conn, make("p1"))
    b = dbm.insert_if_new(pg_conn, make("p2")); dbm.set_status(pg_conn, b, "notify_failed")
    c = dbm.insert_if_new(pg_conn, make("p3")); dbm.set_status(pg_conn, c, "notified")
    ids = {r["source_id"] for r in dbm.pending_listings(pg_conn)}
    assert ids == {"p1", "p2"}
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Add to `db.py`:**

```python
def set_status(conn, listing_id: int, status: str) -> None:
    conn.execute("UPDATE listings SET status=%s WHERE id=%s", (status, listing_id))
    conn.commit()

def recent_listings(conn, limit: int = 200):
    return conn.execute("SELECT * FROM listings ORDER BY id DESC LIMIT %s", (limit,)).fetchall()

def get_listing(conn, listing_id: int):
    return conn.execute("SELECT * FROM listings WHERE id=%s", (listing_id,)).fetchone()

def listings_by_status(conn, status: str, limit: int = 50):
    return conn.execute("SELECT * FROM listings WHERE status=%s ORDER BY id DESC LIMIT %s",
                        (status, limit)).fetchall()

def pending_listings(conn):
    return conn.execute("SELECT * FROM listings WHERE status IN ('new','notify_failed') "
                        "ORDER BY id ASC").fetchall()

def listing_from_row(row) -> Listing:
    import json as _json
    from datetime import datetime
    payload = _json.loads(row["payload_json"]) if row["payload_json"] else {}
    posted = payload.get("posted_at")
    posted_at = None
    if isinstance(posted, str):
        try:
            posted_at = datetime.fromisoformat(posted)
        except ValueError:
            posted_at = None
    return Listing(
        source=row["source"], source_id=row["source_id"], url=row["url"],
        title=row["title"] or "", district=row["district"],
        address=payload.get("address"),
        rooms=row["rooms"], area_m2=row["area_m2"],
        rent_warm=row["rent_warm"], rent_cold=row["rent_cold"],
        features_text=payload.get("features_text", ""),
        photos=payload.get("photos", []) or [], posted_at=posted_at)
```

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `git add -A; git commit -m "feat: postgres status + listing reads"`

---

### Task 4: db.py — DbCache, status_counts, recent_notified

**Files:**
- Modify: `src/radar/db.py`
- Test: `tests/test_db_pg.py`

- [ ] **Step 1: Append failing tests:**

```python
def test_db_cache_roundtrip(pg_conn):
    cache = dbm.DbCache(pg_conn)
    assert "addr1" not in cache
    cache["addr1"] = ("ok", 12)
    assert "addr1" in cache and cache["addr1"] == ("ok", 12)
    cache["addr2"] = ("unknown", None)
    assert cache["addr2"] == ("unknown", None)

def test_db_cache_persists_new_connection(pg_conn):
    dbm.DbCache(pg_conn)["addrX"] = ("too_far", 40)
    # a second cache over the same conn sees it
    assert dbm.DbCache(pg_conn)["addrX"] == ("too_far", 40)

def test_status_counts(pg_conn):
    dbm.insert_if_new(pg_conn, make("c1"))
    b = dbm.insert_if_new(pg_conn, make("c2")); dbm.set_status(pg_conn, b, "notified")
    counts = dbm.status_counts(pg_conn)
    assert counts["new"] == 1 and counts["notified"] == 1

def test_recent_notified_window(pg_conn):
    a = dbm.insert_if_new(pg_conn, make("n1")); dbm.set_status(pg_conn, a, "notified")
    b = dbm.insert_if_new(pg_conn, make("n2")); dbm.set_status(pg_conn, b, "notified")
    pg_conn.execute("UPDATE listings SET created_at = now() - interval '48 hours' WHERE id=%s", (b,))
    pg_conn.commit()
    rows = dbm.recent_notified(pg_conn, since_hours=24)
    assert [r["source_id"] for r in rows] == ["n1"]
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Add to `db.py`:**

```python
class DbCache:
    """Dict-like persistent geocode cache backed by the geocode_cache table.
    Value is a (verdict, minutes|None) tuple."""
    def __init__(self, conn):
        self.conn = conn

    def __contains__(self, address: str) -> bool:
        return self.conn.execute("SELECT 1 FROM geocode_cache WHERE address=%s",
                                 (address,)).fetchone() is not None

    def __getitem__(self, address: str):
        row = self.conn.execute("SELECT verdict, minutes FROM geocode_cache WHERE address=%s",
                                (address,)).fetchone()
        if row is None:
            raise KeyError(address)
        return (row["verdict"], row["minutes"])

    def __setitem__(self, address: str, value) -> None:
        verdict, minutes = value
        self.conn.execute(
            "INSERT INTO geocode_cache (address, verdict, minutes) VALUES (%s,%s,%s) "
            "ON CONFLICT (address) DO UPDATE SET verdict=EXCLUDED.verdict, minutes=EXCLUDED.minutes",
            (address, verdict, minutes))
        self.conn.commit()

def status_counts(conn) -> dict:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM listings GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}

def recent_notified(conn, since_hours: int = 24):
    return conn.execute(
        "SELECT * FROM listings WHERE status IN ('notified','applied','viewing_scheduled') "
        "AND created_at >= now() - make_interval(hours => %s) "
        "ORDER BY created_at DESC, id DESC", (since_hours,)).fetchall()
```

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `git add -A; git commit -m "feat: postgres DbCache + status_counts + recent_notified"`

---

### Task 5: db.py — pending drafts/appointments + bot offset helpers

**Files:**
- Modify: `src/radar/db.py`
- Test: `tests/test_db_pg.py`

These replace the in-memory `pending_drafts` / `pending_appointments` dicts and store the Telegram `getUpdates` offset.

- [ ] **Step 1: Append failing tests:**

```python
def test_draft_store_roundtrip_and_pop(pg_conn):
    dbm.put_draft(pg_conn, 7, "verA", "Sehr geehrte...", "l@x.de")
    got = dbm.get_draft(pg_conn, 7)
    assert got == ("verA", "Sehr geehrte...", "l@x.de")
    # overwrite (new draft for same listing) replaces version
    dbm.put_draft(pg_conn, 7, "verB", "Neu...", None)
    assert dbm.get_draft(pg_conn, 7) == ("verB", "Neu...", None)
    popped = dbm.pop_draft(pg_conn, 7)
    assert popped == ("verB", "Neu...", None)
    assert dbm.get_draft(pg_conn, 7) is None

def test_appointment_store_roundtrip_and_pop(pg_conn):
    dbm.put_appointment(pg_conn, "tok1", {"when": "2026-07-24T15:30:00", "address": "X"}, "orig")
    ap, orig = dbm.get_appointment(pg_conn, "tok1")
    assert ap["address"] == "X" and orig == "orig"
    assert dbm.pop_appointment(pg_conn, "tok1")[0]["when"].startswith("2026-07-24")
    assert dbm.get_appointment(pg_conn, "tok1") is None

def test_bot_offset(pg_conn):
    assert dbm.get_offset(pg_conn) == 0
    dbm.set_offset(pg_conn, 12345)
    assert dbm.get_offset(pg_conn) == 12345
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Add to `db.py`:**

```python
def put_draft(conn, listing_id: int, version: str, text: str, email) -> None:
    conn.execute(
        "INSERT INTO pending_drafts (listing_id, version, draft_text, email, created_at) "
        "VALUES (%s,%s,%s,%s, now()) ON CONFLICT (listing_id) DO UPDATE SET "
        "version=EXCLUDED.version, draft_text=EXCLUDED.draft_text, email=EXCLUDED.email, "
        "created_at=now()", (listing_id, version, text, email))
    conn.commit()

def get_draft(conn, listing_id: int):
    row = conn.execute("SELECT version, draft_text, email FROM pending_drafts WHERE listing_id=%s",
                       (listing_id,)).fetchone()
    return (row["version"], row["draft_text"], row["email"]) if row else None

def pop_draft(conn, listing_id: int):
    row = conn.execute("DELETE FROM pending_drafts WHERE listing_id=%s "
                       "RETURNING version, draft_text, email", (listing_id,)).fetchone()
    conn.commit()
    return (row["version"], row["draft_text"], row["email"]) if row else None

def put_appointment(conn, token: str, appointment_dict: dict, orig_text: str) -> None:
    conn.execute(
        "INSERT INTO pending_appointments (token, appointment_json, orig_text, created_at) "
        "VALUES (%s,%s,%s, now()) ON CONFLICT (token) DO UPDATE SET "
        "appointment_json=EXCLUDED.appointment_json, orig_text=EXCLUDED.orig_text, created_at=now()",
        (token, Json(appointment_dict), orig_text))   # Json() adapts dict -> jsonb
    conn.commit()

def get_appointment(conn, token: str):
    row = conn.execute("SELECT appointment_json, orig_text FROM pending_appointments WHERE token=%s",
                       (token,)).fetchone()
    return (row["appointment_json"], row["orig_text"]) if row else None

def pop_appointment(conn, token: str):
    row = conn.execute("DELETE FROM pending_appointments WHERE token=%s "
                       "RETURNING appointment_json, orig_text", (token,)).fetchone()
    conn.commit()
    return (row["appointment_json"], row["orig_text"]) if row else None

def get_offset(conn) -> int:
    row = conn.execute("SELECT value FROM bot_state WHERE key='last_update_id'").fetchone()
    return int(row["value"]) if row else 0

def set_offset(conn, offset: int) -> None:
    conn.execute("INSERT INTO bot_state (key, value) VALUES ('last_update_id', %s) "
                 "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (str(offset),))
    conn.commit()
```

Note `appointment_json` is JSONB → psycopg returns it already as a Python dict on read (no manual `json.loads` needed).

- [ ] **Step 4: Run → PASS. Also run the WHOLE suite** `.venv\Scripts\python -m pytest -q` — the old SQLite `tests/test_db.py`/`test_dedup.py`/`test_pipeline.py`/`test_status_digest.py` will now FAIL (they call `dbm.connect(path)` with a sqlite path + `insert_if_new` etc against SQLite semantics). That's expected at this stage; they get reconciled in Task 8. Report the count of failures and confirm they're all DB-backend mismatches, not logic breaks.

- [ ] **Step 5: Commit** `git add -A; git commit -m "feat: postgres pending drafts/appointments + bot offset"`

---

### Task 6: Bot client wrapper (send / get_updates / answer)

**Files:**
- Create: `src/radar/botclient.py`
- Test: `tests/test_botclient.py`

Wraps `telegram.Bot` (async) with the small surface the cycle needs, plus a `Notifier` that satisfies the `pipeline.py` contract (`notify(listing_id, listing, result)` / `alert(text)`), replacing the old `TelegramNotifier`.

- [ ] **Step 1: Write failing tests** `tests/test_botclient.py`:

```python
from radar.botclient import Notifier
from radar.filters import FilterResult
from radar.models import Listing

def make():
    return Listing(source="immowelt", source_id="1", url="http://x", title="3-Zi",
                   district="Schleußig", rooms=3, area_m2=72, rent_cold=850)

async def test_notify_sends_card_with_keyboard(monkeypatch):
    sent = {}
    class FakeBot:
        async def send_message(self, **kw): sent.update(kw)
    n = Notifier(FakeBot(), chat_id="42", dry_run=False)
    await n.notify(7, make(), FilterResult(passed=True, unknown=["rent_warm"]))
    assert sent["chat_id"] == "42"
    assert "3-Zi" in sent["text"]
    assert sent["reply_markup"].inline_keyboard[0][0].callback_data == "draft:7"

async def test_dry_run_prints_not_sends(capsys):
    n = Notifier(object(), chat_id="42", dry_run=True)
    await n.notify(7, make(), FilterResult(passed=True))
    assert "[DRY-RUN" in capsys.readouterr().out

async def test_alert_sends_plain(monkeypatch):
    sent = {}
    class FakeBot:
        async def send_message(self, **kw): sent.update(kw)
    await Notifier(FakeBot(), chat_id="9", dry_run=False).alert("⚠️ x")
    assert sent["text"] == "⚠️ x" and "reply_markup" not in sent
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Implement `src/radar/botclient.py`:**

```python
import logging
from telegram import Bot
from .notify import build_card_text, build_keyboard

log = logging.getLogger("radar")

def make_bot(token: str) -> Bot:
    return Bot(token)

class Notifier:
    """Satisfies pipeline's notifier contract using a plain telegram.Bot."""
    def __init__(self, bot, chat_id: str, dry_run: bool = False):
        self.bot = bot
        self.chat_id = chat_id
        self.dry_run = dry_run

    async def notify(self, listing_id, listing, result) -> None:
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

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `git add -A; git commit -m "feat: bot client + Notifier"`

---

### Task 7: Extract framework-free handlers

**Files:**
- Create: `src/radar/handlers.py`
- Modify: `src/radar/main.py` (import the moved fns so local path still works), `src/radar/pipeline.py`
- Test: `tests/test_handlers.py`

Move the handler LOGIC out of `main.py` into `handlers.py` as plain async functions taking explicit deps + reading/writing pending state via `db`. These are the SAME functions the Plan-3 reviews hardened — port them to DB-backed pending state.

- [ ] **Step 1: Write failing tests** `tests/test_handlers.py` (uses `pg_conn` fixture + a fake bot + reuses `tests/test_draft.py::prof` and `tests/test_pipeline.py::crit`):

```python
from radar import db as dbm, handlers
from radar.models import Listing
from tests.test_draft import prof
from tests.test_pipeline import crit, FakeNotifier

class FakeBot:
    def __init__(self): self.sent = []
    async def send_message(self, **kw): self.sent.append(kw)
    async def answer_callback_query(self, **kw): pass

def seed_notified(conn, sid="1", rooms=3):
    l = Listing(source="immowelt", source_id=sid, url="https://x/expose/"+sid,
                title="3-Zimmer-Wohnung", district="Schleußig", rooms=rooms,
                area_m2=72, rent_cold=850)
    rid = dbm.insert_if_new(conn, l); dbm.set_status(conn, rid, "notified")
    return rid

async def test_draft_request_stores_and_sends(pg_conn):
    rid = seed_notified(pg_conn); bot = FakeBot()
    await handlers.handle_draft_request(rid, pg_conn, prof(), bot, chat_id="42", email_finder=None)
    assert any("3-Zimmer-Wohnung" in m["text"] and "Andriy Leso" in m["text"] for m in bot.sent)
    stored = dbm.get_draft(pg_conn, rid)
    assert stored is not None                 # (version, draft_text, email) persisted for the send button
    assert stored[0]                          # version token present

async def test_applied_sets_status(pg_conn):
    rid = seed_notified(pg_conn); bot = FakeBot()
    await handlers.handle_applied(rid, pg_conn, bot, chat_id="42")
    assert dbm.get_listing(pg_conn, rid)["status"] == "applied"

async def test_send_email_stale_version(pg_conn):
    rid = seed_notified(pg_conn); bot = FakeBot()
    dbm.put_draft(pg_conn, rid, "curV", "text", "l@x.de")
    await handlers.handle_send_email(rid, "OLDV", pg_conn, mailer=None, bot=bot, chat_id="42")
    assert any("застаріл" in m["text"].lower() for m in bot.sent)

async def test_forward_appointment_stores_confirm(pg_conn):
    bot = FakeBot()
    await handlers.handle_forward(
        "Besichtigung am 24.07.2026 um 15:30, Karl-Heine-Str. 12",
        pg_conn, crit(), FakeNotifier(), bot, chat_id="42")
    # a pending appointment row was created and a confirm card sent
    assert any("cal:" in str(m.get("reply_markup")) for m in bot.sent)
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Implement `src/radar/handlers.py`** — port each Plan-3 handler, swapping the in-memory dicts for `db` calls and taking `bot`+`chat_id` instead of PTB `update/context`. Signatures:
  - `async def handle_draft_request(row_id, conn, profile, bot, chat_id, email_finder)` — `get_listing`→`listing_from_row`; `build_application` via `asyncio.to_thread`; resolve email; `version = secrets.token_hex(4)`; `db.put_draft(conn,row_id,version,text,email)`; send draft message with `notify.draft_actions_keyboard(row_id, email, version)`; append the placeholder-phone warning (`re.search(r"X{2,}", profile.phone)`).
  - `async def handle_applied(row_id, conn, bot, chat_id)` — `set_status(conn,row_id,"applied")` + confirm send.
  - `async def handle_send_email(row_id, version, conn, mailer, bot, chat_id)` — `db.get_draft`; missing/version-mismatch → stale reply; mailer None → "email не налаштовано"; else `db.pop_draft` (in-flight), subject `"Bewerbung: " + " ".join(title.split())`, `await mailer.send(...)`; success → `set_status applied`; failure → `db.put_draft(...)` restore + generic apology.
  - `async def handle_forward(text, conn, criteria, notifier, bot, chat_id)` — try `parse_appointment(text)`; if found → `token=secrets.token_hex(4)`; `db.put_appointment(conn, token, {"when": ap.when.isoformat(), "address": ap.address, "raw": ap.raw}, text)`; send confirm card with `cal:<token>`/`callisting:<token>` buttons; else `_handle_forward_listing(...)`.
  - `async def _handle_forward_listing(text, conn, criteria, notifier, bot, chat_id)` — the Plan-3 listing-intake body (sha1 source_id, insert_if_new, evaluate, dedup, notify, replies).
  - `async def handle_calendar_confirm(token, conn, calendar, notifier, bot, chat_id)` — `db.get_appointment` (missing → stale); calendar None → restore is unnecessary since get didn't pop — reply "не підключено"; else pop, rebuild `Appointment(datetime.fromisoformat(d["when"]), d["address"], d["raw"])`, `link_appointment`, `build_event`, `calendar.insert`; failure → `db.put_appointment` restore + generic reply.
  - `async def handle_listing_confirm(token, conn, criteria, notifier, bot, chat_id)` — `db.pop_appointment` → `_handle_forward_listing(orig_text, ...)`.
  - `async def handle_status(conn, bot, chat_id)` — `report.build_status_text(db.status_counts(conn))` send.
  - `def link_appointment(conn, appointment)` — unchanged logic (uses `listings_by_status(conn,"applied")`, full STREET_RE, threshold 80).
  - Replies go via `bot.send_message(chat_id=chat_id, text=...)`.

  Update `main.py` to import these from `handlers` (so the local daemon path, if kept, still wires them) OR mark main.py cloud-obsolete (Task 9). `pipeline.py`: it already takes a notifier; no pending-dict dependency there — confirm `_finalize`/`retry_pending` don't touch in-memory pending (they don't). No pipeline change needed beyond using `botclient.Notifier`.

- [ ] **Step 4: Run test_handlers → PASS.** **Step 5: Commit** `git add -A; git commit -m "feat: framework-free db-backed handlers"`

---

### Task 8: Reconcile old SQLite tests + pipeline to Postgres

**Files:**
- Modify: `tests/test_db.py`, `tests/test_dedup.py`, `tests/test_pipeline.py`, `tests/test_status_digest.py`, `tests/test_bot_flows.py`, `tests/test_geo.py` (only DB-touching parts), `tests/conftest.py`
- Delete: `tests/test_main_startup.py` (APScheduler/PTB-Application specific — obsolete in cloud), `tests/test_tg_groups.py` (Telethon dropped)

- [ ] **Step 1: Point DB-backed tests at Postgres.** The pure-parser tests (`test_immowelt`, `test_kleinanzeigen`, `test_wogetra`, `test_bgl`, `test_vlw`, `test_sources_common`, `test_filters`, `test_draft`, `test_appointment`, `test_calendar_api`, `test_config`, `test_msgparse`, `test_notify`, `test_contact`, `test_mailer`, `test_report` non-DB) need NO change. For DB-backed tests: replace `dbm.connect(str(tmp_path/"t.db"))` with the `pg_conn` fixture (add `pg_conn` param, drop the tmp_path connect line). `test_dedup.py`/`test_pipeline.py`/`test_status_digest.py`/`test_bot_flows.py` all follow this pattern. For `test_bot_flows.py`: the handlers moved to `handlers.py` and are DB-backed now — update imports (`from radar import handlers`) and pending assertions to use `db.get_draft`/`get_appointment` instead of the old `bot_data` dicts; convert the fake `send`/`FakeMsg` to the `FakeBot` shape from Task 7. This is the largest reconciliation — do it test-by-test, running each file green before moving on.

- [ ] **Step 2: Delete obsolete tests** — `git rm tests/test_main_startup.py tests/test_tg_groups.py`. Rationale (record in DECISIONS): the supervised-restart + Telethon reader are not part of the cloud architecture.

- [ ] **Step 3: Run the WHOLE suite** `.venv\Scripts\python -m pytest -q`. Iterate until green. Report the final count (expect ~250-260 after deletions + PG conversions). Every remaining failure must be fixed, not skipped.

- [ ] **Step 4: Commit** `git add -A; git commit -m "test: reconcile db-backed tests to postgres; drop daemon-only tests"`

---

### Task 9: dispatch_update + cycle entrypoint

**Files:**
- Create: `src/radar/dispatch.py`, `src/radar/cycle.py`
- Modify: `src/radar/main.py` (delete or reduce), `pyproject.toml` (drop apscheduler/telethon from runtime deps)
- Test: `tests/test_dispatch.py`, `tests/test_cycle.py`

- [ ] **Step 1: Write failing dispatch tests** `tests/test_dispatch.py`:

```python
from types import SimpleNamespace
from radar import db as dbm, dispatch
from tests.test_draft import prof
from tests.test_pipeline import crit, FakeNotifier
from tests.test_handlers import FakeBot, seed_notified

def deps(conn, bot):
    return dispatch.Deps(conn=conn, criteria=crit(), notifier=FakeNotifier(), bot=bot,
                         chat_id="42", profile=prof(), mailer=None, calendar=None,
                         email_finder=None)

def cb_update(data, chat_id="42", uid=100):
    return SimpleNamespace(update_id=uid, callback_query=SimpleNamespace(
        data=data, id="cbid", message=SimpleNamespace(chat=SimpleNamespace(id=int(chat_id)))),
        message=None)

def msg_update(text, chat_id="42", uid=101):
    return SimpleNamespace(update_id=uid, callback_query=None,
        message=SimpleNamespace(text=text, chat=SimpleNamespace(id=int(chat_id))))

async def test_skip_callback_sets_skipped(pg_conn):
    rid = seed_notified(pg_conn); bot = FakeBot()
    await dispatch.dispatch_update(cb_update(f"skip:{rid}"), deps(pg_conn, bot))
    assert dbm.get_listing(pg_conn, rid)["status"] == "skipped"

async def test_non_owner_ignored(pg_conn):
    rid = seed_notified(pg_conn); bot = FakeBot()
    await dispatch.dispatch_update(cb_update(f"skip:{rid}", chat_id="999"), deps(pg_conn, bot))
    assert dbm.get_listing(pg_conn, rid)["status"] == "notified"  # untouched

async def test_status_command(pg_conn):
    bot = FakeBot()
    await dispatch.dispatch_update(msg_update("/status"), deps(pg_conn, bot))
    assert any("Стан" in m["text"] for m in bot.sent)

async def test_forward_text_routes_to_handler(pg_conn):
    bot = FakeBot()
    await dispatch.dispatch_update(msg_update("Дякую всім!"), deps(pg_conn, bot))
    assert any("не розпізнав" in m["text"].lower() for m in bot.sent)
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Implement `src/radar/dispatch.py`:**

```python
import logging
from dataclasses import dataclass
from . import db as dbm, handlers

log = logging.getLogger("radar")

@dataclass
class Deps:
    conn: object
    criteria: object
    notifier: object
    bot: object
    chat_id: str
    profile: object
    mailer: object
    calendar: object
    email_finder: object

def _is_owner(chat_id_val, owner: str) -> bool:
    return chat_id_val is not None and str(chat_id_val) == str(owner)

async def dispatch_update(update, d: Deps) -> None:
    try:
        cq = getattr(update, "callback_query", None)
        msg = getattr(update, "message", None)
        if cq is not None:
            chat = cq.message.chat.id if cq.message else None
            if not _is_owner(chat, d.chat_id):
                return
            data = cq.data or ""
            try:
                await d.bot.answer_callback_query(callback_query_id=cq.id)
            except Exception:
                pass
            if data.startswith("skip:"):
                dbm.set_status(d.conn, int(data.split(":")[1]), "skipped")
            elif data.startswith("draft:"):
                await handlers.handle_draft_request(int(data.split(":")[1]), d.conn, d.profile,
                                                    d.bot, d.chat_id, d.email_finder)
            elif data.startswith("applied:"):
                await handlers.handle_applied(int(data.split(":")[1]), d.conn, d.bot, d.chat_id)
            elif data.startswith("send_email:"):
                _, rid, ver = data.split(":", 2)
                await handlers.handle_send_email(int(rid), ver, d.conn, d.mailer, d.bot, d.chat_id)
            elif data.startswith("cal:"):
                await handlers.handle_calendar_confirm(data.split(":",1)[1], d.conn, d.calendar,
                                                       d.notifier, d.bot, d.chat_id)
            elif data.startswith("callisting:"):
                await handlers.handle_listing_confirm(data.split(":",1)[1], d.conn, d.criteria,
                                                      d.notifier, d.bot, d.chat_id)
        elif msg is not None and getattr(msg, "text", None):
            if not _is_owner(msg.chat.id, d.chat_id):
                return
            if msg.text.strip() == "/status":
                await handlers.handle_status(d.conn, d.bot, d.chat_id)
            else:
                await handlers.handle_forward(msg.text, d.conn, d.criteria, d.notifier,
                                              d.bot, d.chat_id)
    except Exception:
        log.warning("dispatch failed for update", exc_info=True)
```

- [ ] **Step 4: Run dispatch tests → PASS.** **Step 5: Write failing cycle test** `tests/test_cycle.py`:

```python
from radar import db as dbm, cycle
from tests.test_handlers import FakeBot

async def test_drain_updates_advances_offset(pg_conn):
    from types import SimpleNamespace
    bot = FakeBot()
    updates = [SimpleNamespace(update_id=5, callback_query=None,
               message=SimpleNamespace(text="/status", chat=SimpleNamespace(id=42)))]
    async def fake_get_updates(offset, timeout): return updates
    bot.get_updates = fake_get_updates
    from tests.test_dispatch import deps
    await cycle.drain_updates(bot, deps(pg_conn, bot))
    assert dbm.get_offset(pg_conn) == 6  # last update_id + 1
```

- [ ] **Step 6: Run → FAIL.** **Step 7: Implement `src/radar/cycle.py`:**

```python
import argparse
import asyncio
import logging
import os
from pathlib import Path
from . import db as dbm
from .botclient import make_bot, Notifier
from .config import load_criteria
from .profile import load_profile
from .contact import EmailFinder
from .dispatch import Deps, dispatch_update
from .geo import build_geo_checker
from .mailer import GmailMailer
from .calendar_api import CalendarClient
from .pipeline import Pipeline
from .report import build_digest_text
from .sources.registry import build_sources

log = logging.getLogger("radar")
ROOT = Path(__file__).resolve().parents[2]

def _build_deps(conn, bot, criteria, dry_run):
    profile = None
    try:
        profile = load_profile(ROOT / "config" / "profile.yaml")
    except SystemExit:
        log.warning("profile.yaml missing — draft flow limited")
    mailer = GmailMailer.from_env()
    calendar = None
    token = os.getenv("GOOGLE_CALENDAR_TOKEN")
    if token:
        p = ROOT / "token.json"
        p.write_text(token, encoding="utf-8")
        calendar = CalendarClient.from_token(p)
    return Deps(conn=conn, criteria=criteria,
                notifier=Notifier(bot, os.environ["TELEGRAM_CHAT_ID"], dry_run=dry_run),
                bot=bot, chat_id=os.environ["TELEGRAM_CHAT_ID"], profile=profile,
                mailer=mailer, calendar=calendar, email_finder=EmailFinder())

async def drain_updates(bot, d: Deps) -> None:
    offset = dbm.get_offset(d.conn)
    updates = await bot.get_updates(offset=offset + 1 if offset else 0, timeout=0)
    for u in updates:
        await dispatch_update(u, d)
        dbm.set_offset(d.conn, u.update_id + 1)

async def run_cycle(digest: bool = False, dry_run: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    conn = dbm.connect(os.environ["DATABASE_URL"])
    criteria = load_criteria(ROOT / "config" / "criteria.yaml")
    bot = make_bot(os.environ["TELEGRAM_BOT_TOKEN"])
    d = _build_deps(conn, bot, criteria, dry_run)
    if digest:
        text = build_digest_text(conn)
        if text:
            try:
                await d.notifier.alert(text)
            except Exception:
                log.warning("digest send failed", exc_info=True)
        return
    pipeline = Pipeline(conn, criteria, d.notifier,
                        geo=build_geo_checker(criteria, cache=dbm.DbCache(conn)),
                        notify_cap=criteria.max_notifies_per_cycle)
    pipeline.retry_pending()  # NOTE: retry_pending is async? see step 8
    for source, _minutes in build_sources(criteria):
        await pipeline.run_source(source)
    await drain_updates(bot, d)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(run_cycle(digest=args.digest, dry_run=args.dry_run))

if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Fix the `retry_pending` await** — check its signature in `pipeline.py`; it is `async`, so change the cycle line to `await pipeline.retry_pending()`. Run `.venv\Scripts\python -c "import radar.cycle"` to confirm imports. Also drop `apscheduler` and `telethon` from `pyproject.toml` runtime deps (they're no longer imported by the cloud path; `main.py` if kept still imports apscheduler — either delete `main.py` or guard its import. Decision: DELETE `src/radar/main.py` and `run-radar.cmd`/`WohnungRadar.vbs` are local-only, leave them but note they're unused in cloud). If deleting main.py, ensure nothing else imports it (`grep`).

- [ ] **Step 9: Run cycle test + whole suite → PASS.** **Step 10: Commit** `git add -A; git commit -m "feat: dispatch_update + stateless cycle entrypoint"`

---

### Task 10: GitHub Actions workflows + secrets wiring

**Files:**
- Create: `.github/workflows/poll.yml`, `.github/workflows/digest.yml`
- Modify: `.env.example`, `.gitignore`
- Test: manual (workflow YAML lint via `python -c` yaml parse)

- [ ] **Step 1: Create `.github/workflows/poll.yml`:**

```yaml
name: poll
on:
  schedule:
    - cron: "*/30 * * * *"   # every 30 min (UTC); GitHub cron is best-effort
  workflow_dispatch: {}       # manual trigger button
concurrency:
  group: radar-cycle          # never overlap two cycles
  cancel-in-progress: false
jobs:
  cycle:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - run: python -m radar.cycle
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GOOGLE_ROUTES_API_KEY: ${{ secrets.GOOGLE_ROUTES_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          GOOGLE_CALENDAR_TOKEN: ${{ secrets.GOOGLE_CALENDAR_TOKEN }}
```

- [ ] **Step 2: Create `.github/workflows/digest.yml`** (identical env block, different schedule + flag):

```yaml
name: digest
on:
  schedule:
    - cron: "0 18 * * *"      # ~20:00 Europe/Berlin (DST-approximate)
  workflow_dispatch: {}
jobs:
  digest:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - run: python -m radar.cycle --digest
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

- [ ] **Step 3: Update `.env.example`** — add `DATABASE_URL=` and `GOOGLE_CALENDAR_TOKEN=` lines (keep existing keys). Confirm `.gitignore` still excludes `.env`, `token.json`, `client_secret.json`, `config/profile.yaml`, `*.session`.

- [ ] **Step 4: Validate YAML** — `.venv\Scripts\python -c "import yaml; yaml.safe_load(open('.github/workflows/poll.yml')); yaml.safe_load(open('.github/workflows/digest.yml')); print('yaml ok')"`. Expected: `yaml ok`.

- [ ] **Step 5: Commit** `git add -A; git commit -m "ci: github actions poll + digest workflows"`

---

### Task 11: Local dry-run against real sources + test DB

- [ ] **Step 1: Dry-run the full cycle** without sending Telegram: set env in the shell — `DATABASE_URL` = the local test Postgres DSN (`postgresql://postgres:radar@localhost:55432/radar_test`), `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` = the real values from `.env`, `GOOGLE_ROUTES_API_KEY`/`ANTHROPIC_API_KEY` from `.env` — then run `.venv\Scripts\python -m radar.cycle --dry-run`. Expected: all 5 sources fetch, `[DRY-RUN notify]` cards print for any new matches, geo runs (Routes calls), `drain_updates` pulls any pending taps (harmless), no traceback. Record per-source counts + status Counter via a follow-up `psql`/python query against the test DB.

- [ ] **Step 2: Verify graceful-off** — with `GMAIL_*`/`GOOGLE_CALENDAR_TOKEN` unset: mailer None, calendar None, no crash (log lines / silent). Confirm.

- [ ] **Step 3: Run whole suite once more** → green (report count). No commit (verification only).

---

### Task 12: Docs + cutover runbook

**Files:**
- Modify: `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`

- [ ] **Step 1: README** — replace the local-autostart section with a **Cloud (GitHub Actions + Supabase) runbook**:
  1. Create a Supabase project → copy the **session pooler** connection string; substitute the real DB password → this is `DATABASE_URL`.
  2. Create a **private** GitHub repo; `git remote add origin <url>`; `git push -u origin master`.
  3. Repo → Settings → Secrets and variables → Actions → add: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_ROUTES_API_KEY`, `ANTHROPIC_API_KEY`, and optionally `GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD`/`GOOGLE_CALENDAR_TOKEN` (the contents of `token.json`).
  4. Actions tab → enable workflows → run `poll` once via **Run workflow** to smoke-test; watch the run log; confirm a card arrives in Telegram.
  5. Cadence note: `poll` every 30 min, `digest` daily ~20:00 Berlin; button taps process on the next `poll` (≤30 min latency).
  6. `config/profile.yaml` is gitignored → for cloud, put its contents in a `PROFILE_YAML` secret is NOT wired in this plan; instead the committed `config/profile.example.yaml` (placeholder, non-PII) is what the cloud reads unless the user commits a real `profile.yaml` (they should NOT in a repo). **Document the limitation:** application drafts in cloud use the example profile until the user decides how to inject real profile data — flag as the one follow-up.
- [ ] **Step 2: ARCHITECTURE.md** — new stateless-cycle diagram (cron → cycle → poll+drain), Postgres data model, the retired daemon/APScheduler/Telethon pieces noted as local-only history.
- [ ] **Step 3: DECISIONS.md** — cloud-migration entry: SQLite→Postgres, in-memory→DB pending state, Application-polling→getUpdates-drain, 30-min cron latency accepted, Telethon dropped, historical rows not migrated, profile-in-cloud open follow-up.
- [ ] **Step 4: Commit** `git add -A; git commit -m "docs: cloud migration runbook + architecture"`

---

## Follow-ups (not in this plan)

- **Profile data in cloud:** wire a `PROFILE_YAML` secret → written to `config/profile.yaml` at cycle start (mirrors the `GOOGLE_CALENDAR_TOKEN` pattern) so real tenant data isn't committed. Small, do right after cutover if the user wants live applications.
- **Telethon TG-groups:** needs an always-on host (Oracle Free VM) — separate project.
- **DST-exact digest time:** GitHub cron is UTC-only; 18:00 UTC drifts ±1h vs Berlin across DST. Acceptable; revisit only if it matters.
