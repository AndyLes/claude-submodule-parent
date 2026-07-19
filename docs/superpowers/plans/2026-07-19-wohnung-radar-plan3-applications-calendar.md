# Wohnung-Radar Plan 3: Applications + Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-tap German viewing applications from Telegram cards (draft → approve → email where possible, ready-text+link otherwise) and landlord-reply → Google Calendar viewing appointments; plus /status and a daily digest.

**Architecture:** Same service (`projects/wohnung-radar/`, PROD is live — same restart discipline as Plan 2). New modules: `profile.py` (tenant profile config), `draft.py` (DE letter: template fill + optional Haiku polish), `contact.py` (detail-page email extraction), `mailer.py` (Gmail SMTP), `appointment.py` (reply parsing → event), `calendar_api.py` (Google Calendar OAuth + insert). Bot grows: per-card «📝 Заявка» button, draft flow callbacks, appointment confirm flow, `/status`, daily digest job.

**Reality constraints (recorded, don't fight them):**
- KA/Immowelt hide landlord emails behind portal forms → for them the flow is ready-text + deep link (user pastes; ~30 s). Auto-email only when a real address is found (coop detail pages often publish vermietung@…; forwarded WhatsApp/TG texts may include one).
- Gmail send needs `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` (Google account App Password, 2FA required) — optional; without them the email button is hidden, text flow still works.
- Calendar needs one-time OAuth (Desktop client in the same GCP project 185227412834, Calendar API enabled) → `scripts/calendar_auth.py` run once in console → `token.json` (gitignored). Optional; without it appointment flow replies with the parsed data as text.

**New statuses:** `applied` (application sent/marked), `viewing_scheduled`. Full lifecycle: new → notified → applied → viewing_scheduled (→ rejected/won manual later; NOT in this plan — YAGNI until needed).

**New deps:** `dateparser>=1.2` (de/uk/ru datetime parsing), `google-api-python-client`, `google-auth-oauthlib`.

**File structure (new):**

```
config/profile.yaml               # tenant profile + letter template (user-editable)
src/radar/profile.py              # Profile loader
src/radar/draft.py                # build_application(listing, profile) -> German text
src/radar/contact.py              # find_email(listing) -> str|None (detail-page fetch + regex)
src/radar/mailer.py               # send_application(email, subject, body) via Gmail SMTP
src/radar/appointment.py          # parse_appointment(text) -> Appointment|None
src/radar/calendar_api.py         # add_viewing_event(appointment, listing) -> event link
scripts/calendar_auth.py          # one-time OAuth console flow -> token.json
tests/test_profile.py, test_draft.py, test_contact.py, test_mailer.py,
tests/test_appointment.py, test_calendar_api.py, test_bot_flows.py, test_status_digest.py
```

---

### Task 1: Tenant profile config

**Files:** Create `config/profile.yaml`, `src/radar/profile.py`; Test `tests/test_profile.py`

- [ ] **Step 1 — failing test** `tests/test_profile.py`:

```python
from pathlib import Path
from radar.profile import load_profile

def test_profile_loads():
    p = load_profile(Path(__file__).parents[1] / "config" / "profile.yaml")
    assert p.full_name
    assert p.household
    assert p.employment
    assert "{landlord_line}" not in p.letter_template  # template has placeholders but is well-formed
    assert "{intro}" in p.letter_template and "{household}" in p.letter_template
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement**

`src/radar/profile.py`:

```python
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class Profile:
    full_name: str
    phone: str
    email: str
    household: str        # e.g. "Familie mit zwei Kindern (Schulkinder)"
    employment: str       # e.g. "festangestellt, unbefristeter Arbeitsvertrag"
    income_note: str      # e.g. "Einkommensnachweise und SCHUFA-Auskunft liegen vor"
    move_in: str          # e.g. "ab sofort" / "zum 01.09.2026"
    extra: str            # free-form German sentence(s), may be ""
    letter_template: str  # German letter with {placeholders}

def load_profile(path: Path | str) -> Profile:
    with open(path, encoding="utf-8") as f:
        return Profile(**yaml.safe_load(f))
```

`config/profile.yaml` (REAL user data is filled by the user later — ship with placeholder values that are obviously placeholders; the release task tells the user to edit):

```yaml
full_name: "Andriy Leso"
phone: "+49 XXX XXXXXXX"        # user fills
email: "andriy.leso@gmail.com"
household: "Familie mit Kind (Schulkind in Schleußig)"
employment: "festangestellt, unbefristeter Arbeitsvertrag"
income_note: "Einkommensnachweise und SCHUFA-Auskunft liegen vor und können sofort vorgelegt werden"
move_in: "ab sofort"
extra: "Wir sind eine ruhige Nichtraucher-Familie ohne Haustiere."
letter_template: |
  {landlord_line}

  {intro}

  Kurz zu uns: {household}. Ich bin {employment}. {income_note}. Einzug ist {move_in} möglich. {extra}

  Wir würden uns sehr über einen Besichtigungstermin freuen. Sie erreichen mich jederzeit unter {phone} oder per E-Mail an {email}.

  Mit freundlichen Grüßen
  {full_name}
```

- [ ] **Step 4 — PASS. Step 5 —** `git add -A; git commit -m "feat: tenant profile config"`

---

### Task 2: Application draft generator

**Files:** Create `src/radar/draft.py`; Test `tests/test_draft.py`

Template-first; optional Haiku polish (same gating pattern as msgparse `_llm_fallback`: no `ANTHROPIC_API_KEY` → pure template). LLM never invents facts — it only rewrites the intro line to reference the specific listing.

- [ ] **Step 1 — failing tests** `tests/test_draft.py` (autouse fixture deletes ANTHROPIC_API_KEY so tests are template-only):

```python
import pytest
from radar.draft import build_application
from radar.models import Listing
from radar.profile import Profile

@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

def prof():
    return Profile(full_name="Andriy Leso", phone="+49 1", email="a@b.c",
                   household="Familie mit Kind", employment="festangestellt",
                   income_note="Nachweise liegen vor", move_in="ab sofort", extra="",
                   letter_template=("{landlord_line}\n\n{intro}\n\n{household}; {employment}; "
                                    "{income_note}; {move_in}. {extra}\n{phone} {email}\n{full_name}"))

def make(**kw):
    base = dict(source="immowelt", source_id="1", url="https://x/expose/1",
                title="Schöne 3-Zimmer-Wohnung", district="Schleußig", rooms=3,
                area_m2=72, rent_cold=850)
    base.update(kw)
    return Listing(**base)

def test_template_filled_with_listing_reference():
    text = build_application(make(), prof())
    assert "Sehr geehrte Damen und Herren" in text        # default landlord line
    assert "3-Zimmer-Wohnung" in text                     # intro references the listing title
    assert "Schleußig" in text
    assert "Familie mit Kind" in text and "Andriy Leso" in text
    assert "{" not in text                                # no unfilled placeholders

def test_intro_mentions_rent_when_known():
    text = build_application(make(rent_warm=950), prof())
    assert "950" in text

def test_no_district_no_crash():
    text = build_application(make(district=None, title="Wohnung zur Miete"), prof())
    assert "{" not in text
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement**

`src/radar/draft.py`:

```python
import logging
import os
from .models import Listing
from .profile import Profile

log = logging.getLogger("radar")

def _default_intro(listing: Listing) -> str:
    where = f" in {listing.district}" if listing.district else ""
    rent = listing.rent_warm or listing.rent_cold
    rent_part = f" ({rent:.0f} € {'warm' if listing.rent_warm else 'kalt'})" if rent else ""
    return (f"mit großem Interesse habe ich Ihre Anzeige „{listing.title}“{where}"
            f"{rent_part} gesehen und bewerbe mich hiermit um die Wohnung.")

def build_application(listing: Listing, profile: Profile) -> str:
    intro = _llm_intro(listing) or _default_intro(listing)
    text = profile.letter_template.format(
        landlord_line="Sehr geehrte Damen und Herren,",
        intro=intro,
        household=profile.household,
        employment=profile.employment,
        income_note=profile.income_note,
        move_in=profile.move_in,
        extra=profile.extra,
        phone=profile.phone,
        email=profile.email,
        full_name=profile.full_name,
    )
    return text.strip()

def _llm_intro(listing: Listing) -> str | None:
    """One German intro sentence referencing the listing; None without API key/on failure."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=150,
            messages=[{"role": "user", "content":
                "Write ONE polite German sentence (formal Sie) expressing interest in this "
                "rental listing, mentioning its concrete details. No greeting, no signature, "
                "start lowercase (it follows 'Sehr geehrte Damen und Herren,'). Facts only "
                "from: " + f"title={listing.title!r}, district={listing.district!r}, "
                f"rooms={listing.rooms}, area={listing.area_m2}m², "
                f"rent_warm={listing.rent_warm}, rent_cold={listing.rent_cold}"}])
        text = resp.content[0].text.strip()
        return text if 20 < len(text) < 400 else None
    except Exception:
        log.warning("llm intro failed", exc_info=True)
        return None
```

NOTE the f-string in `_default_intro` uses `rent:.0f` — rent may be float; test covers. `_llm_intro` is blocking → caller in bot wraps via `asyncio.to_thread` (Task 3).

- [ ] **Step 4 — PASS. Step 5 —** commit `feat: german application draft generator`

---

### Task 3: Bot draft flow («📝 Заявка» button)

**Files:** Modify `src/radar/notify.py`, `src/radar/main.py`; Test `tests/test_bot_flows.py`

- [ ] **Step 1 — failing tests** `tests/test_bot_flows.py`:

```python
from types import SimpleNamespace
from radar import db as dbm
from radar.main import handle_draft_request
from radar.models import Listing
from radar.notify import build_keyboard
from tests.test_pipeline import crit
from tests.test_draft import prof

def test_card_keyboard_has_draft_button():
    kb = build_keyboard(42)
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "skip:42" in datas and "draft:42" in datas

class FakeQuery:
    def __init__(self, row_id):
        self.data = f"draft:{row_id}"
        self.replies = []
        self.answered = False
    async def answer(self, *a, **kw):
        self.answered = True
    async def message_reply(self, text, **kw):  # not used; replies go via bot.send_message fake
        pass

async def test_draft_request_generates_letter(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    row_id = dbm.insert_if_new(conn, Listing(
        source="immowelt", source_id="1", url="https://x/expose/1",
        title="3-Zimmer-Wohnung", district="Schleußig", rooms=3, area_m2=72, rent_cold=850))
    sent = []
    async def fake_send(chat_id, text, **kw):
        sent.append(text)
    await handle_draft_request(row_id, conn, prof(), fake_send, email_finder=None)
    assert any("3-Zimmer-Wohnung" in t and "Andriy Leso" in t for t in sent)
    assert any("https://x/expose/1" in t for t in sent)   # link for manual paste

async def test_draft_request_unknown_row(tmp_path):
    conn = dbm.connect(str(tmp_path / "t.db"))
    sent = []
    async def fake_send(chat_id, text, **kw):
        sent.append(text)
    await handle_draft_request(999, conn, prof(), fake_send, email_finder=None)
    assert any("не знайшов" in t.lower() for t in sent)
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement**

`notify.py` `build_keyboard`:

```python
def build_keyboard(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📝 Заявка", callback_data=f"draft:{listing_id}"),
        InlineKeyboardButton("Пропустити", callback_data=f"skip:{listing_id}"),
    ]])
