# Wohnung-Radar Plan 2: Sources + Geo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand coverage (Immowelt, 3 easy coop sites, UA Telegram groups, WhatsApp forwards) and add the exact ≤15-min-to-school travel-time filter.

**Architecture:** Same single service (`projects/wohnung-radar/`). New source adapters plug into the existing `Source` protocol; a config-driven source registry replaces the hardcoded list. A shared free-text message parser feeds Telegram-group messages and manual forwards into the same pipeline. Geo check (Nominatim geocode cache + Google Routes walk/transit) runs after the cheap filter, refining district decisions.

**Tech Stack additions:** Telethon (TG user session), anthropic (Haiku message-parse fallback, optional), Google Routes API v2 (REST via httpx), Nominatim (geocoding, cached).

**Grounded by live recon 2026-07-18** (do NOT re-guess these facts):
- **Immowelt**: `https://www.immowelt.de/suche/mieten/wohnung/sachsen/leipzig-04103/ad08de10168?prima=1000&wflmi=60&rmmi=3` → HTTP 200, server-rendered, 32 cards/page. Card anatomy: container `[data-testid^="classified-card-mfe-"]` / `id="classified-card-<ID>"`; link `a[href*="/expose/"]` whose `title` attr = full summary; img `alt` = summary incl. street+district+PLZ; price `[data-testid="cardmfe-price-testid"]` (label = **Kaltmiete**); keyfacts `[data-testid="cardmfe-keyfacts-testid"]` = "2 Zimmer · 34 m² · 6. Geschoss"; address `[data-testid="cardmfe-description-box-address"]` = "Eisenbahnstr. 117, Volkmarsdorf, Leipzig (04315)". Pagination is XHR-only (no URL param) → we poll page 1 only, sorted newest if a sort param can be verified in-task. UNITAS coop lists exclusively on Immowelt → covered automatically.
- **IS24**: AWS WAF challenge (HTTP 401 "Ich bin kein Roboter") on plain GET → **excluded from this plan**; revisit only via official API.
- **Wogetra**: `https://www.wogetra.de/immobilien` — server-rendered WordPress, all listings on one page; fields: title, district+street, Objekt-ID, Zimmer, Wohnfläche, **Nettokaltmiete AND Warmmiete**.
- **BGL**: `https://www.bgl.de/vermietung/wohnungsangebot` — server-rendered Joomla "OS Property", URL-param filters work; fields: Zi., m², **Kaltmiete only**, full address.
- **VLW**: `https://vlw-eg.de/ueber-uns/wohnungsangebote/` — listing cards present in server HTML; fields: rooms, m², **"XXX € warm"**, street+PLZ+district; detail links `wohnung?id=...`.
- **Hard-tier coops (JS apps, NOT in this plan — future plan with headless browser): LWB** (easySquare/SAPUI5 external portal), **Lipsia** (wg-lipsia.de AngularJS widget), **WBG Kontakt** (wbg-kontakt.de Contao AJAX). Correct domains recorded here because the obvious guesses are wrong: wg-lipsia.de (NOT lipsia.de), wbg-kontakt.de (NOT wg-kontakt.de), vlw-eg.de (NOT vlw-leipzig.de).
- **UA Telegram**: no scrapable Leipzig housing channels exist — only **groups** (no public post feed). Primary: `@accomodation_leipzig_ukraine` (4.3k, dedicated housing group by Leipzig Helps Ukraine e.V.). Secondary candidates: `@UAinDE_Leipzig` (classifieds), `@leipzig_ukrainians`, `@ukrainerinleipzig` (general). Reading requires **Telethon user session + the user's account being a member**.

