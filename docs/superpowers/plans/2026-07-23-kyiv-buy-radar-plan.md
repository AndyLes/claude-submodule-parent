# Kyiv Buy Radar (Multi-Market Extension) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second market to the live wohnung-radar — buy 2-room Kyiv apartments ≤$70k, Obolon preferred — alerting a separate Telegram bot/channel, reusing the cloud engine, with the Leipzig market unchanged.

**Architecture:** `radar.cycle` gains `--market {leipzig,kyiv}` (default leipzig). A per-market config bundle (`config/markets/*.yaml`) declares mode (rent/buy), sources, criteria, and bot-credential env-var names. DB `listings` rows are tagged with a `market` column (default 'leipzig') and every listing query is market-scoped; the bot getUpdates offset is keyed per market. Buy-mode is monitoring-only (no geo/applications/calendar). Three new Kyiv adapters (OLX, DIM.RIA, flatfy) built fixture-first from recon-verified markup.

**Tech Stack:** Python 3.12, psycopg/Postgres (Supabase), python-telegram-bot (Bot only), GitHub Actions, pytest. Tests hit Supabase `radar_test` schema via the existing `pg_conn` fixture.

**Repo/spec:** `C:\SuperWork\projects\wohnung-radar\` (own git, master). Spec: `docs/superpowers/specs/2026-07-23-kyiv-buy-radar-design.md`. The full existing suite (285) must stay green throughout — Leipzig behavior is preserved by market-defaulting + mode-gating.

**Recon facts (2026-07-23, verified live — the fixture is still authority at build time):**
- **OLX**: `https://www.olx.ua/uk/nedvizhimost/kvartiry/prodazha-kvartir/2-kmnati/kiev/?search[filter_float_price:to]=70000&currency=USD` → HTTP 200, server-rendered React (NOT Next.js, no `__NEXT_DATA__`). Clean per-listing `<script type="application/ld+json">` `Offer` blocks: `name`(title), `price`, `priceCurrency`("USD"), `url`, `image`, `areaServed.name`(district). Obolon filter `&search[district_id]=9`. ID from url `-ID<x>.html`. No anti-bot. USD.
- **DIM.RIA**: `https://dom.ria.com/prodazha-kvartir/kiev-2k-rayon-obolonskyi/` → HTTP 200, server-rendered legacy HTML cards (no JSON blob). Price/rooms/district in the slug; **price NOT filterable via URL → post-filter ≤$70k in code**. Per-card: price `NN NNN $`, url/id `...-<numeric-id>.html`, breadcrumb district ("Оболонь · … · Оболонский · Киев"), rooms "2 комнаты", area "45.9 м²". No anti-bot. USD.
- **flatfy.ua**: `https://flatfy.ua/uk/продаж-квартир-київ-оболонський-район-двокімнатні?price_max=70000` → HTTP 200, SSR React; one `<script type="application/ld+json">` `["ItemList","RealEstateListing"]`, `JSON.parse`-able. Per-item: `name`(address), `room_count`, `price`, `offers.priceCurrency`("USD"), `insert_time`, `images`, internal numeric `id`, `site.internal_name`(source portal). `price_max` + `&page=N` work. Cloudflare present, no challenge on single requests. NOTE: no per-listing `<a href>` in HTML (client-side routing) → derive url from the numeric id at fixture time or fall back to the filtered search URL.
- **Skipped (documented in DECISIONS at KB-12):** lun.ua (same backend as flatfy, Next.js RSC — redundant + harder), rieltor.ua (429 rate-limit that silently serves stale content; already aggregated by flatfy).

**Market-scoping scope (deliberately minimal to protect live Leipzig):** ONLY the `listings` table gets a `market` column; the bot offset is namespaced by a `{market}:last_update_id` key in the existing `bot_state` table (no PK change). `geocode_cache`, `pending_drafts`, `pending_appointments` stay Leipzig/rent-only (buy-mode never touches geo/applications) — untouched. Source names are disjoint across markets, so the `UNIQUE (source, source_id)` constraint needs no change.

**File map:**
```
src/radar/models.py               # KB-1: +price, +currency on Listing
src/radar/db.py                   # KB-2: market column + market-scoped queries + offset key
src/radar/config.py               # KB-3: Market bundle + load_market()
config/markets/leipzig.yaml       # KB-3: current leipzig criteria+sources+mode:rent (migrated)
config/markets/kyiv.yaml          # KB-3: kyiv buy config
src/radar/filters.py              # KB-4: buy-mode evaluate branch
src/radar/notify.py               # KB-5: buy-mode card + skip-only keyboard
src/radar/sources/ua_common.py    # KB-6: UA num/currency/district/json-ld helpers
src/radar/sources/olx.py          # KB-7
src/radar/sources/domria.py       # KB-8
src/radar/sources/flatfy.py       # KB-9
src/radar/sources/registry.py     # KB-10: +olx/domria/flatfy factories
src/radar/pipeline.py             # KB-2/KB-11: market threaded to db calls
src/radar/cycle.py                # KB-11: --market, per-market bot creds, mode-gating
src/radar/dispatch.py             # KB-11: Deps.market
.github/workflows/poll-kyiv.yml   # KB-12
tests/... , docs/...
```

---

### KB-1: Listing gains price + currency (buy-mode fields)

**Files:** Modify `src/radar/models.py`; Test `tests/test_models_price.py`

- [ ] **Step 1: failing test** `tests/test_models_price.py`:

```python
from radar.models import Listing

def test_listing_has_price_currency_defaults():
    l = Listing(source="olx", source_id="1", url="u", title="t")
    assert l.price is None and l.currency is None

def test_listing_price_set():
    l = Listing(source="olx", source_id="1", url="u", title="t", price=68000, currency="USD")
    assert l.price == 68000 and l.currency == "USD"
```

- [ ] **Step 2: run → FAIL** (`unexpected keyword 'price'`). `.venv\Scripts\python -m pytest tests/test_models_price.py -v`

- [ ] **Step 3: implement** — in `src/radar/models.py`, add to the `Listing` dataclass AFTER `rent_cold` (keep all existing fields/order):

```python
    price: float | None = None       # buy-mode sale price (in `currency`)
    currency: str | None = None      # e.g. "USD", "UAH"
```

- [ ] **Step 4: run → PASS. Whole suite must stay green** (`asdict`/`listing_from_row` tolerate new optional fields — verify `tests/test_db_pg.py` still green: the payload_json round-trip carries them; `listing_from_row` won't set them yet — that's fine, they default None). Report count.
- [ ] **Step 5: commit** `git add -A; git commit -m "feat: Listing price/currency fields for buy-mode"`

---

### KB-2: DB market column + market-scoped queries

**Files:** Modify `src/radar/db.py`, `src/radar/pipeline.py`; Test `tests/test_db_market.py`

Every listing query gains a `market: str = "leipzig"` parameter (default preserves Leipzig callers). The offset is namespaced per market. `insert_if_new` writes the market.

- [ ] **Step 1: failing tests** `tests/test_db_market.py`:

```python
from radar import db as dbm
from radar.models import Listing

def mk(sid, market_src="olx"):
    return Listing(source=market_src, source_id=sid, url="u"+sid, title="T"+sid,
                   district="Оболонь", price=68000, currency="USD")

def test_insert_and_recent_scoped_by_market(pg_conn):
    dbm.insert_if_new(pg_conn, mk("k1"), market="kyiv")
    dbm.insert_if_new(pg_conn, Listing(source="kleinanzeigen", source_id="l1",
                                       url="u", title="L", rent_warm=900), market="leipzig")
    kyiv = dbm.recent_listings(pg_conn, market="kyiv")
    leip = dbm.recent_listings(pg_conn, market="leipzig")
    assert [r["source_id"] for r in kyiv] == ["k1"]
    assert [r["source_id"] for r in leip] == ["l1"]

def test_market_defaults_to_leipzig(pg_conn):
    dbm.insert_if_new(pg_conn, Listing(source="kleinanzeigen", source_id="d1",
                                       url="u", title="L", rent_warm=900))
    assert [r["source_id"] for r in dbm.recent_listings(pg_conn)] == ["d1"]  # default leipzig
    assert dbm.recent_listings(pg_conn, market="kyiv") == []

def test_status_counts_and_pending_scoped(pg_conn):
    a = dbm.insert_if_new(pg_conn, mk("k2"), market="kyiv")
    dbm.set_status(pg_conn, a, "notified")
    dbm.insert_if_new(pg_conn, mk("k3"), market="kyiv")   # stays 'new'
    assert dbm.status_counts(pg_conn, market="kyiv") == {"notified": 1, "new": 1}
    assert {r["source_id"] for r in dbm.pending_listings(pg_conn, market="kyiv")} == {"k3"}
    assert dbm.status_counts(pg_conn, market="leipzig") == {}

def test_offset_namespaced_per_market(pg_conn):
    dbm.set_offset(pg_conn, 100, market="leipzig")
    dbm.set_offset(pg_conn, 200, market="kyiv")
    assert dbm.get_offset(pg_conn, market="leipzig") == 100
    assert dbm.get_offset(pg_conn, market="kyiv") == 200
    assert dbm.get_offset(pg_conn) == 100  # default leipzig
```

- [ ] **Step 2: run → FAIL** (`insert_if_new` has no market param; no market column).

- [ ] **Step 3: implement** in `src/radar/db.py`:

Add to `SCHEMA` `listings` table a `market TEXT NOT NULL DEFAULT 'leipzig'` column (after `status`). Add an idempotent migration in `connect()` after `conn.execute(SCHEMA)`:

```python
    conn.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'leipzig'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_market ON listings (market)")
```

`insert_if_new` gains `market` and writes it:

```python
def insert_if_new(conn, listing, market: str = "leipzig") -> int | None:
    payload = json.dumps(asdict(listing), default=str, ensure_ascii=False)
    try:
        row = conn.execute(
            "INSERT INTO listings (source, source_id, url, title, district,"
            " rooms, area_m2, rent_warm, rent_cold, payload_json, market)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (source, source_id) DO NOTHING RETURNING id",
            (listing.source, listing.source_id, listing.url, listing.title,
             listing.district, listing.rooms, listing.area_m2, listing.rent_warm,
             listing.rent_cold, payload, market)).fetchone()
    except psycopg.errors.NotNullViolation:
        raise
    return row["id"] if row else None
```

Add `market: str = "leipzig"` + a `WHERE market=%s` predicate to each of: `recent_listings`, `listings_by_status`, `pending_listings`, `status_counts`, `recent_notified`. Examples:

```python
def recent_listings(conn, market: str = "leipzig", limit: int = 200):
    return conn.execute("SELECT * FROM listings WHERE market=%s ORDER BY id DESC LIMIT %s",
                        (market, limit)).fetchall()

def listings_by_status(conn, status: str, market: str = "leipzig", limit: int = 50):
    return conn.execute("SELECT * FROM listings WHERE market=%s AND status=%s "
                        "ORDER BY id DESC LIMIT %s", (market, status, limit)).fetchall()

def pending_listings(conn, market: str = "leipzig"):
    return conn.execute("SELECT * FROM listings WHERE market=%s AND status IN ('new','notify_failed') "
                        "ORDER BY id ASC", (market,)).fetchall()

def status_counts(conn, market: str = "leipzig") -> dict:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM listings WHERE market=%s GROUP BY status",
                        (market,)).fetchall()
    return {r["status"]: r["n"] for r in rows}

def recent_notified(conn, market: str = "leipzig", since_hours: int = 24):
    return conn.execute(
        "SELECT * FROM listings WHERE market=%s AND status IN ('notified','applied','viewing_scheduled') "
        "AND created_at >= now() - make_interval(hours => %s) "
        "ORDER BY created_at DESC, id DESC", (market, since_hours)).fetchall()
```

`get_offset`/`set_offset` namespace by market via the key:

```python
def get_offset(conn, market: str = "leipzig") -> int:
    row = conn.execute("SELECT value FROM bot_state WHERE key=%s",
                       (f"{market}:last_update_id",)).fetchone()
    return int(row["value"]) if row else 0

def set_offset(conn, offset: int, market: str = "leipzig") -> None:
    conn.execute("INSERT INTO bot_state (key, value) VALUES (%s, %s) "
                 "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                 (f"{market}:last_update_id", str(offset)))
```

(`list_by_status` KEEP the existing param order the callers use — `handlers.link_appointment` calls `listings_by_status(conn, "applied")`; adding `market` as the 2nd positional with default keeps that call valid since it passes status positionally and market defaults. Verify.)

`pipeline.py`: `Pipeline.__init__` gains `market: str = "leipzig"`; store `self.market`; pass it to every db call inside `run_source`/`retry_pending`/`_finalize` (`recent_listings(self.conn, market=self.market)`, `insert_if_new(self.conn, listing, market=self.market)`, `pending_listings(self.conn, market=self.market)`, `set_status` needs no market — id is unique).

- [ ] **Step 4: run test_db_market → PASS. Whole suite → GREEN** (Leipzig defaults preserve all existing tests; verify test_pipeline/test_status_digest still pass — they call the defaulted functions). Report count.
- [ ] **Step 5: commit** `git add -A; git commit -m "feat: market-scoped listings + per-market bot offset"`

---

### KB-3: Market config bundles + loader

**Files:** Create `config/markets/leipzig.yaml`, `config/markets/kyiv.yaml`; Modify `src/radar/config.py`; Test `tests/test_market_config.py`

The `Market` bundle wraps the existing `Criteria` plus mode + bot env-var names + sources. Leipzig's current `config/criteria.yaml` content migrates into `markets/leipzig.yaml` (criteria.yaml stays for back-compat but the cycle reads the market file).

- [ ] **Step 1: failing test** `tests/test_market_config.py`:

```python
from pathlib import Path
from radar.config import load_market

ROOT = Path(__file__).parents[1]

def test_leipzig_market_rent():
    m = load_market("leipzig", ROOT / "config" / "markets")
    assert m.mode == "rent"
    assert m.bot_token_env == "TELEGRAM_BOT_TOKEN"
    assert m.criteria.min_rooms == 3
    assert "kleinanzeigen" in m.sources

def test_kyiv_market_buy():
    m = load_market("kyiv", ROOT / "config" / "markets")
    assert m.mode == "buy"
    assert m.bot_token_env == "KYIV_TELEGRAM_BOT_TOKEN"
    assert m.chat_id_env == "KYIV_TELEGRAM_CHAT_ID"
    assert m.criteria.mode == "buy"
    assert m.criteria.max_price_usd == 70000
    assert m.criteria.rooms_exact == 2
    assert "Оболонь" in m.criteria.preferred_districts
    assert set(m.sources) == {"olx", "domria", "flatfy"}
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement**

`config.py` — extend `Criteria` with buy-mode fields (all optional, defaulting so rent Criteria is unaffected):

```python
@dataclass
class Criteria:
    min_rooms: float
    min_area_m2: float
    max_rent_warm: float
    required_features: list
    district_whitelist: list
    max_travel_min: int
    sources: dict = None
    feature_keywords: dict = None
    plz_districts: dict = None
    school_address: str = ""
    telegram_groups: list = None
    kleinanzeigen_search_url: str = ""
    max_notifies_per_cycle: int = 10
    # buy-mode (kyiv)
    mode: str = "rent"
    max_price_usd: float = 0
    rooms_exact: int = 0
    uah_per_usd: float = 41.5
    preferred_districts: list = None
```

Add `Market` + `load_market`:

```python
@dataclass
class Market:
    name: str
    mode: str
    bot_token_env: str
    chat_id_env: str
    sources: dict
    criteria: Criteria