```

`main.py` — add (db needs a row fetch: add `def get_listing(conn, listing_id)` to db.py returning row or None + `listing_from_row` reuse):

```python
async def handle_draft_request(row_id, conn, profile, send, email_finder) -> None:
    """Generate the German application for a stored listing and send it to the owner chat."""
    row = dbm.get_listing(conn, row_id)
    if row is None:
        await send(chat_id=None, text="Не знайшов це оголошення в базі 🤷")
        return
    listing = dbm.listing_from_row(row)
    text = await asyncio.to_thread(build_application, listing, profile)
    email = None
    if email_finder is not None:
        email = await email_finder(listing)
    lines = [f"📝 Чернетка заявки для: {listing.title}", "", text, ""]
    if email:
        lines.append(f"✉️ Знайдено email: {email} — надіслати?")
    elif listing.url:
        lines.append(f"🔗 Вставте текст у форму: {listing.url}")
    await send(chat_id=None, text="\n".join(lines),
               reply_markup=draft_actions_keyboard(row_id, email))
```

(Status stays `notified` at this step — it flips to `applied` only via the applied/send callbacks.) `draft_actions_keyboard(row_id, email)` in notify.py: row of [✉️ Надіслати email] (only when email), [✅ Позначено надісланою] (callback "applied:<id>"), plain-text guidance otherwise. `on_draft` callback handler (pattern `^draft:`) extracts id, calls handle_draft_request with a `send` closure over `context.bot.send_message(chat_id=...)` and email_finder from Task 4 (None until wired). `on_applied` handler (pattern `^applied:`) → set_status applied + answer "Зафіксовано ✅". Owner guard `_is_owner` on all new handlers. Register handlers in run(). The fake `send` in tests takes `chat_id=None` — make the closure signature `send(chat_id, text, **kw)` and the real one substitute the owner chat id.

- [ ] **Step 4 — full suite PASS; import OK. Step 5 —** commit `feat: application draft flow in bot`

---

### Task 4: Detail-page email extraction

**Files:** Create `src/radar/contact.py`; Test `tests/test_contact.py`

- [ ] **Step 1 — failing tests** (pure parsing + a fetch seam like WogetraSource._get):

```python
from radar.contact import extract_email, EmailFinder