**Fixture-first protocol for every adapter task** (lesson from Plan 1's KA rework): (1) fetch the live page once with httpx + browser UA, save trimmed real HTML (2-4 cards, <30KB) to `tests/fixtures/<source>_<yyyy-mm>.html`, commit it; (2) write tests against that real fixture; (3) implement parser; selectors in this plan come from recon and are the starting point — if the live fixture differs, follow the fixture and record the deviation. Parsers are pure functions over HTML; per-card try/except isolation; `_num()`-style German number handling reused via a shared helper.

**File structure (new/modified):**

```
src/radar/sources/immowelt.py      # Task 3
src/radar/sources/wogetra.py       # Task 4
src/radar/sources/bgl.py           # Task 5
src/radar/sources/vlw.py           # Task 6
src/radar/sources/common.py        # Task 3: shared num/PLZ-district helpers
src/radar/sources/registry.py      # Task 7: config → [Source] list
src/radar/msgparse.py              # Task 8: free-text → Listing candidate
src/radar/tg_groups.py             # Task 10: Telethon reader
src/radar/geo.py                   # Task 11: geocode cache + Routes check
src/radar/db.py                    # Task 1: rent_cold column + migration; Task 11: geocode_cache table
src/radar/dedup.py                 # Task 1: like-for-like rent guard
src/radar/config.py + config/criteria.yaml   # Task 2: sources/features/plz sections
src/radar/main.py                  # Tasks 7/9/10/11 wiring
tests/...                          # per task
```

---

### Task 1: rent_cold column + like-for-like dedup rent guard

**Files:** Modify `src/radar/db.py`, `src/radar/dedup.py`; Test `tests/test_db.py`, `tests/test_dedup.py`

Closes the Plan-1 landmine: dedup compared `rent_warm` only, which KA never fills → rent guard inert.

- [ ] **Step 1: failing tests**

Append to `tests/test_db.py`:

```python
def test_rent_cold_persisted_and_migrated(tmp_path):
    path = str(tmp_path / "t.db")
    conn = dbm.connect(path)
    l = make(); l.rent_cold = 750
    row_id = dbm.insert_if_new(conn, l)
    assert dbm.recent_listings(conn)[0]["rent_cold"] == 750
    conn.close()
    conn2 = dbm.connect(path)  # reconnect on existing db must not fail (migration idempotent)
    assert dbm.recent_listings(conn2)[0]["rent_cold"] == 750
```

Append to `tests/test_dedup.py`:

```python
def test_cold_vs_cold_rent_guard(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    dbm.insert_if_new(conn, Listing(source="immowelt", source_id="c1", url="u",
                                    title="3 Zimmer Wohnung Schleußig", rent_cold=700, area_m2=72))
    cand = Listing(source="kleinanzeigen", source_id="c2", url="u2",
                   title="3 Zimmer Wohnung Schleußig", rent_cold=950, area_m2=72)
    assert not is_cross_source_duplicate(cand, dbm.recent_listings(conn))  # cold 700 vs 950 differ

def test_warm_vs_cold_not_compared(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    dbm.insert_if_new(conn, Listing(source="immowelt", source_id="w1", url="u",
                                    title="3 Zimmer Wohnung Schleußig", rent_warm=950, area_m2=72))
    cand = Listing(source="kleinanzeigen", source_id="w2", url="u2",
                   title="3 Zimmer Wohnung Schleußig", rent_cold=700, area_m2=72)
    assert is_cross_source_duplicate(cand, dbm.recent_listings(conn))  # rent kinds differ -> skip rent guard, fuzzy title decides
```

- [ ] **Step 2: run → FAIL** (`no such column: rent_cold`; warm-vs-cold currently compared as warm None → guard skipped… verify each red reason).

- [ ] **Step 3: implement**

`db.py`: add `rent_cold REAL` to SCHEMA after `rent_warm REAL,`; add migration in `connect()` after executescript:

```python
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(listings)")}
    if "rent_cold" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN rent_cold REAL")
        conn.commit()
```

Extend `insert_if_new` INSERT column list with `rent_cold` (+ value `listing.rent_cold`).

`dedup.py`: replace the rent guard with like-for-like comparison:

```python
        if (listing.rent_cold is not None and row["rent_cold"] is not None
                and abs(listing.rent_cold - row["rent_cold"]) > 20):
            continue
        if (listing.rent_warm is not None and row["rent_warm"] is not None
                and abs(listing.rent_warm - row["rent_warm"]) > 20):
            continue
```

`pipeline.py` (closes the second Plan-1 landmine now that multiple sources run concurrently): move the `existing = dbm.recent_listings(self.conn)` snapshot from before the loop to inside it — fetch fresh rows right before the `is_cross_source_duplicate` call for each new listing (SQLite-local, 200 rows, negligible cost). Add a comment: same-cycle cross-source duplicates are now visible.

- [ ] **Step 4: full suite → PASS.** **Step 5:** `git add -A; git commit -m "feat: rent_cold column + like-for-like dedup rent guard"`

---

### Task 2: config expansion (sources, feature keywords, PLZ map)

**Files:** Modify `src/radar/config.py`, `config/criteria.yaml`; Test `tests/test_config.py`

- [ ] **Step 1: failing test** — append to `tests/test_config.py`:

```python
def test_extended_config_loads():
    c = load_criteria(Path(__file__).parents[1] / "config" / "criteria.yaml")
    assert c.sources["kleinanzeigen"]["enabled"] is True
    assert c.sources["immowelt"]["interval_minutes"] == 7
    assert c.sources["wogetra"]["interval_minutes"] == 60
    assert "küche" in c.feature_keywords["kitchen"]
    assert c.plz_districts["04229"] == "Schleußig"
    assert c.school_address.startswith("Könneritzstraße 47")
    assert c.telegram_groups == []
```

- [ ] **Step 2: run → FAIL** (unexpected keyword). **Step 3: implement**

`config.py` — add fields to `Criteria`:

```python
    sources: dict = None
    feature_keywords: dict = None
    plz_districts: dict = None
    school_address: str = ""
    telegram_groups: list = None
```

(defaults keep old direct-construction tests working; `load_criteria` unchanged — yaml supplies all keys.)

`criteria.yaml` — append:

```yaml
school_address: "Könneritzstraße 47, 04229 Leipzig"
feature_keywords:
  kitchen: [küche, ebk, einbauküche, kochnische, кухня]
  shower: [dusche, duschbad, душ]
plz_districts:   # unambiguous PLZ→district (whitelist-relevant); extend as needed
  "04229": Schleußig
  "04179": Altlindenau
  "04177": Lindenau
  "04107": Zentrum-Süd
  "04109": Zentrum-West
telegram_groups: []   # e.g. [accomodation_leipzig_ukraine, UAinDE_Leipzig] — user joins them first
sources:
  kleinanzeigen:
    enabled: true
    interval_minutes: 7
    url: "https://www.kleinanzeigen.de/s-wohnung-mieten/leipzig/preis::1000/c203l4233"
  immowelt:
    enabled: true
    interval_minutes: 7
    url: "https://www.immowelt.de/suche/mieten/wohnung/sachsen/leipzig-04103/ad08de10168?prima=1000&wflmi=60&rmmi=3"
  wogetra:
    enabled: true
    interval_minutes: 60
    url: "https://www.wogetra.de/immobilien"
  bgl:
    enabled: true
    interval_minutes: 60
    url: "https://www.bgl.de/vermietung/wohnungsangebot"
  vlw:
    enabled: true
    interval_minutes: 60
    url: "https://vlw-eg.de/ueber-uns/wohnungsangebote/"
```

`filters.py`: `evaluate` uses `c.feature_keywords or FEATURE_KEYWORDS` (module dict stays as fallback for direct-constructed Criteria in old tests). One-line change:

```python
    keywords = c.feature_keywords or FEATURE_KEYWORDS
    for feat in c.required_features:
        if not any(kw in text for kw in keywords.get(feat, [feat])):
```

Also migrate `kleinanzeigen_search_url` usage: keep the field for back-compat but `main.py` (Task 7) reads `sources` instead; remove the old key from yaml only after Task 7 flips wiring (do NOT break main.py in this task — leave both keys in yaml for now).

- [ ] **Step 4: full suite → PASS.** **Step 5:** commit `feat: config-driven sources, feature keywords, PLZ map`

---

### Task 3: shared source helpers + Immowelt adapter

**Files:** Create `src/radar/sources/common.py`, `src/radar/sources/immowelt.py`; Test `tests/test_immowelt.py` (+ fixture per protocol)

- [ ] **Step 1: capture fixture** — fetch the recon URL above (httpx, browser UA), trim to 3 real cards (one with district in address, one sparse if present), save `tests/fixtures/immowelt_search_2026-07.html`.

- [ ] **Step 2: failing tests** — `tests/test_immowelt.py`:

```python
from pathlib import Path
from radar.sources.immowelt import parse_search_page

HTML = (Path(__file__).parent / "fixtures" / "immowelt_search_2026-07.html").read_text(encoding="utf-8")

def test_parses_cards():
    ads = parse_search_page(HTML)
    assert len(ads) >= 2
    ad = ads[0]
    assert ad.source == "immowelt"
    assert ad.url.startswith("https://www.immowelt.de/expose/")
    assert ad.source_id  # expose uuid
    assert ad.title
    assert ad.rent_cold is not None and ad.rent_warm is None  # Immowelt lists Kaltmiete
    assert ad.rooms is not None and ad.area_m2 is not None
    assert ad.district is not None   # from address box "…, Volkmarsdorf, Leipzig (04315)"
    assert ad.address                # raw address string preserved

def test_dedup_key_stable():
    a = parse_search_page(HTML); b = parse_search_page(HTML)
    assert [x.source_id for x in a] == [x.source_id for x in b]
```

(Adjust assertions to what the captured fixture actually contains — that is the point of fixture-first; keep at least id/url/title/rent_cold/rooms/area.)

- [ ] **Step 3: run → FAIL.** **Step 4: implement**

`sources/common.py`:

```python
import re

def num_de(text: str | None) -> float | None:
    """German-format number: '1.100,50' -> 1100.5. Requires a digit."""
    m = re.search(r"\d[\d.,]*", text or "")
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))

def district_from_address(addr: str, plz_districts: dict | None = None) -> str | None:
    """'Eisenbahnstr. 117, Volkmarsdorf, Leipzig (04315)' -> 'Volkmarsdorf';
    fallback: PLZ lookup; city-only -> None."""
    parts = [p.strip() for p in addr.split(",")]
    for p in parts[1:]:
        name = re.sub(r"\s*\(\d{5}\)\s*", "", p).strip()
        if name and name.lower() not in ("leipzig",):
            return name
    m = re.search(r"\b(0\d{4})\b", addr)
    if m and plz_districts:
        return plz_districts.get(m.group(1))
    return None
```

`sources/immowelt.py`:

```python
import logging
import re
import httpx
from bs4 import BeautifulSoup
from ..models import Listing
from .common import num_de, district_from_address

log = logging.getLogger("radar")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
           "Accept-Language": "de-DE"}

def parse_search_page(html: str, plz_districts: dict | None = None) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    for card in soup.select('[data-testid^="classified-card-mfe-"], [id^="classified-card-"]'):
        try:
            link = card.select_one('a[href*="/expose/"]')
            if link is None or not link.get("href"):
                continue
            url = link["href"]
            source_id = url.rstrip("/").rsplit("/", 1)[-1]
            price_el = card.select_one('[data-testid="cardmfe-price-testid"]')
            facts_el = card.select_one('[data-testid="cardmfe-keyfacts-testid"]')
            addr_el = card.select_one('[data-testid="cardmfe-description-box-address"]')
            rooms = area = None
            facts = facts_el.get_text(" ", strip=True) if facts_el else ""
            m = re.search(r"([\d,.]+)\s*Zimmer", facts)
            if m:
                rooms = num_de(m.group(1))
            m = re.search(r"([\d,.]+)\s*m²", facts)
            if m:
                area = num_de(m.group(1))
            addr = addr_el.get_text(" ", strip=True) if addr_el else ""
            out.append(Listing(
                source="immowelt",
                source_id=source_id,
                url=url if url.startswith("http") else "https://www.immowelt.de" + url,
                title=(link.get("title") or link.get_text(strip=True) or "").strip(),
                district=district_from_address(addr, plz_districts) if addr else None,
                address=addr or None,
                rooms=rooms,
                area_m2=area,
                rent_cold=num_de(price_el.get_text() if price_el else None),
                features_text=facts,
            ))
        except Exception:
            log.warning("skipping malformed immowelt card", exc_info=True)
            continue
    # de-dupe repeated promoted cards within the page
    seen, unique = set(), []
    for ad in out:
        if ad.source_id not in seen:
            seen.add(ad.source_id)
            unique.append(ad)
    return unique

class ImmoweltSource:
    name = "immowelt"

    def __init__(self, search_url: str, plz_districts: dict | None = None):
        self.search_url = search_url
        self.plz_districts = plz_districts

    async def fetch(self) -> list[Listing]:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30,
                                     follow_redirects=True) as client:
            resp = await client.get(self.search_url)
            resp.raise_for_status()
        return parse_search_page(resp.text, self.plz_districts)
```

In-task check (record result in DECISIONS.md): try appending `&sort=createdate` (and `&order=DateDesc` as second candidate) to the search URL — if the first page then leads with newest listings, add the working param to the yaml URL; if neither works, keep default order (page 1 + 7-min polling is acceptable).

- [ ] **Step 5: full suite → PASS.** **Step 6:** commit `feat: immowelt adapter (covers UNITAS listings)`

---

### Task 4: Wogetra adapter

**Files:** Create `src/radar/sources/wogetra.py`; Test `tests/test_wogetra.py` + fixture

Fixture-first protocol against `https://www.wogetra.de/immobilien` (server-rendered WordPress; all listings on one page; per recon fields include title, "Grünau-Nord, Plovdiver Str. 72 /0101", Objekt-ID, Zimmer, Wohnfläche ca., Verfügbar ab, Nettokaltmiete, Warmmiete).

- [ ] **Step 1: capture fixture** `tests/fixtures/wogetra_2026-07.html` (2-3 real listing blocks).
- [ ] **Step 2: failing tests** — same shape as Task 3: parse count ≥2; first listing asserts source="wogetra", source_id = Objekt-ID, title, district (first segment before comma of the location line), area, rooms, **rent_cold from Nettokaltmiete AND rent_warm from Warmmiete** (both present per recon), url (detail link or the immobilien page anchor), address preserved.
- [ ] **Step 3: implement** `wogetra.py` mirroring the immowelt.py structure (constructor `(url)`, class `WogetraSource`, name "wogetra"): select the recurring listing container observed in the fixture; extract labeled values by their German labels ("Zimmer", "Wohnfläche", "Nettokaltmiete", "Warmmiete", "Objekt-ID") via label→value traversal, `num_de` for numbers; per-card try/except. Exact selectors follow the captured fixture.
- [ ] **Step 4: suite → PASS.** **Step 5:** commit `feat: wogetra adapter`

---

### Task 5: BGL adapter

**Files:** Create `src/radar/sources/bgl.py`; Test `tests/test_bgl.py` + fixture

Against `https://www.bgl.de/vermietung/wohnungsangebot` (Joomla OS Property, URL-param filters e.g. `?min_price=100`; cards: "3 Zi.", m², Kaltmiete only, "Mannheimer Straße 76, 04209 Leipzig", detail slug per unit, `images/osproperty/properties/<id>/` thumbnails → property id usable as source_id).

- [ ] **Step 1: capture fixture** `tests/fixtures/bgl_2026-07.html`.
- [ ] **Step 2: failing tests**: count ≥2; source="bgl", source_id (OS Property id from detail URL or image path), title, rooms ("Zi."), area, rent_cold, address, district via `district_from_address`/PLZ map (BGL addresses are "street, PLZ Leipzig" → district often only via PLZ; None acceptable → unknown flag).
- [ ] **Step 3: implement** `bgl.py` (`BGLSource`, name "bgl", constructor `(url, plz_districts)`) — selectors from fixture; per-card isolation.
- [ ] **Step 4: suite → PASS.** **Step 5:** commit `feat: bgl adapter`

---

### Task 6: VLW adapter

**Files:** Create `src/radar/sources/vlw.py`; Test `tests/test_vlw.py` + fixture

Against `https://vlw-eg.de/ueber-uns/wohnungsangebote/` (cards in server HTML; "2 Zimmer", "50 m²", **"508 € warm"** — warm ONLY → map to rent_warm, rent_cold=None; address "Hartzstr. 14, 04129 Eutritzsch" → district = segment after PLZ; detail links `wohnung?id=...` → id param = source_id).

- [ ] **Step 1: capture fixture** `tests/fixtures/vlw_2026-07.html`. NOTE: if the live page turns out to be JS-filtered with empty server HTML (recon saw content, but verify), mark task BLOCKED and report — do not build a headless browser here.
- [ ] **Step 2: failing tests**: count ≥1; source="vlw", **rent_warm set, rent_cold None**, rooms, area, district ("Eutritzsch"-style), url absolute, source_id from `id=` query param.
- [ ] **Step 3: implement** `vlw.py` (`VLWSource`, name "vlw") per fixture.
- [ ] **Step 4: suite → PASS.** **Step 5:** commit `feat: vlw adapter`

---

### Task 7: config-driven source registry + wiring

**Files:** Create `src/radar/sources/registry.py`; Modify `src/radar/main.py`, `config/criteria.yaml`, `src/radar/config.py`; Test `tests/test_registry.py`

- [ ] **Step 1: failing test** — `tests/test_registry.py`:

```python
from radar.config import Criteria
from radar.sources.registry import build_sources

def crit(sources):
    return Criteria(min_rooms=3, min_area_m2=60, max_rent_warm=1000,
                    required_features=[], district_whitelist=[], max_travel_min=15,
                    sources=sources)

def test_builds_enabled_sources_with_intervals():
    c = crit({
        "kleinanzeigen": {"enabled": True, "interval_minutes": 7, "url": "http://ka"},
        "immowelt": {"enabled": False, "interval_minutes": 7, "url": "http://iw"},
        "wogetra": {"enabled": True, "interval_minutes": 60, "url": "http://wg"},
    })
    built = build_sources(c)
    names = {s.name: minutes for s, minutes in built}
    assert names == {"kleinanzeigen": 7, "wogetra": 60}  # disabled immowelt absent

def test_unknown_source_key_raises():
    import pytest
    with pytest.raises(KeyError):
        build_sources(crit({"nope": {"enabled": True, "interval_minutes": 5, "url": "u"}}))
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement**

`sources/registry.py`:

```python
from ..config import Criteria
from .bgl import BGLSource
from .immowelt import ImmoweltSource
from .kleinanzeigen import KleinanzeigenSource
from .vlw import VLWSource
from .wogetra import WogetraSource

_FACTORIES = {
    "kleinanzeigen": lambda cfg, c: KleinanzeigenSource(cfg["url"]),
    "immowelt": lambda cfg, c: ImmoweltSource(cfg["url"], c.plz_districts),
    "wogetra": lambda cfg, c: WogetraSource(cfg["url"]),
    "bgl": lambda cfg, c: BGLSource(cfg["url"], c.plz_districts),
    "vlw": lambda cfg, c: VLWSource(cfg["url"]),
}

def build_sources(criteria: Criteria) -> list[tuple[object, int]]:
    """[(source_instance, poll_interval_minutes)] for enabled sources."""
    out = []
    for key, cfg in (criteria.sources or {}).items():
        factory = _FACTORIES[key]  # unknown key -> KeyError, fail loud
        if cfg.get("enabled"):
            out.append((factory(cfg, criteria), int(cfg["interval_minutes"])))
    return out
```

`main.py`: replace `sources = [KleinanzeigenSource(...)]` + fixed `POLL_MINUTES` with:

```python
    built = build_sources(criteria)
    sources = [s for s, _ in built]
    ...
    for source, minutes in built:
        scheduler.add_job(pipeline.run_source, "interval",
                          minutes=minutes, jitter=60, args=[source])
```

(import `build_sources`; drop POLL_MINUTES and the KleinanzeigenSource import.) Now remove the legacy `kleinanzeigen_search_url` key from `criteria.yaml` and the field's required status in `Criteria` (make default `""`); update `tests/test_config.py` accordingly.

- [ ] **Step 4: full suite → PASS; `python -c "import radar.main"` OK.** **Step 5:** commit `feat: config-driven source registry`

---

### Task 8: free-text message parser (rules + optional Haiku fallback)

**Files:** Create `src/radar/msgparse.py`; Test `tests/test_msgparse.py`; Modify `pyproject.toml` (add `anthropic>=0.40` dependency)

Turns a UA/RU/DE free-text message (TG group post or WhatsApp forward) into a Listing candidate or None.

- [ ] **Step 1: failing tests** — `tests/test_msgparse.py`:

```python
from radar.msgparse import parse_message

def test_ua_rental_offer_parsed():
    text = ("Здам 3-кімнатну квартиру в Лейпцигу, Schleußig, 72 м², "
            "1000 євро warm, є кухня і душ. Писати в приват.")
    l = parse_message(text, source="tg:accomodation_leipzig_ukraine", source_id="42")
    assert l is not None
    assert l.rooms == 3 and l.area_m2 == 72
    assert l.rent_warm == 1000
    assert l.district == "Schleußig"
    assert l.source == "tg:accomodation_leipzig_ukraine" and l.source_id == "42"

def test_de_offer_parsed():
    l = parse_message("Vermiete 3-Zimmer-Wohnung, 65 m², 950€ warm, Plagwitz",
                      source="whatsapp", source_id="x1")
    assert l and l.rooms == 3 and l.rent_warm == 950 and l.district == "Plagwitz"

def test_kalt_price_goes_to_rent_cold():
    l = parse_message("3-Zi-Wohnung 70 m² 800 € kalt Lindenau", source="whatsapp", source_id="x2")
    assert l and l.rent_cold == 800 and l.rent_warm is None

def test_search_request_not_offer_returns_none():
    assert parse_message("Шукаю квартиру для сім'ї, розгляну варіанти",
                         source="whatsapp", source_id="x3") is None

def test_unrelated_chatter_returns_none():
    assert parse_message("Дякую всім за допомогу з документами!",
                         source="whatsapp", source_id="x4") is None
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement**

`msgparse.py`:

```python
import logging
import os
import re
from .models import Listing

log = logging.getLogger("radar")

OFFER_HINTS = re.compile(r"\b(здам|здаю|сдам|сдаю|vermiete|zu vermieten|пропоную оренду|"
                         r"free from|frei ab|доступн\w* з)\b", re.IGNORECASE)
SEEK_HINTS = re.compile(r"\b(шукаю|ищу|ищем|шукаємо|suche|sucht)\b", re.IGNORECASE)
ROOMS_RE = re.compile(r"(\d[.,]?\d?)\s*[-\s]?(кімнат|комнат|zimmer|zi\b|к\b|r\b|raum)", re.IGNORECASE)
AREA_RE = re.compile(r"(\d{2,3})\s*(?:м²|м2|кв\.?\s?м|m²|m2|qm)", re.IGNORECASE)
PRICE_RE = re.compile(r"(\d{3,4})\s*(?:€|евро|євро|euro|eur)\s*(warm|kalt|холодн\w*|тепл\w*)?",
                      re.IGNORECASE)
DISTRICTS = ["Schleußig", "Plagwitz", "Lindenau", "Altlindenau", "Südvorstadt",
             "Waldstraßenviertel", "Musikviertel", "Zentrum-West", "Zentrum-Süd",
             "Gohlis", "Connewitz", "Stötteritz", "Reudnitz", "Eutritzsch", "Grünau",
             "Paunsdorf", "Möckern", "Leutzsch"]

def parse_message(text: str, source: str, source_id: str) -> Listing | None:
    """Free-text rental OFFER -> Listing candidate; None for seek-requests/chatter."""
    if SEEK_HINTS.search(text) and not OFFER_HINTS.search(text):
        return None
    rooms_m, area_m, price_m = ROOMS_RE.search(text), AREA_RE.search(text), PRICE_RE.search(text)
    is_offer = OFFER_HINTS.search(text) or (price_m and (rooms_m or area_m))
    if not is_offer:
        return _llm_fallback(text, source, source_id)
    rent_warm = rent_cold = None
    if price_m:
        value = float(price_m.group(1))
        kind = (price_m.group(2) or "").lower()
        if kind.startswith(("kalt", "холодн")):
            rent_cold = value
        else:
            rent_warm = value  # warm explicit or unlabeled -> assume warm (conservative)
    district = next((d for d in DISTRICTS if d.lower() in text.lower()), None)
    return Listing(
        source=source,
        source_id=source_id,
        url="",  # message-based listings have no URL; card shows source instead
        title=text.strip().splitlines()[0][:120],
        district=district,
        rooms=float(rooms_m.group(1).replace(",", ".")) if rooms_m else None,
        area_m2=float(area_m.group(1)) if area_m else None,
        rent_warm=rent_warm,
        rent_cold=rent_cold,
        features_text=text,
    )

def _llm_fallback(text: str, source: str, source_id: str) -> Listing | None:
    """Haiku classification for ambiguous messages; disabled without API key."""
    if not os.getenv("ANTHROPIC_API_KEY") or len(text) < 30:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=200,
            messages=[{"role": "user", "content":
                "Is this a housing RENTAL OFFER in/near Leipzig (not a search request, "
                "not chatter)? Reply ONLY JSON: {\"offer\": bool, \"rooms\": num|null, "
                "\"area_m2\": num|null, \"rent\": num|null, \"rent_kind\": \"warm\"|\"kalt\"|null, "
                "\"district\": str|null}\n\n" + text[:1500]}])
        import json
        data = json.loads(resp.content[0].text)
        if not data.get("offer"):
            return None
        return Listing(source=source, source_id=source_id, url="",
                       title=text.strip().splitlines()[0][:120],
                       district=data.get("district"),
                       rooms=data.get("rooms"), area_m2=data.get("area_m2"),
                       rent_warm=data.get("rent") if data.get("rent_kind") != "kalt" else None,
                       rent_cold=data.get("rent") if data.get("rent_kind") == "kalt" else None,
                       features_text=text)
    except Exception:
        log.warning("llm fallback failed", exc_info=True)
        return None
```

Notes: tests never hit the LLM path (no key in test env + rule-based hits); notify.build_card_text must tolerate `url=""` — add tiny guard: skip the url line when empty (adjust `test_notify` accordingly with one new assertion).

- [ ] **Step 4: pip install -e ".[dev]" (new dep) → full suite → PASS.** **Step 5:** commit `feat: message parser for TG/WhatsApp rental offers`

---

### Task 9: manual-forward handler in the bot (WhatsApp + anything)

**Files:** Modify `src/radar/main.py`; Test `tests/test_forward_handler.py`

Any plain-text message sent/forwarded to the bot → `parse_message` → pipeline-equivalent processing → card or "not recognized" reply.

- [ ] **Step 1: failing test** — `tests/test_forward_handler.py`:

```python
from types import SimpleNamespace
from radar import db as dbm
from radar.config import Criteria
from radar.main import handle_forward
from tests.test_pipeline import FakeNotifier, crit  # reuse

class FakeMsg:
    def __init__(self, text):
        self.text = text
        self.message_id = 777
        self.replies = []
    async def reply_text(self, text):
        self.replies.append(text)

async def test_forwarded_offer_creates_card(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    msg = FakeMsg("Здам 3-кімнатну 72 м² 950 € warm Schleußig, тел +49...")
    await handle_forward(msg, conn, crit(), n)
    assert n.notified == ["777"]
    assert dbm.recent_listings(conn)[0]["status"] == "notified"

async def test_chatter_gets_polite_reply(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    msg = FakeMsg("Дякую всім!")
    await handle_forward(msg, conn, crit(), n)
    assert n.notified == []
    assert "не розпізнав" in msg.replies[0]
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement** in `main.py`:

```python
from .dedup import is_cross_source_duplicate
from .filters import evaluate
from .msgparse import parse_message

async def handle_forward(message, conn, criteria, notifier) -> None:
    """Plain/forwarded text -> listing candidate -> filter -> card."""
    listing = parse_message(message.text or "", source="forward",
                            source_id=str(message.message_id))
    if listing is None:
        await message.reply_text("Не розпізнав оголошення в цьому тексті 🤷")
        return
    row_id = dbm.insert_if_new(conn, listing)
    if row_id is None:
        await message.reply_text("Це оголошення вже було.")
        return
    result = evaluate(listing, criteria)
    if not result.passed:
        dbm.set_status(conn, row_id, "filtered_out")
        await message.reply_text("Не проходить критерії: " + "; ".join(result.violations))
        return
    if is_cross_source_duplicate(listing, dbm.recent_listings(conn)):
        dbm.set_status(conn, row_id, "duplicate")
        await message.reply_text("Схоже на дубль уже баченого оголошення.")
        return
    await notifier.notify(row_id, listing, result)
    dbm.set_status(conn, row_id, "notified")

async def on_text(update, context):
    await handle_forward(update.message, context.bot_data["conn"],
                         context.bot_data["criteria"], context.bot_data["notifier"])
```

Wire in `run()`: `app.bot_data.update(criteria=criteria, notifier=notifier)` and `app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))` (import `MessageHandler, filters` from telegram.ext; alias `filters as tg_filters` to avoid clashing with `radar.filters` — use `from telegram.ext import MessageHandler, filters as tg_filters`).

- [ ] **Step 4: full suite → PASS; import OK.** **Step 5:** commit `feat: forward-to-bot listing intake`

---

### Task 10: Telegram groups reader (Telethon)

**Files:** Create `src/radar/tg_groups.py`; Modify `src/radar/main.py`, `pyproject.toml` (`telethon>=1.36`), `.env.example` (TG_API_ID, TG_API_HASH); Test `tests/test_tg_groups.py`

User prerequisites (document in README): create API credentials at my.telegram.org → `.env`; JOIN the groups with own account; set `telegram_groups: [accomodation_leipzig_ukraine]` (recommended primary; optional: UAinDE_Leipzig) in criteria.yaml. First run performs interactive Telethon login (one-time, console) → session file `radar_tg.session` (gitignore `*.session`).

- [ ] **Step 1: failing test** — the handler logic is testable without Telethon network:

`tests/test_tg_groups.py`:

```python
from radar import db as dbm
from radar.tg_groups import process_group_message
from tests.test_pipeline import FakeNotifier, crit

