# MorningGlow — App-Design

- **Datum:** 2026-08-29
- **Verantwortlich:** Andriy
- **Status:** Design freigegeben, Umsetzungsplan noch nicht geschrieben
- **Quellen:** Claude-Design-Handoff-Bundle `MorningGlow App (Remix)`; Konzeptdokument
  `App - Onboarding-Konzept - annotated.pdf` (April 2026, mit Anmerkungen der Auftraggeberseite)

## Worum es geht

Eine mobile App für Frauen in der Peri- und Menopause. Kern des Produkts ist eine
**personalisierte Morgenroutine**, die aus Modulen zusammengestellt wird — passend zum
individuellen Symptomprofil, zum Zeitbudget und zum Aktivitätslevel.

Oberflächensprache zum Start: Deutsch (Markt DACH). Ton: „sanft statt streng" — kein
Druck, alles überspringbar, keine Prozentzahlen und keine Bewertungen.

## Ausgangsmaterial

Der Handoff ist ein **Prototyp**, kein Produktionscode: React 18 UMD + Babel standalone
in `<script>`-Tags, rund 14 300 Zeilen JSX in 13 Dateien, sämtliche Module über
`Object.assign(window, …)`, Zustand ausschließlich im `localStorage` unter dem Schlüssel
`mg.profile.v1`. Ein Backend existiert nicht.

Nachgebaut wird das **visuelle Ergebnis**, nicht die interne Struktur des Prototyps.

Als Assets übernommen werden: Design-Tokens (`components.jsx`), die Domänenlogik
(`engine.jsx`), die SVG-Pfade der Icons, Logo, Plus Jakarta Sans sowie die Übungsmedien.

**Medien-Inventar (im Bundle geprüft):**

| | Vorhanden |
|---|---|
| Übungsvideos | 4 — `catcow`, `sidebend`, `fold`, `tree` |
| Anker-Videos | 2 — `glas-water`, `sunlight-window` (Wasser und Morgenlicht, keine Übungen) |
| Posenfotos | 6 — `breathe`, `catcow`, `fold`, `sidebend`, `tree`, `twist` |

Die Stufe `gentle` umfasst 5 Übungen, Video liegt für 4 davon vor: **„Stehende Drehung"
(twist) existiert nur als Foto.** Die Stufen `moderate` (6 Übungen) und `active`
(6 Übungen) haben weder Video noch Foto.

## Scope-Entscheidungen

| Frage | Entscheidung |
|---|---|
| Ziel | Produktionsreife App |
| Client | React Native + Expo (iOS und Android aus einer Codebasis) |
| Markt | DACH, nur `de`; i18n von Tag eins in der Architektur verankert |
| Konten | Zunächst anonym (Supabase Anonymous Sign-in), Kontoangebot am dritten Tag |
| Monetarisierung | Nicht in v1; das Datenbankschema ist auf Tarife vorbereitet |
| Community | Nicht in v1 (Moderation, Meldungen, Apple-Richtlinie 1.2 — ein eigenes Teilsystem) |
| Inhalte | Artikelentwürfe von Claude aus offiziellen Quellen, **verpflichtende** Freigabe durch eine Ärztin; Videos durch die Auftraggeberseite |
| Datenbank | Das Schema bildet das **vollständige** Konzeptmodell sofort ab; die Oberfläche zu den Feldern folgt schrittweise |

## Architektur

### Stack

Expo SDK 54 (RN 0.81) · expo-router · TypeScript strict · Supabase EU
(Postgres + Auth + RLS + Storage) · i18next · expo-notifications ·
Zustand + MMKV (lokaler Zustand und Offline-Betrieb) · react-native-reanimated ·
react-native-svg · expo-linear-gradient · expo-blur · expo-video

### Modulgrenzen