def test_extracts_mailto():
    assert extract_email('<a href="mailto:vermietung@bgl.de">Kontakt</a>') == "vermietung@bgl.de"

def test_extracts_plain_email_near_kontakt():
    html = "<div>Kontakt: wohnen@vlw-eg.de Telefon 0341...</div>"
    assert extract_email(html) == "wohnen@vlw-eg.de"

def test_ignores_image_emails_and_junk():
    assert extract_email("<p>foo@2x.png bar</p>") is None

def test_no_email_none():
    assert extract_email("<p>Nur Telefon: 0341 123</p>") is None

async def test_finder_fetches_detail_page():
    class F(EmailFinder):
        async def _get(self, url):
            return '<a href="mailto:info@coop.de">mail</a>'
    from radar.models import Listing
    l = Listing(source="bgl", source_id="1", url="https://bgl.de/x", title="t")
    assert await F()(l) == "info@coop.de"

async def test_finder_skips_message_sources():
    class F(EmailFinder):
        async def _get(self, url):
            raise AssertionError("must not fetch")
    from radar.models import Listing
    l = Listing(source="forward", source_id="1", url="", title="t",
                features_text="Пишіть на owner@gmail.com")
    assert await F()(l) == "owner@gmail.com"   # from features_text, no fetch
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement** `contact.py`: `EMAIL_RE = r"[\w.+-]+@[\w-]+\.[\w.]{2,}"`; `extract_email(html)` — prefer `mailto:` hrefs; else regex over visible text, reject matches ending in common image/file extensions (`.png/.jpg/.svg/...`); lowercase result. `class EmailFinder`: `async __call__(listing)` — if listing.url empty or source in ("forward",) or source.startswith("tg:") → search `listing.features_text` only; else fetch detail page via overridable `async _get(url)` (httpx, browser UA, 20s, raise_for_status; on exception → log.debug → None) and extract. Per-call, no cache (volume tiny — one click).
- [ ] **Step 4 — PASS. Step 5 —** commit `feat: landlord email extraction`