def load_market(name: str, markets_dir) -> Market:
    from pathlib import Path
    with open(Path(markets_dir) / f"{name}.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    crit_data = dict(data.get("criteria", {}))
    crit_data["sources"] = data["sources"]
    criteria = Criteria(**crit_data)
    return Market(name=name, mode=data["mode"],
                  bot_token_env=data["bot_token_env"], chat_id_env=data["chat_id_env"],
                  sources=data["sources"], criteria=criteria)
```

`config/markets/leipzig.yaml` — mirror the CURRENT `config/criteria.yaml` under a `criteria:` block + the sources + envs (copy the live criteria.yaml values verbatim so Leipzig is identical):

```yaml
mode: rent
bot_token_env: TELEGRAM_BOT_TOKEN
chat_id_env: TELEGRAM_CHAT_ID
criteria:
  min_rooms: 3
  min_area_m2: 60
  max_rent_warm: 1000
  required_features: [kitchen, shower]
  district_whitelist: [Schleußig, Plagwitz, Lindenau, Altlindenau, Südvorstadt, Waldstraßenviertel, Musikviertel, Zentrum-West, Zentrum-Süd]
  max_travel_min: 15
  feature_keywords:
    kitchen: [küche, ebk, einbauküche, kochnische, кухня]
    shower: [dusche, duschbad, душ]
  plz_districts: {"04229": Schleußig, "04179": Altlindenau, "04177": Lindenau, "04107": Zentrum-Süd, "04109": Zentrum-West}
  school_address: "Könneritzstraße 47, 04229 Leipzig"
  telegram_groups: []
  max_notifies_per_cycle: 10
sources:
  kleinanzeigen: { enabled: true, interval_minutes: 7, url: "https://www.kleinanzeigen.de/s-wohnung-mieten/leipzig/preis::1000/c203l4233" }
  immowelt: { enabled: true, interval_minutes: 7, url: "https://www.immowelt.de/suche/mieten/wohnung/sachsen/leipzig-04103/ad08de10168?prima=1000&wflmi=60&rmmi=3" }
  wogetra: { enabled: true, interval_minutes: 60, url: "https://www.wogetra.de/immobilien" }
  bgl: { enabled: true, interval_minutes: 60, url: "https://www.bgl.de/vermietung/wohnungsangebot" }
  vlw: { enabled: true, interval_minutes: 60, url: "https://vlw-eg.de/ueber-uns/wohnungsangebote/" }
```

(IMPORTANT: copy the ACTUAL current values from `config/criteria.yaml` — read it first; the above must match it exactly so Leipzig is unchanged.)

`config/markets/kyiv.yaml`:

```yaml
mode: buy
bot_token_env: KYIV_TELEGRAM_BOT_TOKEN
chat_id_env: KYIV_TELEGRAM_CHAT_ID
criteria:
  min_rooms: 0
  min_area_m2: 0
  max_rent_warm: 0
  required_features: []
  district_whitelist: []
  max_travel_min: 0
  mode: buy
  max_price_usd: 70000
  rooms_exact: 2
  uah_per_usd: 41.5
  preferred_districts: [Оболонь, Оболонський, Оболонский, Поділ, Подільський, Подольский]
  max_notifies_per_cycle: 15
sources:
  olx: { enabled: true, interval_minutes: 30, url: "https://www.olx.ua/uk/nedvizhimost/kvartiry/prodazha-kvartir/2-kmnati/kiev/?currency=USD&search[filter_float_price:to]=70000" }
  domria: { enabled: true, interval_minutes: 30, url: "https://dom.ria.com/prodazha-kvartir/kiev-2k/" }
  flatfy: { enabled: true, interval_minutes: 30, url: "https://flatfy.ua/uk/продаж-квартир-київ-двокімнатні?price_max=70000" }
```

(Kyiv URLs are the whole-Kyiv 2-room ≤$70k searches — Obolon is a soft preference applied in the filter, so we fetch all Kyiv and flag Obolon, per the spec. Obolon-only URLs from recon exist too if we later want to narrow.)

- [ ] **Step 4: run → PASS. Whole suite green.** **Step 5: commit** `git add -A; git commit -m "feat: market config bundles + load_market"`

---

### KB-4: Buy-mode filter branch

**Files:** Modify `src/radar/filters.py`; Test `tests/test_filters_buy.py`

- [ ] **Step 1: failing tests** `tests/test_filters_buy.py`:

```python
import pytest
from radar.models import Listing
from radar.config import Criteria
from radar.filters import evaluate, to_usd

def buy_crit():
    return Criteria(min_rooms=0, min_area_m2=0, max_rent_warm=0, required_features=[],
                    district_whitelist=[], max_travel_min=0, mode="buy", max_price_usd=70000,
                    rooms_exact=2, uah_per_usd=41.5, preferred_districts=["Оболонь", "Поділ"])

def mk(**kw):
    base = dict(source="olx", source_id="1", url="u", title="t", district="Оболонь",
                rooms=2, price=68000, currency="USD")
    base.update(kw); return Listing(**base)

def test_to_usd():
    assert to_usd(68000, "USD", 41.5) == 68000
    assert to_usd(2075000, "UAH", 41.5) == 50000
    assert to_usd(None, "USD", 41.5) is None

def test_good_buy_passes_and_preferred(buy_crit):
    r = evaluate(mk(), buy_crit)
    assert r.passed and not r.violations and "preferred" in r.flags

def test_over_price_fails(buy_crit):
    assert not evaluate(mk(price=71000), buy_crit).passed

def test_wrong_rooms_fails(buy_crit):
    assert not evaluate(mk(rooms=3), buy_crit).passed

def test_missing_price_flagged_not_dropped(buy_crit):
    r = evaluate(mk(price=None), buy_crit)
    assert r.passed and "price" in r.unknown

def test_non_preferred_district_still_passes(buy_crit):
    r = evaluate(mk(district="Дарницький"), buy_crit)
    assert r.passed and "preferred" not in r.flags

def test_uah_listing_converted(buy_crit):
    r = evaluate(mk(price=2905000, currency="UAH"), buy_crit)  # 70k usd exactly
    assert r.passed
    assert not evaluate(mk(price=2946500, currency="UAH"), buy_crit).passed  # ~71k
```

- [ ] **Step 2: run → FAIL** (no `to_usd`; `FilterResult` has no `flags`; evaluate has no buy branch).

- [ ] **Step 3: implement** in `src/radar/filters.py`:

Add `flags` to `FilterResult`:

```python
@dataclass
class FilterResult:
    passed: bool
    violations: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    flags: list = field(default_factory=list)   # non-blocking notes, e.g. "preferred"

    @property
    def needs_review(self) -> bool:
        return self.passed and bool(self.unknown)
```

Add `to_usd` + a buy branch in `evaluate`:

```python
def to_usd(price, currency, uah_per_usd):
    if price is None:
        return None
    if currency and currency.upper() == "UAH":
        return price / uah_per_usd
    return price  # USD or unknown-currency treated as USD

def evaluate(listing, c):
    if getattr(c, "mode", "rent") == "buy":
        return _evaluate_buy(listing, c)
    ...  # existing rent logic unchanged

def _evaluate_buy(listing, c):
    violations, unknown, flags = [], [], []
    if listing.rooms is None:
        unknown.append("rooms")
    elif int(listing.rooms) != c.rooms_exact:
        violations.append(f"rooms={listing.rooms} != {c.rooms_exact}")
    usd = to_usd(listing.price, listing.currency, c.uah_per_usd)
    if usd is None:
        unknown.append("price")
    elif usd > c.max_price_usd:
        violations.append(f"price={usd:.0f}usd > {c.max_price_usd:.0f}")
    if listing.district and any(p.lower() in listing.district.lower()
                                for p in (c.preferred_districts or [])):
        flags.append("preferred")
    return FilterResult(passed=not violations, violations=violations, unknown=unknown, flags=flags)
```

(The existing rent `evaluate` body moves under the `else`/after the buy early-return, unchanged. Verify all rent tests still pass.)

- [ ] **Step 4: run → PASS. Whole suite green** (rent tests unaffected). **Step 5: commit** `git add -A; git commit -m "feat: buy-mode filter (rooms/price-usd/preferred-district)"`

---

### KB-5: Buy-mode card + skip-only keyboard

**Files:** Modify `src/radar/notify.py`; Test `tests/test_notify_buy.py`

- [ ] **Step 1: failing tests** `tests/test_notify_buy.py`:

```python
from radar.filters import FilterResult
from radar.models import Listing
from radar.notify import build_card_text, build_keyboard

def mk(**kw):
    base = dict(source="olx", source_id="1", url="http://x", title="2-к Оболонь",
                district="Оболонь", rooms=2, price=68000, currency="USD")
    base.update(kw); return Listing(**base)

def test_buy_card_shows_price_and_star():
    text = build_card_text(mk(), FilterResult(passed=True, flags=["preferred"]))
    assert "68000" in text or "68 000" in text
    assert "$" in text or "USD" in text
    assert "⭐" in text          # preferred district marked
    assert "Оболонь" in text and "http://x" in text

def test_buy_card_no_star_when_not_preferred():
    text = build_card_text(mk(district="Дарницький"), FilterResult(passed=True))
    assert "⭐" not in text

def test_buy_keyboard_only_skip():
    kb = build_keyboard(7, mode="buy")
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert datas == ["skip:7"]     # no draft button in buy-mode
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement** in `notify.py`:

`build_card_text` — detect buy-mode by presence of `listing.price`:

```python
def build_card_text(listing, result):
    if listing.price is not None or (result.flags if hasattr(result, "flags") else None):
        return _build_buy_card(listing, result)
    ... existing rent card ...

def _build_buy_card(listing, result):
    star = "⭐ " if "preferred" in getattr(result, "flags", []) else ""
    price = f"{listing.price:.0f} {listing.currency or ''}".strip() if listing.price is not None else "?"
    lines = [
        f"🏢 {listing.title}",
        f"💵 {price} | 🚪 {listing.rooms or '?'} кімн.",
        f"{star}📍 {listing.district or 'район невідомий'} · {listing.source}",
    ]
    if result.unknown:
        lines.append("⚠️ Перевірити: " + ", ".join(result.unknown))
    lines.append(listing.url)
    return "\n".join(l for l in lines if l)
```

`build_keyboard` — add optional `mode`:

```python
def build_keyboard(listing_id, mode="rent"):
    if mode == "buy":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Пропустити", callback_data=f"skip:{listing_id}")]])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📝 Заявка", callback_data=f"draft:{listing_id}"),
        InlineKeyboardButton("Пропустити", callback_data=f"skip:{listing_id}")]])
```

`botclient.Notifier` needs the mode so its `notify` builds the right keyboard: add `mode="rent"` to `Notifier.__init__` and use `build_keyboard(listing_id, mode=self.mode)`. (Rent default keeps Leipzig identical; verify test_botclient still green — the existing tests construct Notifier without mode → default rent → two-button keyboard, unchanged.)

- [ ] **Step 4: run → PASS. Whole suite green.** **Step 5: commit** `git add -A; git commit -m "feat: buy-mode card + skip-only keyboard"`

---

### KB-6: UA source helpers

**Files:** Create `src/radar/sources/ua_common.py`; Test `tests/test_ua_common.py`

- [ ] **Step 1: failing tests** `tests/test_ua_common.py`:

```python
from radar.sources.ua_common import parse_price, first_jsonld, district_from_breadcrumb

def test_parse_price_usd():
    assert parse_price("68 000 $") == (68000.0, "USD")
    assert parse_price("2 075 000 грн") == (2075000.0, "UAH")
    assert parse_price("Договірна") == (None, None)

def test_first_jsonld_extracts_offer_list():
    html = '<script type="application/ld+json">{"@type":"ItemList","itemListElement":[1,2]}</script>'
    data = first_jsonld(html)
    assert data["@type"] == "ItemList"

def test_district_from_breadcrumb():
    assert district_from_breadcrumb("Оболонь · Оболонь · Оболонский · Киев") == "Оболонь"
    assert district_from_breadcrumb("") is None
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement** `ua_common.py`:

```python
import json
import re
from bs4 import BeautifulSoup

def parse_price(text: str):
    """'68 000 $' -> (68000.0,'USD'); '2 075 000 грн' -> (.,'UAH'); 'Договірна' -> (None,None)."""
    t = text or ""
    m = re.search(r"[\d \u00a0\u202f.,]{3,}", t)
    if not m:
        return (None, None)
    digits = re.sub(r"[^\d]", "", m.group(0))
    if not digits:
        return (None, None)
    value = float(digits)
    cur = "UAH" if ("грн" in t or "₴" in t) else "USD" if ("$" in t or "USD" in t.upper()) else None
    return (value, cur or "USD")

def first_jsonld(html: str):
    """Return the first application/ld+json object (parsed). None if absent/unparseable."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            return json.loads(tag.string or tag.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
    return None

def district_from_breadcrumb(text: str):
    """'Оболонь · … · Киев' -> first segment; None if empty."""
    if not text:
        return None
    parts = [p.strip() for p in re.split(r"[·>/|]", text) if p.strip()]
    return parts[0] if parts else None
```

- [ ] **Step 4: run → PASS.** **Step 5: commit** `git add -A; git commit -m "feat: UA source helpers (price/jsonld/district)"`

---

### KB-7: OLX adapter (fixture-first)

**Files:** Create `src/radar/sources/olx.py`; Test `tests/test_olx.py` + `tests/fixtures/olx_kyiv_2026-07.html`

- [ ] **Step 1: capture fixture** — fetch the recon URL (httpx, browser UA, follow_redirects). Trim to 2-3 real `application/ld+json` `Offer` blocks + their card wrappers (<30KB), save `tests/fixtures/olx_kyiv_2026-07.html`. If HTTP != 200 / no JSON-LD → BLOCKED with evidence.

- [ ] **Step 2: failing tests** `tests/test_olx.py`:

```python
from pathlib import Path
from radar.sources.olx import parse_search_page

HTML = (Path(__file__).parent / "fixtures" / "olx_kyiv_2026-07.html").read_text(encoding="utf-8")

def test_parses_offers():
    ads = parse_search_page(HTML)
    assert len(ads) >= 2
    a = ads[0]
    assert a.source == "olx"
    assert a.url.startswith("http") and a.source_id
    assert a.title
    assert a.price is not None and a.currency == "USD"
    assert a.rooms == 2 or a.rooms is None   # OLX 2-room search; rooms may come from title
    assert a.district  # areaServed.name
```

(Adjust concrete assertions to the captured fixture; keep id/url/title/price/currency/district coverage. Rooms: OLX JSON-LD may not carry rooms — set `rooms=2` since the search is 2-room-filtered, OR parse from title; decide from fixture and note it.)

- [ ] **Step 3: run → FAIL.** **Step 4: implement** `olx.py`: `parse_search_page(html)` iterates `application/ld+json` blocks (via `ua_common.first_jsonld` per-block — but there are MANY blocks; use BeautifulSoup to collect ALL ld+json scripts, filter `@type=="Offer"` or nested offers), building `Listing(source="olx", source_id=<from url -ID..html>, url, title=name, price, currency=priceCurrency, district=areaServed.name, rooms=2)`. Per-item try/except; in-page dedup by source_id. `class OLXSource` (name="olx", `__init__(search_url)`, async `fetch` via httpx browser UA). Follow the fixture for the exact JSON-LD shape.

- [ ] **Step 5: run → PASS.** **Step 6: commit** `git add -A; git commit -m "feat: olx kyiv sale adapter"`

---

### KB-8: DIM.RIA adapter (fixture-first, code-side price filter)

**Files:** Create `src/radar/sources/domria.py`; Test `tests/test_domria.py` + fixture

- [ ] **Step 1: capture fixture** from `https://dom.ria.com/prodazha-kvartir/kiev-2k/` → `tests/fixtures/domria_kyiv_2026-07.html` (2-3 real cards; HTML markup, no JSON-LD per recon).
- [ ] **Step 2: failing tests** `tests/test_domria.py`: parse count ≥2; first card source="domria", source_id (trailing numeric id from `...-<id>.html`), url absolute, title, price (from `NN NNN $` via `parse_price`), currency "USD", rooms (from "2 комнаты" → 2), district (from breadcrumb via `district_from_breadcrumb`), area. Include a malformed-card isolation test.
- [ ] **Step 3: run → FAIL.** **Step 4: implement** `domria.py`: select the recurring card container from the fixture; extract price via `ua_common.parse_price`, rooms via regex `(\d+)\s*комнат`, district via `district_from_breadcrumb` on the breadcrumb element, id from the detail-link href; per-card try/except; in-page dedup. `class DomRiaSource` (name="domria", `__init__(search_url)`, async fetch). NOTE: price is NOT URL-filtered → the pipeline's buy-filter drops >$70k, so no adapter-side price cap needed (but the adapter still parses the price for the filter).
- [ ] **Step 5: run → PASS.** **Step 6: commit** `git add -A; git commit -m "feat: dom.ria kyiv sale adapter"`

---

### KB-9: flatfy adapter (fixture-first, JSON-LD ItemList)

**Files:** Create `src/radar/sources/flatfy.py`; Test `tests/test_flatfy.py` + fixture

- [ ] **Step 1: capture fixture** from the recon flatfy URL → `tests/fixtures/flatfy_kyiv_2026-07.html` (the single `["ItemList","RealEstateListing"]` ld+json block + minimal wrapper).
- [ ] **Step 2: failing tests** `tests/test_flatfy.py`: parse count ≥2; first item source="flatfy", source_id (internal numeric id), title (name/address), price + currency "USD", rooms (room_count), district (from the URL/area if present in JSON — else None acceptable → flagged), url (derive `https://flatfy.ua/uk/<id>` OR fall back to the search url — assert it startswith "http").
- [ ] **Step 3: run → FAIL.** **Step 4: implement** `flatfy.py`: `first_jsonld(html)` → the ItemList; iterate `itemListElement`/`mainEntity` items (follow the fixture's exact nesting); build Listing per item; url derivation per what the fixture supports (report the decision); per-item try/except; in-page dedup. `class FlatfySource` (name="flatfy", `__init__(search_url)`, async fetch with browser UA; Cloudflare present but recon saw clean 200s — no special handling, but on 403/429 the pipeline's source-failure alert covers it). District: if the JSON lacks per-item district, set None (filter flags it; Obolon-preferred still works when present).
- [ ] **Step 5: run → PASS.** **Step 6: commit** `git add -A; git commit -m "feat: flatfy kyiv sale adapter"`

---

### KB-10: register Kyiv adapters

**Files:** Modify `src/radar/sources/registry.py`; Test `tests/test_registry_kyiv.py`

- [ ] **Step 1: failing test** `tests/test_registry_kyiv.py`:

```python
from radar.config import Criteria
from radar.sources.registry import build_sources

def crit(sources):
    return Criteria(min_rooms=0, min_area_m2=0, max_rent_warm=0, required_features=[],
                    district_whitelist=[], max_travel_min=0, mode="buy", sources=sources)

def test_builds_kyiv_sources():
    c = crit({"olx": {"enabled": True, "interval_minutes": 30, "url": "http://o"},
              "domria": {"enabled": True, "interval_minutes": 30, "url": "http://d"},
              "flatfy": {"enabled": False, "interval_minutes": 30, "url": "http://f"}})
    names = {s.name for s, _ in build_sources(c)}
    assert names == {"olx", "domria"}   # flatfy disabled
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement** — add to `_FACTORIES` in `registry.py`:

```python
    "olx": lambda cfg, c: OLXSource(cfg["url"]),
    "domria": lambda cfg, c: DomRiaSource(cfg["url"]),
    "flatfy": lambda cfg, c: FlatfySource(cfg["url"]),
```

with the imports. (Leipzig factories unchanged.)

- [ ] **Step 4: run → PASS. Whole suite green.** **Step 5: commit** `git add -A; git commit -m "feat: register kyiv adapters"`

---

### KB-11: cycle --market wiring + mode-gating

**Files:** Modify `src/radar/cycle.py`, `src/radar/dispatch.py`; Test `tests/test_cycle_market.py`

- [ ] **Step 1: failing tests** `tests/test_cycle_market.py`:

```python
import os
from radar import cycle

def test_build_deps_uses_market_bot_env(monkeypatch, pg_conn):
    monkeypatch.setenv("KYIV_TELEGRAM_BOT_TOKEN", "123:kyivbot")
    monkeypatch.setenv("KYIV_TELEGRAM_CHAT_ID", "555")
    from radar.config import load_market
    from pathlib import Path
    m = load_market("kyiv", Path(cycle.ROOT) / "config" / "markets")
    d = cycle._build_deps(pg_conn, cycle.make_bot("123:kyivbot"), m, dry_run=True)
    assert d.chat_id == "555"
    assert d.market == "kyiv"
    assert d.notifier.mode == "buy"        # buy notifier
    assert d.calendar is None and d.mailer is None  # buy-mode: no calendar/mailer
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement**

`dispatch.py`: add `market: str = "leipzig"` to `Deps`. `dispatch_update` passes nothing new (handlers use it only via db calls that are Leipzig-only; for buy the only callback is `skip:` which calls `dbm.set_status(conn, id, "skipped")` — id unique, no market needed; the forward/status paths are rent-only but harmless — buy channel simply won't send draft buttons). Keep dispatch as-is except the Deps field.

`cycle.py`: `run_cycle` gains `market` param from `--market` (default "leipzig"). Load the market bundle: `m = load_market(market, ROOT/"config"/"markets")`. `_build_deps(conn, bot, market_obj, dry_run)` now:
- reads bot token/chat from `os.environ[market_obj.bot_token_env]` / `[market_obj.chat_id_env]`,
- `Notifier(bot, chat_id, dry_run=dry_run, mode=market_obj.mode)`,
- for `mode == "buy"`: `mailer=None`, `calendar=None`, `profile=None`, `email_finder=None` (mode-gated — no applications/calendar); for `rent`: current behavior,
- `Deps(..., market=market_obj.name, criteria=market_obj.criteria)`.
`run_cycle` builds `Pipeline(conn, m.criteria, notifier, market=m.name, geo=(build_geo_checker(...) if m.mode=="rent" else None), notify_cap=m.criteria.max_notifies_per_cycle)` — **geo only for rent** (buy has no geo). `pipeline.retry_pending()` and per-source loop use `build_sources(m.criteria)`. `drain_updates(bot, d)` uses `dbm.get_offset(conn, market=m.name)` / `set_offset(conn, off, market=m.name)`.

`main()`: `--market` arg (choices leipzig/kyiv, default leipzig).

IMPORTANT: the current Leipzig path calls `run_cycle()` with no market → default "leipzig" → loads `markets/leipzig.yaml` (which must equal the old criteria.yaml). Confirm the Leipzig poll.yml still works by running `python -m radar.cycle --dry-run` against the test schema (see KB-12 verification).

- [ ] **Step 4: run test_cycle_market → PASS. `python -c "import radar.cycle"` clean. Whole suite green.** **Step 5: commit** `git add -A; git commit -m "feat: cycle --market wiring + buy mode-gating"`

---

### KB-12: Kyiv workflow + dry-run + docs

**Files:** Create `.github/workflows/poll-kyiv.yml`; Modify `README.md`, `docs/DECISIONS.md`, `.env.example`

- [ ] **Step 1: dry-run both markets** against an isolated schema (like the Leipzig CM-11 dry-run): with `PGOPTIONS=-c search_path=radar_test` + real keys + a placeholder `KYIV_TELEGRAM_BOT_TOKEN`/`KYIV_TELEGRAM_CHAT_ID` (or the real Kyiv bot once created), run `python -m radar.cycle --market kyiv --dry-run` → all 3 Kyiv sources fetch, `[DRY-RUN notify]` buy-cards print for ≤$70k 2-room, no traceback; then `python -m radar.cycle --market leipzig --dry-run` → Leipzig still fetches its 5 sources unchanged. Query the isolated schema per-market counts. Drop the schema after.

- [ ] **Step 2: create `.github/workflows/poll-kyiv.yml`:**

```yaml
name: poll-kyiv
on:
  schedule:
    - cron: "*/30 * * * *"
  workflow_dispatch: {}
concurrency:
  group: radar-cycle-kyiv
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
      - run: python -m radar.cycle --market kyiv
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          KYIV_TELEGRAM_BOT_TOKEN: ${{ secrets.KYIV_TELEGRAM_BOT_TOKEN }}
          KYIV_TELEGRAM_CHAT_ID: ${{ secrets.KYIV_TELEGRAM_CHAT_ID }}
```

(No Routes/Anthropic/Gmail/Calendar — buy-mode doesn't use them.)

- [ ] **Step 3: docs** — `README.md`: a "Kyiv market (buy)" section — the `--market kyiv` cycle, buy-mode (monitoring only), the two Kyiv secrets, the poll-kyiv workflow, and the cutover step (create a new @BotFather bot + channel → add `KYIV_TELEGRAM_BOT_TOKEN`/`KYIV_TELEGRAM_CHAT_ID` repo secrets → enable poll-kyiv). `.env.example`: add `KYIV_TELEGRAM_BOT_TOKEN=` / `KYIV_TELEGRAM_CHAT_ID=`. `docs/DECISIONS.md`: multi-market design (market column on listings only; offset namespaced; geocode/pending stay rent-only), buy-mode (rooms-exact/price-usd/preferred-district-soft; USD default, UAH via static uah_per_usd), Kyiv sources chosen (OLX JSON-LD; DIM.RIA HTML + code-side price filter; flatfy JSON-LD aggregating rieltor), and dropped lun.ua (RSC-redundant) + rieltor.ua (429/stale under burst, redundant).

- [ ] **Step 4: full suite green; `import radar.cycle` clean.** **Step 5: commit** `git add -A; git commit -m "ci+docs: kyiv poll workflow + multi-market runbook"`

---

## Cutover (user + operator, after the plan)

1. User creates a new Telegram bot via @BotFather + a channel/chat → `KYIV_TELEGRAM_BOT_TOKEN` + `KYIV_TELEGRAM_CHAT_ID`.
2. Add both as GitHub repo secrets (`gh secret set`). `DATABASE_URL` already set (shared).
3. Push; the workflow-file change auto-registers `poll-kyiv` (GitHub registers workflows when their files change in a push — an empty commit won't).
4. Actions → Run `poll-kyiv` manually to smoke-test; confirm a buy-card lands in the Kyiv channel (or a clean run if nothing ≤$70k right now).

## Follow-ups (not in this plan)
- Obolon-only narrowing (recon has the exact URLs) if the whole-Kyiv feed is too noisy.
- rieltor.ua adapter (throttled) only if flatfy proves to miss exclusive listings.
- Kyiv daily digest.
- Live UAH→USD rate (static rate suffices; most listings are USD).
