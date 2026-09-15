---
name: natural-prose
description: Use when text reads as machine-written, when a client says copy "sounds like AI", or before publishing any long-form English or Ukrainian content — measures the tells with a scanner, then repairs them by rewriting sentences rather than substituting words.
---

# Natural prose

Machine-written text is rarely wrong. It is **regular**. A human writer's habits
drift with mood, subject and fatigue; density of any one construction swings from
paragraph to paragraph. A model's does not. Sixty pages arriving at the same
comma-count per hundred words is the thing a reader detects, even when they cannot
name it.

Two consequences run through everything below:

1. **Never fix by substitution.** Replacing every em dash with a comma, or every
   "rather than" with "instead of", produces prose that is regular in a *new* way
   and reads exactly as machine-set. Each repair must be a different repair.
2. **Uniformity is the defect, not the word.** An em dash is good punctuation. Nine
   per thousand words across a whole site is a fingerprint.

## Step 1 — Measure. Do not guess.

Run the scanner before editing anything:

```bash
node .claude/skills/natural-prose/scan.mjs <path> [--lang en|uk]
```

`<path>` takes a built-site directory (it reads `<p>` text out of `.html` and
ignores tables), a source directory, or single files.

Two mistakes to avoid, both made on real work:

- **Count prose only.** A first pass on priwatt.us counted 24 em dashes on a page
  and called it a tell. Twenty of them were label separators in a document
  schedule — `CSI specification — 08 88 00`. That is correct typography and
  "fixing" it damages the page. The scanner strips `<table>` and reads `<p>` only.
- **Rank by page spread, not raw count.** Five uses on one page is a voice. Five
  uses across five pages is a mould.

## Step 2 — Read what the scanner ranks first

The scanner reports two things. Take them in this order:

**Shared blocks.** A phrase on 70+ pages is one source string, and one edit fixes
all of them. This is always the cheapest and largest win — find the module, not
the pages. On priwatt.us a single CTA helper carried `If it is not that settled
yet …` onto **77 pages**. Nobody writes that sentence.

**Density.** Then work down the per-page list, worst first.

## Step 3 — The tells

### A. Phrases no native speaker writes

The real complaint behind "this sounds like AI" is usually here: constructions that
are grammatical, sound considered, and are not English. Measured examples from
production copy:

| Written | What a person writes |
|---|---|
| If it is not that settled yet | If you're not that far along |
| … is the faster route | … is quicker / just call |
| is set out on [page] | see [page] / there's a page on it |
| It is worth deciding deliberately | Worth deciding up front |
| a room that has to be supervised | a room staff have to watch |

There is no fixed list — derive it per project by reading the scanner's top phrases
aloud. If you would not say it to somebody, cut it.

### B. Constructions, with the density that gives them away

Per 1,000 words of running prose. The right column is what unedited model output
typically hits, measured across 77k words:

| Construction | Healthy | Model output |
|---|---|---|
| em dash in prose | 1–3 | 9.4 |
| `rather than` | ≤1 | 4.0 |
| it-cleft — *it is X that …* | ≤0.5 | 1.3 |
| `and it is …` appended to a clause | ≤0.3 | 1.3 |
| `which is` / `which is why` | ≤0.8 | 2.3 |
| pseudo-cleft — *What comes back is …* | ≤0.5 | 0.5–2.0 |
| three-item lists as whole sentences | occasional | every page |

Two of these need judgement rather than arithmetic, and both were learned the
hard way on a real corpus:

- **Pseudo-cleft.** A loose regex counts every noun clause — *what the material
  does in a fire*, *what the room is for* — and reports a crisis. Those are plain
  English. Only the fronted-subject form is a tell: *What comes back is a
  quotation.* On the corpus above the loose count was 118 and the real one about
  a dozen. The scanner discriminates; do not widen it back.
- **Negative definition** (*is not a …*). A page whose argument IS a correction —
  *a frosted panel is not a dark one*, *this is not security film* — has earned
  it, and removing it flattens the writing. Judge by repetition inside one page,
  not by the corpus rate.

### C. Rhythm

The hardest one, and the one that survives after every word above is fixed:
**every sentence built the same way.** Statement, comma, qualifying clause.
Or: short declarative, then a colon, then three items. When two adjacent
paragraphs have the same shape, one of them is wrong regardless of its words.

Fix by varying **length** first. A four-word sentence after a thirty-word one does
more for naturalness than any lexical change.

## Step 4 — Repair

Work in the source, never the build output. For each hit, pick a *different* move:

- Drop the qualifier entirely — usually the best option, and the one a model
  resists.
- Split into two sentences.
- Colon or semicolon where the second half explains the first.
- Rebuild the clause so the connective disappears.
- **Keep it.** Some em dashes are the point. Leaving a few is what makes the rest
  read as chosen.

Rule of thumb: if the repair took no thought, it was a substitution, and it will
read as one.

## Step 5 — Verify

Re-run the scanner. Confirm density moved into the healthy column and that no
single replacement word has itself become a new tell — check the top phrases again
after editing, not just the counts.

## Ukrainian

The constructions differ, the method does not. Common tells in machine Ukrainian:

- `є ключовим`, `відіграє важливу роль`, `варто зазначити`, `не лише … але й`
- Nominalisation where a verb belongs: *здійснює встановлення* → *встановлює*
- Uniform sentence length; absence of the short fragment a Ukrainian writer uses
  for emphasis
- Calqued English rhythm — a participial clause opening every second sentence

Pass `--lang uk` to the scanner for these patterns.

## Do not

- Do not run a global find-and-replace. Ever.
- Do not touch table cells, form labels, spec rows, or document schedules — the
  typography there is deliberate and different.
- Do not "add personality" (rhetorical questions, exclamations, second-person
  asides) to compensate. That is a second machine register, not a human one.
- Do not change a fact while changing a sentence. Verify numbers survived the edit.