---

### Task 5: Gmail sender + wiring the email button

**Files:** Create `src/radar/mailer.py`; Modify `src/radar/main.py`, `.env.example`; Test `tests/test_mailer.py`

- [ ] **Step 1 — failing tests** (SMTP faked via seam):

```python
from radar.mailer import GmailMailer

def test_disabled_without_creds(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    assert GmailMailer.from_env() is None

async def test_send_builds_proper_message(monkeypatch):
    sent = {}
    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, user, pw): sent["login"] = user
        def send_message(self, msg): sent["msg"] = msg
    m = GmailMailer("me@gmail.com", "apppw", smtp_factory=FakeSMTP)
    await m.send("landlord@coop.de", "Bewerbung: 3-Zimmer-Wohnung", "Sehr geehrte...")
    assert sent["login"] == "me@gmail.com"
    assert sent["msg"]["To"] == "landlord@coop.de"
    assert sent["msg"]["Subject"].startswith("Bewerbung")
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement** `mailer.py`: `GmailMailer(address, app_password, smtp_factory=smtplib.SMTP_SSL)`; `from_env()` → None without both vars; `async send(to, subject, body)` → `asyncio.to_thread` around the blocking SMTP block (`smtp_factory("smtp.gmail.com", 465)` context manager, login, `EmailMessage` utf-8 with From/To/Subject/body, send_message). `main.py`: build mailer in run(); in the draft flow add `send_email:<id>` callback — draft text is regenerated (deterministic template; if LLM key present regenerate may differ — acceptable) or better: store the last draft per row in a small in-memory dict `pending_drafts[row_id] = (text, email)` when the draft is shown, and the send handler uses it (drop after send). On send success → set_status applied + confirm message; on failure → log + apologetic message, status unchanged. `.env.example` += `GMAIL_ADDRESS=`, `GMAIL_APP_PASSWORD=`. Tests for the callback path analogous to test_bot_flows (fake mailer recording sends).
- [ ] **Step 4 — PASS. Step 5 —** commit `feat: gmail application sending`

---

### Task 6: Appointment parsing

**Files:** Create `src/radar/appointment.py`; Modify `pyproject.toml` (dateparser); Test `tests/test_appointment.py`

- [ ] **Step 1 — failing tests**:

```python
from datetime import datetime
from radar.appointment import parse_appointment