```
src/core/          reines TypeScript, kein React- und kein Supabase-Import
  symptoms.ts        12 Symptome, Skala 0-4, Trennung in-scope / out-of-scope
  goals.ts           6 Wirkziele + Mapping Symptom -> Ziel
  evidence.ts        6 Evidenzstufen + Sprachregelung
  catalog.ts         Modulkatalog (Varianten gentle/standard/extended)
  phase.ts           Phasen-Modifikator der Gewichtungen
  rotation.ts        wöchentliche Übungsrotation
  buildRoutine.ts    budgetbewusste Zusammenstellung
  profile.ts         Typen + zod-Schema + finalize
  __tests__/
src/ui/            Designsystem aus den MG-Tokens
src/features/      onboarding · today · ritual · discover · me
src/data/          Supabase-Client, Repositories, Offline-Queue
app/               Routen für expo-router
```

**`core` importiert weder React noch Supabase.** Alles, was entscheidet, *welche
Routine angezeigt wird*, liegt dort und ist ohne Rendering testbar. Der Kern lässt sich
später unverändert ins Backend verlagern, um Push-Nachrichten serverseitig zu erzeugen.

`src/data/` ist die einzige Schicht, die Supabase kennt. Die Features greifen auf
Repositories zu, nicht direkt auf den Client.

### Personalisierungs-Engine

Reihenfolge der Berechnung (Konzept, Abschnitt 2.8):

1. Basis-Scores der Kategorien aus dem Onboarding — Symptom × Intensität laut Gewichtungsmatrix
2. Phasen-Modifikator
3. Vorlieben-Booster (×1,5 auf gewählte Themen)
4. Nutzungsverhalten der letzten 7 Tage — **in v1 nicht angewendet** (keine Daten vorhanden)
5. Modifikator aus dem Tages-Check-in (Energie)
6. Sortierung der Kategorien nach Score
7. Zeitbudget-Filter: wie viele Slots passen hinein
8. Auswahl der Übungen unter Berücksichtigung von Rotation, Aktivitätslevel und **körperlichen Einschränkungen**
9. Abschlusselement (Tagesanker), sofern das Budget ≥ 10 Minuten beträgt
10. Kürzen, bis die Summe in das Budget passt

Unveränderliche Invarianten, aus dem Prototyp übernommen:

- **Die Anker (Wasser, Morgenlicht) sind immer dabei** und werden nie gekürzt
- Ein Modul wird zuerst **gekürzt** (extended → standard → gentle) und erst danach weggelassen
- Die Summe der Schritte überschreitet nie das angegebene Budget
- Ein Symptom aktiviert ein Ziel erst ab Intensität ≥ 2

### Sprachregelung zur Evidenz

Sechs Stufen (`hilft`, `kann_helfen`, `tut_gut`, `mechanismus`, `anker`, `reflexion`).
**Nur `hilft` darf „belegt wirksam" sagen.** Alle übrigen formulieren „kann
unterstützen". Diese Regel liegt in `core/evidence.ts` und wird durch einen Test
abgesichert: kein Modul ohne die Stufe `hilft` darf einen behauptenden Text führen.

### Out-of-Scope-Symptome

Herzbeschwerden, Libido, Blase und Scheidentrockenheit werden **nie zu einem
Routineschritt**. Sie führen zu einem Wissensbeitrag und zu einem klaren Verweis an
die Ärztin.

Das ist eine bewusste Abweichung vom Konzept: dort erhält `Herzrasen` in der Matrix
„Nervensystem 3", also eine Atemübung. Eine Atemübung als Antwort auf Herzrasen
verzögert die Abklärung. Das Verhalten des Prototyps bleibt bestehen.

## Datenmodell

Gesundheitsdaten liegen in einer **eigenen Tabelle**, getrennt vom Profil: Art. 9 DSGVO
verlangt eine eigene Rechtsgrundlage und eine eigene Einwilligung, und das eine muss
sich löschen lassen, ohne das andere zu berühren.