async def test_group_offer_message_processed(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    await process_group_message(
        chat="accomodation_leipzig_ukraine", msg_id=555,
        text="Vermiete 3-Zimmer-Wohnung 70 m² 900 € warm in Plagwitz, ab sofort",
        conn=conn, criteria=crit(), notifier=n)
    assert n.notified == ["555"]

async def test_group_chatter_ignored_silently(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    n = FakeNotifier()
    await process_group_message(chat="x", msg_id=1, text="Всім привіт!",
                                conn=conn, criteria=crit(), notifier=n)
    assert n.notified == [] and dbm.recent_listings(conn) == []
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement**

`tg_groups.py`:

```python
import logging
import os
from . import db as dbm
from .dedup import is_cross_source_duplicate
from .filters import evaluate
from .msgparse import parse_message

log = logging.getLogger("radar")

async def process_group_message(chat, msg_id, text, conn, criteria, notifier) -> None:
    """One TG group message through the standard pipeline; silent on chatter."""
    listing = parse_message(text or "", source=f"tg:{chat}", source_id=str(msg_id))
    if listing is None:
        return
    row_id = dbm.insert_if_new(conn, listing)
    if row_id is None:
        return
    result = evaluate(listing, criteria)
    if not result.passed:
        dbm.set_status(conn, row_id, "filtered_out")
        return
    if is_cross_source_duplicate(listing, dbm.recent_listings(conn)):
        dbm.set_status(conn, row_id, "duplicate")
        return
    try:
        await notifier.notify(row_id, listing, result)
    except Exception:
        log.warning("notify failed for tg message %s", msg_id, exc_info=True)
        dbm.set_status(conn, row_id, "notify_failed")
        return
    dbm.set_status(conn, row_id, "notified")

def start_group_reader(conn, criteria, notifier):
    """Attach Telethon NewMessage listeners; returns started client or None."""
    groups = criteria.telegram_groups or []
    api_id, api_hash = os.getenv("TG_API_ID"), os.getenv("TG_API_HASH")
    if not groups or not api_id or not api_hash:
        log.info("tg group reader disabled (no groups or TG_API_ID/TG_API_HASH)")
        return None
    from telethon import TelegramClient, events
    client = TelegramClient("radar_tg", int(api_id), api_hash)

    @client.on(events.NewMessage(chats=groups))
    async def _on_msg(event):
        await process_group_message(
            chat=getattr(event.chat, "username", None) or str(event.chat_id),
            msg_id=event.message.id, text=event.message.message,
            conn=conn, criteria=criteria, notifier=notifier)

    client.start()  # interactive login on first ever run
    log.info("tg group reader active for: %s", groups)
    return client
```

`main.py` in `run()` after pipeline creation: `tg_client = start_group_reader(conn, criteria, notifier)`; in the shutdown `finally`: `if tg_client: await tg_client.disconnect()`. Add `*.session` to `.gitignore`, `TG_API_ID=`/`TG_API_HASH=` to `.env.example`.

- [ ] **Step 4: pip install → full suite → PASS; import OK.** **Step 5:** commit `feat: UA telegram groups reader via telethon`

---

### Task 11: geo — travel time to school + PLZ-aware KA districts

**Files:** Create `src/radar/geo.py`; Modify `src/radar/db.py` (cache table), `src/radar/pipeline.py`, `src/radar/main.py`, `src/radar/sources/kleinanzeigen.py`, `.env.example` (GOOGLE_ROUTES_API_KEY); Test `tests/test_geo.py`

Semantics (consistent with violations/unknown): runs only for listings that passed the cheap filter. District **violation** (known non-whitelisted district) short-circuits as today — geo not consulted. District **unknown**: geo decides — travel ≤ max → pass (flag removed), travel > max → violation (drop), un-geocodable/no key → unknown flag stays. Whitelisted district: geo refines — > max → violation; API failure → pass (whitelist already vouched).

User prerequisite (README): Google Cloud key with Routes API + Geocoding not needed (Nominatim), `GOOGLE_ROUTES_API_KEY` in `.env`; without key the whole geo stage degrades to "travel_time" unknown flags.

- [ ] **Step 1: failing tests** — `tests/test_geo.py` (all network mocked):

```python
import pytest
from radar.geo import GeoChecker

class FakeTransport:
    def __init__(self, geocode=(51.33, 12.33), seconds_walk=1200, seconds_transit=600, fail=False):
        self.geocode_result, self.walk, self.transit, self.fail = geocode, seconds_walk, seconds_transit, fail
    async def geocode(self, address):
        if self.fail:
            return None
        return self.geocode_result
    async def route_seconds(self, origin, mode):
        return {"WALK": self.walk, "TRANSIT": self.transit}[mode]

async def test_within_15_by_transit_passes(tmp_path):
    g = GeoChecker(FakeTransport(seconds_walk=2400, seconds_transit=840), max_minutes=15)
    verdict, minutes = await g.check("Karl-Heine-Str. 1, Leipzig")
    assert verdict == "ok" and minutes == 14

async def test_too_far_both_modes(tmp_path):
    g = GeoChecker(FakeTransport(seconds_walk=2400, seconds_transit=1500), max_minutes=15)
    verdict, _ = await g.check("Paunsdorf X")
    assert verdict == "too_far"

async def test_ungeocodable_is_unknown(tmp_path):
    g = GeoChecker(FakeTransport(fail=True), max_minutes=15)
    verdict, minutes = await g.check("???")
    assert verdict == "unknown" and minutes is None
```

- [ ] **Step 2: run → FAIL.** **Step 3: implement**

`geo.py`:

```python
import logging
import os
import httpx

log = logging.getLogger("radar")
SCHOOL = "Könneritzstraße 47, 04229 Leipzig"  # overridden from criteria.school_address in main

class HttpTransport:
    """Nominatim geocode + Google Routes v2 durations."""
    def __init__(self, api_key: str, school_address: str):
        self.api_key = api_key
        self.school_address = school_address

    async def geocode(self, address: str) -> tuple[float, float] | None:
        params = {"q": f"{address}, Leipzig, Germany", "format": "json", "limit": 1}
        headers = {"User-Agent": "wohnung-radar/1.0 (private family apartment search)"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            r = await client.get("https://nominatim.openstreetmap.org/search", params=params)
            r.raise_for_status()
            data = r.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])

    async def route_seconds(self, origin: tuple[float, float], mode: str) -> int | None:
        body = {
            "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
            "destination": {"address": self.school_address},
            "travelMode": mode,
        }
        headers = {"X-Goog-Api-Key": self.api_key,
                   "X-Goog-FieldMask": "routes.duration"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post("https://routes.googleapis.com/directions/v2:computeRoutes",
                                  json=body, headers=headers)
            r.raise_for_status()
            routes = r.json().get("routes") or []
        if not routes:
            return None
        return int(routes[0]["duration"].rstrip("s").split(".")[0])

class GeoChecker:
    def __init__(self, transport, max_minutes: int, cache=None):
        self.transport = transport
        self.max_minutes = max_minutes
        self.cache = cache if cache is not None else {}

    async def check(self, address: str) -> tuple[str, int | None]:
        """-> ("ok"|"too_far"|"unknown", minutes|None); cached per address."""
        if address in self.cache:
            return self.cache[address]
        try:
            origin = await self.transport.geocode(address)
            if origin is None:
                result = ("unknown", None)
            else:
                best = None
                for mode in ("TRANSIT", "WALK"):
                    seconds = await self.transport.route_seconds(origin, mode)
                    if seconds is not None:
                        minutes = round(seconds / 60)
                        best = minutes if best is None else min(best, minutes)
                        if minutes <= self.max_minutes:
                            result = ("ok", minutes)
                            break
                else:
                    result = ("too_far", best) if best is not None else ("unknown", None)
        except Exception:
            log.warning("geo check failed for %s", address, exc_info=True)
            result = ("unknown", None)
        self.cache[address] = result
        return result

def build_geo_checker(criteria) -> GeoChecker | None:
    key = os.getenv("GOOGLE_ROUTES_API_KEY")
    if not key:
        log.info("geo check disabled (no GOOGLE_ROUTES_API_KEY)")
        return None
    return GeoChecker(HttpTransport(key, criteria.school_address or SCHOOL),
                      criteria.max_travel_min)
```

`pipeline.py`: `Pipeline.__init__(..., geo=None)`; in the passing branch after `evaluate`, before dedup, when `self.geo is not None`: compute `verdict, minutes = await self.geo.check(listing.address or f"{listing.district}, Leipzig")` (skip entirely and append `"travel_time"` to `result.unknown` when there is neither address nor district). Implement EXACTLY this decision table (and test it at pipeline level):

| district state | geo verdict | outcome |
|---|---|---|
| whitelisted | ok / unknown / no-geo | notify |
| whitelisted | too_far | filtered_out |
| unknown | ok | notify, drop "district" flag |
| unknown | too_far | filtered_out |
| unknown | unknown / no-geo | notify with flag (as today) |

Add pipeline tests for rows 2, 3, 4 with a FakeGeo class. `main.py`: `pipeline = Pipeline(conn, criteria, notifier, geo=build_geo_checker(criteria))`. Persist cache: `db.py` table `geocode_cache (address TEXT PRIMARY KEY, verdict TEXT, minutes INTEGER)` + load/save in GeoChecker via small `DbCache` dict-like wrapper (get/`in`/set) — test with tmp db.

`sources/kleinanzeigen.py`: accept optional `plz_districts` and, when `_district` returns None but the location text has a PLZ, use the map (registry passes `criteria.plz_districts`); also put the raw location text into `Listing.address`. Update registry factory: `KleinanzeigenSource(cfg["url"], c.plz_districts)`. Tests: "04229 Leipzig" + map → district "Schleußig"; unmapped PLZ → None + address kept.

- [ ] **Step 4: full suite → PASS.** **Step 5:** commit `feat: travel-time geo check + PLZ district mapping`

---

### Task 12: live verification + docs + release

- [ ] **Step 1:** Stop the running background instance (`Get-Process pythonw | Stop-Process`). Run one dry-run cycle (`DRY_RUN=1`, temp db like Plan 1's Task 10 script but via `build_sources`): every enabled source fetches without error; print per-source counts + status Counter. Geo/TG paths report "disabled" cleanly when keys absent.
- [ ] **Step 2:** Update `docs/ARCHITECTURE.md` (new components), `docs/DECISIONS.md` (IS24 excluded — AWS WAF; UNITAS via Immowelt; hard-tier coops deferred with correct domains; TG groups-not-channels finding; Immowelt page-1-only strategy + sort-param result; geo decision table; unlabeled message price assumed warm), `README.md` (new env vars: TG_API_ID/TG_API_HASH/GOOGLE_ROUTES_API_KEY/ANTHROPIC_API_KEY — all optional with graceful degradation; Telethon first-login; joining TG groups; forward-to-bot usage).
- [ ] **Step 3:** Full suite green; commit `docs: plan 2 — sources, geo, messaging intake`; restart background instance (`wscript WohnungRadar.vbs`) — with `DRY_RUN=0` .env intact.

---

## Deferred (future plans)

- **Plan 3 (applications + calendar):** tenant profile, DE application drafts, approve-to-send email, landlord-reply → Google Calendar, `/status`, daily digest.
- **Plan 4 (hard-tier coops):** LWB (easySquare SAPUI5 — likely needs Playwright or reverse-engineered API), Lipsia (wg-lipsia.de Angular), WBG Kontakt (wbg-kontakt.de Contao AJAX; c2_ivm_pro_api endpoint discovery). IS24 only if official API access obtained.