def test_german_reply_parsed():
    a = parse_appointment(
        "Guten Tag, gerne laden wir Sie zur Besichtigung am 24.07.2026 um 15:30 ein. "
        "Treffpunkt: Karl-Heine-Straße 12, 04229 Leipzig.",
        now=datetime(2026, 7, 19, 12, 0))
    assert a is not None
    assert a.when == datetime(2026, 7, 24, 15, 30)
    assert "Karl-Heine" in a.address

def test_ua_forward_parsed():
    a = parse_appointment("Перегляд у вівторок о 14:00, адреса Hartzstr. 14",
                          now=datetime(2026, 7, 19, 12, 0))  # Sunday
    assert a.when == datetime(2026, 7, 21, 14, 0)

def test_no_datetime_none():
    assert parse_appointment("Дякую за заявку, ми з вами зв'яжемось",
                             now=datetime(2026, 7, 19)) is None

def test_past_datetime_none():
    assert parse_appointment("Besichtigung am 01.01.2020 um 10:00",
                             now=datetime(2026, 7, 19)) is None
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement** `appointment.py`: `@dataclass Appointment(when: datetime, address: str|None, raw: str)`. `parse_appointment(text, now=None)`: gate on viewing keywords (`besichtigung|termin|перегляд|огляд|просмотр|зустріч|viewing`) OR explicit date+time pattern; use `dateparser.search.search_dates(text, languages=["de","uk","ru"], settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})`; pick the first result with a time component (hour/minute not both zero OR text match `\d{1,2}[:.]\d{2}`); reject if <= now. Address: regex for street-like pattern (`[A-ZÄÖÜ][\wäöüß.-]+(?:straße|strasse|str\.|weg|allee|platz|ring)\s*\d+[a-z]?` case-insensitive) else None. If dateparser's behavior differs from the tests (verify!), adapt implementation, not intent; report deviations. Add `dateparser>=1.2` dep + pip install.
- [ ] **Step 4 — PASS. Step 5 —** commit `feat: viewing appointment parser`

---

### Task 7: Google Calendar integration

**Files:** Create `src/radar/calendar_api.py`, `scripts/calendar_auth.py`; Modify `.gitignore`, `pyproject.toml`; Test `tests/test_calendar_api.py`

- [ ] **Step 1 — failing tests** (Google client faked via seam; no network):

```python
from datetime import datetime
from radar.appointment import Appointment
from radar.calendar_api import CalendarClient, build_event

def test_build_event_shape():
    a = Appointment(when=datetime(2026, 7, 24, 15, 30), address="Karl-Heine-Str. 12", raw="...")
    ev = build_event(a, listing_title="3-Zi Schleußig", listing_url="https://x/1")
    assert ev["summary"].startswith("Перегляд квартири")
    assert "3-Zi Schleußig" in ev["summary"]
    assert ev["location"] == "Karl-Heine-Str. 12"
    assert ev["start"]["dateTime"].startswith("2026-07-24T15:30")
    assert ev["start"]["timeZone"] == "Europe/Berlin"
    assert "https://x/1" in ev["description"]
    assert ev["reminders"]["overrides"][0]["minutes"] == 60

def test_client_disabled_without_token(tmp_path):
    assert CalendarClient.from_token(tmp_path / "nope.json") is None
```

- [ ] **Step 2 — run → FAIL.** **Step 3 — implement** `calendar_api.py`: `build_event(appointment, listing_title, listing_url)` → dict per Calendar API v3 (summary "Перегляд квартири: <title>", location, description with url + raw text, start/end (end = +45 min), timeZone Europe/Berlin, reminders overrides popup 60 min). `CalendarClient`: `from_token(path)` → None if file missing; else load `google.oauth2.credentials.Credentials.from_authorized_user_file` (scope `https://www.googleapis.com/auth/calendar.events`), refresh if expired; `async insert(event)` → `asyncio.to_thread` around `build("calendar","v3",credentials=...).events().insert(calendarId="primary", body=event).execute()`, returns htmlLink. `scripts/calendar_auth.py`: console script — `InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes).run_local_server(port=0)` → save `token.json` at repo root; prints instructions if client_secret.json missing (download from GCP Console → Credentials → OAuth client ID → Desktop app). `.gitignore` += `token.json`, `client_secret.json`. Deps: `google-api-python-client>=2.100`, `google-auth-oauthlib>=1.2` + pip install.
- [ ] **Step 4 — PASS. Step 5 —** commit `feat: google calendar client`