| Tabelle | Inhalt |
|---|---|
| `profiles` | `id` = auth.uid, Locale, Name, Zeitpunkt des Onboarding-Abschlusses |
| `health_profile` | Phase · HRT-Status · Aktivitätslevel · Aufwachfenster · Zeitbudget · Themen · **körperliche Einschränkungen** · Motivation · Routine-Erfahrung · Tagesstruktur · Schlafmuster |
| `symptom_assessments` | Verlauf der Einschätzungen (jsonb + Datum) — Grundlage der Verlaufskurve |
| `daily_checkins` | Stimmung, Energie, Hitzewallungen, Schlafqualität — einer pro Tag |
| `ritual_completions` | absolvierte Schritte, Dauer, Abschlusszeitpunkt |
| `routine_overrides` | manuell entfernte und hinzugefügte Schritte |
| `exercise_feedback` | abgeschlossen / abgebrochen / übersprungen — Grundlage des Lernens in v2 |
| `articles` · `exercises` | Inhalte in der Datenbank, nicht im Bundle |

Felder für die auf v2 verschobenen Funktionen (Motivation, Schlafmuster, Tagesstruktur,
Wochenende) werden **jetzt** angelegt, damit das Nachfüllen des Profils am fünften Tag
keine Migration erfordert.

### Was bewusst nicht in der Datenbank liegt

**Der Streak wird nicht gespeichert**, sondern aus `ritual_completions` berechnet. Ein
gespeicherter Zähler läuft zwangsläufig auseinander — nach Offline-Phasen, einem
Zeitzonenwechsel oder einer wiederholten Synchronisation. Im Prototyp ist er fest
verdrahtet (`streak = 3`); das korrekte Verhalten wurde also bisher nie definiert.

**Der Streak ist weich:** ein ausgelassener Tag setzt ihn nicht zurück. Das folgt
unmittelbar aus dem Grundsatz „sanft statt streng".

**Der Modulkatalog bleibt im Code.** Er ist mit der Zusammenstellungslogik verwachsen —
Varianten nach Stufen, Anker, kontextabhängige Evidenzstufen. Ihn in ein Admin-Interface
zu verlagern hieße, die Engine über einen Editor zerstörbar zu machen, und der Preis
eines Fehlers ist hier eine falsche Empfehlung an eine Frau mit Beschwerden. Artikel und
Übungen liegen dagegen in der Datenbank, damit Inhalte ohne App-Release ausgeliefert
werden können.

### Zugriff

RLS auf allen Tabellen: jede Nutzerin sieht ausschließlich die eigenen Zeilen.
`articles` und `exercises` sind für alle authentifizierten Nutzerinnen lesbar,
schreibbar nur über die Service-Rolle.

## Änderungen gegenüber dem Prototyp

### Körperliche Einschränkungen — Sicherheit

Der Prototyp kennt den Begriff der Einschränkung an keiner Stelle der Codebasis.
Gleichzeitig enthält die Stufe `gentle` „Baum (Balance)" — eine Gleichgewichtsübung auf
einem Bein —, und `active` enthält „Kniebeuge" und „Push-ups". Die Zielgruppe ist
45 bis 70 Jahre alt.

Gefragt wird **vor der ersten Übung**, nicht im Onboarding (so schlägt es das Konzept
selbst vor): Rücken · Knie · Schulter/Nacken · Gleichgewicht · keine Einschränkungen.
Die Angaben filtern anschließend den Übungskatalog in `buildRoutine`.

### Die Phase beginnt, die Auswahl zu beeinflussen

Im Prototyp erzeugt `phase` innerhalb von `buildRoutine` genau eine Textzeile
(`phaseNote`) und **beeinflusst die Modulauswahl nicht**. Der wichtigste Datenpunkt des
Onboardings ist damit eine Bildunterschrift.

Der Modifikator wird gemäß Konzept (Abschnitt 2.3) aktiviert: frühe Perimenopause →
Nervensystem +20 %; Perimenopause „mittendrin" → Nervensystem +30 %, Mindset +20 %;
Menopause → Wissen +20 %; Postmenopause → Bewegung +30 %, Nervensystem −10 %;
„unsicher" → Wissen +30 %.

### Themen sind keine toten Daten mehr

`profile.topics` wird in Schritt 4 des Onboardings geschrieben und danach nirgends
gelesen — `buildRoutine` sieht die Angabe nicht. Sie wird als Booster ×1,5 auf die
zugehörigen Kategorien angebunden.