---

### Task 8: Appointment flow in bot

**Files:** Modify `src/radar/main.py`; Test `tests/test_bot_flows.py` (extend)

Routing change in `handle_forward`: BEFORE listing-parse, try `parse_appointment(text)` — if found, reply with a confirm card («📅 Додати в календар: <дата> <час> <адреса?>» + buttons [✅ Так / callback `cal:<pending_key>`] [❌ Ні, це оголошення / `callisting:<pending_key>`]); store pending appointment + original text in an in-memory dict keyed by a short uuid. `cal:` handler → CalendarClient (None → reply "Календар не підключено — запустіть scripts/calendar_auth.py"; else insert → reply з посиланням на подію) and try to link the appointment to a recent `applied` listing by fuzzy title/address match (best-effort: if exactly one applied row matches address fragment → set_status viewing_scheduled). `callisting:` handler → run the original text through the normal listing intake path (reuse handle_forward's listing branch — refactor the listing part into `_handle_forward_listing(text, ...)` so both call sites share it).

- [ ] **Step 1 — failing tests**: forward with Besichtigung text → confirm reply (no listing insert); `cal:` confirm with fake calendar → event inserted + reply contains link; `cal:` without calendar → підказка про calendar_auth; `callisting:` → text lands as listing (row inserted). Owner-guard on new handlers.
- [ ] **Step 2 — run → FAIL. Step 3 — implement per above. Step 4 — PASS. Step 5 —** commit `feat: viewing appointment flow`

---

### Task 9: /status + daily digest

**Files:** Modify `src/radar/main.py`, `src/radar/db.py`; Test `tests/test_status_digest.py`

- [ ] **Step 1 — failing tests**: `db.status_counts(conn)` → dict; `build_status_text(counts)` → UA text with counts (нові/сповіщені/заявки/перегляди/відсіяні today+total); `build_digest_text(conn, since_hours=24)` → "за добу: X нових, Y пройшли фільтри..." including titles of notified-in-window listings (query by created_at). Test with seeded rows.
- [ ] **Step 2 — run → FAIL. Step 3 — implement**: db helpers (`status_counts`, `recent_notified(conn, since_hours)` using created_at); `/status` CommandHandler (owner-guarded) → build_status_text; digest: APScheduler cron job daily 20:00 Europe/Berlin → notifier.alert(build_digest_text(...)) (skip send if nothing new — no noise). Register in run().
- [ ] **Step 4 — PASS. Step 5 —** commit `feat: /status command + daily digest`

---

### Task 10: Docs + live verification + release

- [ ] **Step 1 — docs**: README (profile.yaml editing — user MUST fill phone; GMAIL_ADDRESS/GMAIL_APP_PASSWORD app-password steps; calendar: enable Calendar API in GCP project 185227412834 → OAuth Desktop client → download client_secret.json to repo root → run `.venv\Scripts\python scripts\calendar_auth.py` once in console; new buttons/commands guide). ARCHITECTURE (new modules, flows). DECISIONS (portal-form reality → text+link primary path; email auto-send scope; in-memory pending drafts/appointments — lost on restart, acceptable: user re-taps; digest 20:00; statuses added).
- [ ] **Step 2 — suite green; dry checks**: import radar.main; profile loads; a synthetic end-to-end draft generation via test already covers. NO live Gmail/Calendar test without user creds — verify graceful-disabled paths in log instead.
- [ ] **Step 3 — release**: commit docs `docs: plan 3 — applications + calendar`; restart production (same stop/wscript/verify procedure: 5 jobs + no tracebacks + digest job registered + bot handlers registered). Remind user: fill `config/profile.yaml` phone, optionally set Gmail vars + run calendar_auth.

---

## Deferred

- rejected/won statuses + outcome tracking (add when first applications get replies)
- Persistent pending-draft store (in-memory is fine for single user)
- Plan 4: hard coops (LWB easySquare, Lipsia, WBG Kontakt) via headless; IS24 via official API only