### Übungsrotation

Der Prototyp zeigt jeden Tag dieselbe Routine. Das Ziel des Produkts ist eine
Gewohnheit, und ein 30 Tage lang identischer Bildschirm arbeitet diesem Ziel direkt
entgegen.

Innerhalb einer Kategorie rotieren die Übungen wöchentlich. Mindestens einmal pro Woche
erscheint eine Kategorie außerhalb der Top-Prioritäten — das „Entdeckungs-Element" des
Konzepts.

### Umstellung der Onboarding-Schritte

Das Konzept fordert „maximal 7–8 Screens, rund 2 Minuten". Der Prototyp hat formal
8 Schritte, doch Schritt 3 besteht aus drei Unterseiten zu je 4 Slidern, also
**12 Slidern hintereinander**. In zwei Minuten ist das nicht zu schaffen, und genau
hier ist der größte Abbruch zu erwarten.

Die Schritte 3 und 4 werden getauscht: zuerst die Symptom-Chips (bis zu 5), danach die
Intensität **nur für die ausgewählten**. Statt immer 12 Slidern sind es höchstens 5.

Das entspricht der Variante C2 des Konzepts selbst („Anzeige nur für die am stärksten
ausgewählten").

## Abgelehnt — mit Begründung

**Alter (A2).** Die Phase trägt dasselbe Signal, und im Algorithmus des Konzepts wird
das Alter an keiner Stelle verwendet. Personenbezogene Daten nach Art. 9 ohne jede
Verwendung — Datenminimierung verkleinert die Angriffsfläche.

**Herzrasen als Ritual** — siehe „Out-of-Scope-Symptome" oben.

**Saisonale Hydration** — von der Auftraggeberseite am Rand des Konzeptdokuments
selbst abgelehnt.

**30-Tage-Challenge.** Das Konzept bittet ausdrücklich um eine kritische Prüfung.
Bewertung: für diese Zielgruppe schädlich. Eine Challenge führt eine Alles-oder-nichts-
Logik ein — ein Tag verpasst, verloren, ausgestiegen. Das widerspricht direkt dem
Grundsatz „sanft statt streng", und Bindung entsteht eher über die Leichtigkeit der
Rückkehr nach einer Lücke als über Lückenlosigkeit. Stattdessen: ein weicher Streak,
der von einem einzelnen ausgelassenen Tag nicht zurückgesetzt wird.

## Auf v2 verschoben

Lernen aus dem Nutzungsverhalten (abgeschlossen +1 / abgebrochen −1) — setzt gesammelte
Daten voraus. Getrennte Pläne für Werktage und Wochenende. Progressives Profiling an
den Tagen 2–7 (Motivation, Routine-Erfahrung, Tagesstruktur). Unterscheidung der **Art**
der Schlafproblematik — das Konzept kennt 5 Muster, „ich wache auf und schlafe wieder
ein" und „ich liege wach" führen zu unterschiedlichen Ritualen, der Prototyp kennt nur
die Intensität. Die Kategorie „Ernährung" — in der Matrix des Konzepts vorhanden, im
Modulkatalog überhaupt nicht. Community. Abonnement.

**Der HRT-Tab mit Tracking und Verlaufskurve** ebenfalls v2. Der **HRT-Status wird
jedoch in v1 erhoben**, in Schritt 2 des Onboardings: er bestimmt die sprachliche
Rahmung in den Modulen (`mgPhaseNote`) und ob HRT-Beiträge im Wissensbereich angezeigt
werden. In v1 wird der Status also erhoben und genutzt, nur der eigene Tracking-Tab
fehlt.

Die Datenbankfelder für all das werden in v1 angelegt.

## Inhaltsumfang in v1

**Artikel — alle 9.** Drei sind im Prototyp bereits geschrieben (Östrogen, „Was ist
HRT?", HRT-Typen mit Vergleichstabelle, Arztgespräch vorbereiten, Studien & Fakten).
Sechs sind einzeilige Platzhalter; die Entwürfe entstehen aus offiziellen Quellen
(S3-Leitlinie, NAMS), die Freigabe durch eine Ärztin vor Release ist verpflichtend.

**Übungen — offene Frage.** Die Stufe `gentle` ist zu 4/5 fertig. Die Stufen `moderate`
und `active` haben überhaupt keine Medien — das sind 12 Übungen. Varianten: (a) in v1
ist nur `gentle` verfügbar, der Rest wird mit Eintreffen der Aufnahmen freigeschaltet;
(b) die Stufen 2 und 3 laufen mit Foto und Text ohne Video. Die Entscheidung liegt bei
der Auftraggeberseite und blockiert die übrige Arbeit nicht.

## Risiken der Portierung nach React Native

Stellen, an denen der Prototyp nicht wörtlich übernommen werden kann:

- **`backdropFilter: blur()`** wird in den Modalen und im Zurück-Button verwendet — in
  React Native existiert das nicht. Ersatz durch `expo-blur`: visuell nahe, aber nicht
  pixelgenau.
- **Variable Schrift.** Plus Jakarta Sans (`font-weight: 200–800` aus einer einzigen
  TTF) wird unter Android in React Native unzuverlässig unterstützt. Statt des stufenlosen
  Bereichs werden 4 statische Schnitte eingebunden.
- **Schatten.** Der Prototyp arbeitet durchgängig mit `box-shadow` in einem warmen
  Bernsteinton. Android kennt nur `elevation` — grau und ohne Farbe. Das warme Leuchten
  der Karten fällt unter Android deutlich ärmer aus; Alternative wäre, den Schatten als
  Verlauf zu zeichnen.
- Verläufe, SVG und Animationen portieren sauber: `expo-linear-gradient`,
  `react-native-svg` (die Icon-Pfade werden wörtlich übernommen), `reanimated` für den
  Atem-Pacer und die Fortschrittsringe.

## Zerlegung

v1 ist für einen einzelnen Umsetzungsplan zu groß. Die Arbeit zerfällt in Etappen mit
je eigenem Plan und eigenem Prüfpunkt:

1. **Kern** — `src/core/` vollständig, mit Tests. Ohne Oberfläche. Prüfpunkt: die
   Invarianten der Engine sind grün, einschließlich der neuen (Phase, Booster,
   Einschränkungen, Rotation).
2. **Datenbankschema** — vollständiges Konzeptmodell, RLS, Migrationen, Repositories.
   Ohne Oberfläche.
3. **Designsystem** — Tokens, Basiskomponenten, Schriften, Auflösung der drei
   RN-Risiken (Blur, Schatten, Schnitte).
4. **Onboarding** — 8 Screens mit getauschten Schritten 3 und 4.
5. **Heute + Ritual-Player** — Startbildschirm, Check-in, Schritte, Übungen, Reflexion.
6. **Wissen + Profil + Erinnerungen** — Artikelbereich, Einstellungen, Push.
7. **Release** — Konten und Synchronisation, Einwilligungen, Store-Seiten, TestFlight.

Etappe 1 und 2 können parallel zu 3 laufen, danach ist die Reihenfolge sequenziell.

## Tests

- `core/` — Unit-Tests ohne Rendering. Kritische Invarianten: Summe der Schritte
  ≤ Budget; die Anker sind immer vorhanden; kein Out-of-Scope-Symptom wird je zum
  Schritt; keine Übung widerspricht den angegebenen Einschränkungen; die Sprachregelung
  zur Evidenz.
- `src/data/` — Repository-Tests gegen ein Supabase-Testschema.
- Screens — Smoke-Tests der Navigation; die visuelle Übereinstimmung wird manuell gegen
  den Prototyp geprüft.

## Rechtliches (außerhalb des Codes, blockiert aber den Release)

Einwilligung in die Verarbeitung von Gesundheitsdaten (Art. 9) getrennt von der
allgemeinen Einwilligung. Datenschutzerklärung und Nutzungsbedingungen. Positionierung
als Wellness-Anwendung, nicht als Medizinprodukt — andernfalls greift die MDR.
Freigabe der medizinischen Inhalte durch eine Ärztin vor Release.
