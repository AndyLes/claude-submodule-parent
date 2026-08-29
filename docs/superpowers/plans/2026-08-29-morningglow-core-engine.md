# MorningGlow Core Engine — Implementation Plan (Etappe 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/core/` — the complete personalization engine as pure TypeScript with unit tests, no React and no Supabase.

**Architecture:** Scoring runs on the concept's five categories (Nervensystem, Bewegung, Ernährung, Mindset, Wissen). A pipeline of pure functions transforms base scores through phase, preference and check-in modifiers, then `buildRoutine` fills budget slots from the ranked categories. Every function is total, deterministic and takes its inputs explicitly — no clocks, no randomness, no I/O.

**Tech Stack:** TypeScript 5 (strict), vitest, zod.

**Spec:** `docs/superpowers/specs/2026-08-29-morningglow-design.md`

**Language note:** identifiers and comments in English; user-facing strings in German, exactly as they appear in the prototype.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/core/symptoms.ts` | The 12 symptoms, severity scale, in/out-of-scope split |
| `src/core/categories.ts` | The 5 categories and the symptom × category weighting matrix |
| `src/core/goals.ts` | The 6 Wirkziele — labels and colors for the UI only |
| `src/core/evidence.ts` | The 6 evidence levels and the efficacy-claim rule |
| `src/core/profile.ts` | Profile types + zod schema + `finalizeProfile` |
| `src/core/scoring.ts` | Base scores from symptom × severity |
| `src/core/phase.ts` | Phase modifier |
| `src/core/preferences.ts` | Preference booster (F1) |
| `src/core/checkin.ts` | Daily energy modifier |
| `src/core/exercises.ts` | Exercise catalog with contraindications |
| `src/core/restrictions.ts` | Exercise filter by physical restrictions |
| `src/core/rotation.ts` | Deterministic weekly rotation |
| `src/core/catalog.ts` | Module catalog |
| `src/core/buildRoutine.ts` | Budget-aware assembly |
| `src/core/index.ts` | Public surface of the package |

Each file exports types and pure functions only. `buildRoutine.ts` is the single composition point; nothing else imports it.

---

## Task 1: Project scaffold

**Files:**
- Create: `projects/morningglow/package.json`
- Create: `projects/morningglow/tsconfig.json`
- Create: `projects/morningglow/vitest.config.ts`
- Create: `projects/morningglow/.gitignore`
- Test: `projects/morningglow/src/core/__tests__/scaffold.test.ts`

- [ ] **Step 1: Create the directory and initialize git**

```bash
mkdir -p projects/morningglow/src/core/__tests__
cd projects/morningglow
git init
```

- [ ] **Step 2: Write `package.json`**

```json
{
  "name": "morningglow",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "typescript": "^5.6.3",
    "vitest": "^2.1.8"
  },
  "dependencies": {
    "zod": "^3.23.8"
  }
}
```

- [ ] **Step 3: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["vitest/globals"]
  },
  "include": ["src"]
}
```

`noUncheckedIndexedAccess` is deliberate: the engine indexes into record lookups constantly, and this forces every lookup to be handled rather than assumed.

- [ ] **Step 4: Write `vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    include: ['src/**/*.test.ts'],
  },
});
```

- [ ] **Step 5: Write `.gitignore`**

```
node_modules/
dist/
.expo/
*.log
.env*
```

- [ ] **Step 6: Write a scaffold test that must fail**

`src/core/__tests__/scaffold.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { CORE_VERSION } from '../index';

describe('scaffold', () => {
  it('exposes a core version', () => {
    expect(CORE_VERSION).toBe('1.0.0');
  });
});
```

- [ ] **Step 7: Install and run the test to verify it fails**

```bash
npm install
npm test
```

Expected: FAIL — `Failed to resolve import "../index"`.

- [ ] **Step 8: Create `src/core/index.ts`**

```ts
export const CORE_VERSION = '1.0.0';
```

- [ ] **Step 9: Run tests and typecheck**

```bash
npm test && npm run typecheck
```

Expected: 1 test passes, typecheck clean.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "chore: scaffold core package with vitest and strict TypeScript"
```

---

## Task 2: Symptoms

**Files:**
- Create: `src/core/symptoms.ts`
- Test: `src/core/__tests__/symptoms.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import {
  SYMPTOMS, SEVERITY_LABELS, SEVERITY_THRESHOLD,
  symptomById, inScopeSymptoms, outOfScopeSymptoms,
} from '../symptoms';

describe('symptoms', () => {
  it('holds 12 symptoms', () => {
    expect(SYMPTOMS).toHaveLength(12);
  });

  it('splits 8 in-scope and 4 out-of-scope', () => {
    expect(inScopeSymptoms()).toHaveLength(8);
    expect(outOfScopeSymptoms()).toHaveLength(4);
  });

  it('gives every out-of-scope symptom a referral text', () => {
    for (const s of outOfScopeSymptoms()) {
      expect(s.referral).toBeTruthy();
    }
  });

  it('gives no in-scope symptom a referral text', () => {
    for (const s of inScopeSymptoms()) {
      expect(s.referral).toBeUndefined();
    }
  });

  it('routes heart complaints out of scope', () => {
    expect(symptomById('heart')?.scope).toBe('out');
  });

  it('labels the 0-4 scale with 5 German labels', () => {
    expect(SEVERITY_LABELS).toEqual([
      'gar nicht', 'selten', 'manchmal', 'oft', 'sehr oft',
    ]);
    expect(SEVERITY_THRESHOLD).toBe(2);
  });

  it('returns undefined for an unknown id', () => {
    expect(symptomById('nope' as never)).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- symptoms
```

Expected: FAIL — cannot resolve `../symptoms`.

- [ ] **Step 3: Write `src/core/symptoms.ts`**

```ts
export type InScopeSymptomId =
  | 'depressed' | 'irritable' | 'anxious' | 'fatigue'
  | 'hotFlashes' | 'sleep' | 'joints' | 'weight';

export type OutOfScopeSymptomId = 'heart' | 'sexual' | 'bladder' | 'vaginal';

export type SymptomId = InScopeSymptomId | OutOfScopeSymptomId;

export type SymptomGroup = 'inner' | 'bodysleep' | 'medical';
export type SymptomScope = 'in' | 'out';

/** Severity on the internal 0-4 scale. Never surfaced as "MRS" in the UI. */
export type Severity = 0 | 1 | 2 | 3 | 4;

export interface SymptomItem {
  readonly id: SymptomId;
  readonly label: string;
  readonly short: string;
  readonly group: SymptomGroup;
  readonly scope: SymptomScope;
  /** Present only on out-of-scope symptoms: the referral shown instead of an exercise. */
  readonly referral?: string;
}

export const SEVERITY_LABELS = [
  'gar nicht', 'selten', 'manchmal', 'oft', 'sehr oft',
] as const;

/** A symptom contributes to scoring only from this severity upward. */
export const SEVERITY_THRESHOLD = 2;

export const SYMPTOMS: readonly SymptomItem[] = [
  { id: 'depressed',  label: 'Niedergeschlagenheit',          short: 'Stimmung',       group: 'inner',     scope: 'in' },
  { id: 'irritable',  label: 'Reizbarkeit',                   short: 'Reizbarkeit',    group: 'inner',     scope: 'in' },
  { id: 'anxious',    label: 'Innere Unruhe & Ängstlichkeit', short: 'Unruhe',         group: 'inner',     scope: 'in' },
  { id: 'fatigue',    label: 'Erschöpfung & Konzentration',   short: 'Erschöpfung',    group: 'inner',     scope: 'in' },
  { id: 'hotFlashes', label: 'Hitzewallungen & Schwitzen',    short: 'Hitzewallungen', group: 'bodysleep', scope: 'in' },
  { id: 'sleep',      label: 'Schlafprobleme',                short: 'Schlaf',         group: 'bodysleep', scope: 'in' },
  { id: 'joints',     label: 'Gelenk- & Muskelbeschwerden',   short: 'Gelenke',        group: 'bodysleep', scope: 'in' },
  { id: 'weight',     label: 'Gewichtszunahme',               short: 'Gewicht',        group: 'bodysleep', scope: 'in' },
  {
    id: 'heart', label: 'Herzbeschwerden', short: 'Herz', group: 'medical', scope: 'out',
    referral: 'Herzbeschwerden können in der Menopause auftreten. Eine Morgenroutine kann hier nicht helfen – Deine Ärztin ist die richtige Adresse.',
  },
  {
    id: 'sexual', label: 'Sexualität & Libido', short: 'Sexualität', group: 'medical', scope: 'out',
    referral: 'Veränderungen bei Lust und Sexualität sind häufig. Dazu findest Du Wissen – und Wege, ärztlich Unterstützung zu finden.',
  },
  {
    id: 'bladder', label: 'Harnwege & Blase', short: 'Blase', group: 'medical', scope: 'out',
    referral: 'Blasen- und Harnwegsthemen lassen sich gut ärztlich behandeln. Wir verweisen Dich an die richtige Stelle.',
  },
  {
    id: 'vaginal', label: 'Scheidentrockenheit', short: 'Trockenheit', group: 'medical', scope: 'out',
    referral: 'Scheidentrockenheit ist gut behandelbar. Dazu gibt es Wissen und einen Verweis zu Deiner Ärztin.',
  },
];

export function symptomById(id: SymptomId): SymptomItem | undefined {
  return SYMPTOMS.find((s) => s.id === id);
}

export function inScopeSymptoms(): SymptomItem[] {
  return SYMPTOMS.filter((s) => s.scope === 'in');
}

export function outOfScopeSymptoms(): SymptomItem[] {
  return SYMPTOMS.filter((s) => s.scope === 'out');
}

/** Severity map as stored on the profile. Absent means 0. */
export type SymptomScores = Partial<Record<SymptomId, Severity>>;

export function severityOf(scores: SymptomScores, id: SymptomId): Severity {
  return scores[id] ?? 0;
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- symptoms
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/symptoms.ts src/core/__tests__/symptoms.test.ts
git commit -m "feat(core): symptom catalog with in/out-of-scope split"
```

---

## Task 3: Categories and the weighting matrix

The matrix comes from the concept document, section 2.2. Row alignment is verified by the worked example the document itself supplies — that example becomes a test.

**Files:**
- Create: `src/core/categories.ts`
- Test: `src/core/__tests__/categories.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { CATEGORIES, WEIGHTS, CONCEPT_ROWS, emptyScores } from '../categories';
import { inScopeSymptoms } from '../symptoms';

describe('categories', () => {
  it('holds the 5 concept categories', () => {
    expect(CATEGORIES).toEqual([
      'nervensystem', 'bewegung', 'ernaehrung', 'mindset', 'wissen',
    ]);
  });

  it('weights every in-scope symptom', () => {
    for (const s of inScopeSymptoms()) {
      expect(WEIGHTS[s.id as keyof typeof WEIGHTS]).toBeDefined();
    }
  });

  it('keeps every weight within the concept range 0-3', () => {
    for (const row of Object.values(WEIGHTS)) {
      for (const w of Object.values(row)) {
        expect(w).toBeGreaterThanOrEqual(0);
        expect(w).toBeLessThanOrEqual(3);
      }
    }
  });

  it('reproduces the worked example from the concept document', () => {
    // "Schlafstörungen (4/5) und Erschöpfung (3/5)":
    //   Nervensystem (3x4)+(2x3)=18, Bewegung (1x4)+(3x3)=13, Mindset (2x4)+(1x3)=11
    // Checked against CONCEPT_ROWS, not WEIGHTS: the production `fatigue` row
    // merges Erschöpfung with Brain Fog and so no longer matches the example.
    const sleep = CONCEPT_ROWS.schlafstoerungen;
    const fatigue = CONCEPT_ROWS.erschoepfung;
    expect(sleep.nervensystem * 4 + fatigue.nervensystem * 3).toBe(18);
    expect(sleep.bewegung * 4 + fatigue.bewegung * 3).toBe(13);
    expect(sleep.mindset * 4 + fatigue.mindset * 3).toBe(11);
  });

  it('merges Erschöpfung and Brain Fog by column maximum', () => {
    expect(WEIGHTS.fatigue).toEqual({
      nervensystem: 2, bewegung: 3, ernaehrung: 2, mindset: 2, wissen: 1,
    });
  });

  it('gives depressed and irritable the same row', () => {
    expect(WEIGHTS.depressed).toEqual(WEIGHTS.irritable);
  });

  it('starts every category at zero', () => {
    expect(emptyScores()).toEqual({
      nervensystem: 0, bewegung: 0, ernaehrung: 0, mindset: 0, wissen: 0,
    });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- categories
```

Expected: FAIL — cannot resolve `../categories`.

- [ ] **Step 3: Write `src/core/categories.ts`**

The merge of Erschöpfung and Brain Fog changes the Mindset column for `fatigue`. To keep the document's example verifiable, both rows are exported: `WEIGHTS` holds the merged production rows, `CONCEPT_ROWS` holds the document verbatim.

```ts
import type { InScopeSymptomId } from './symptoms';

export const CATEGORIES = [
  'nervensystem', 'bewegung', 'ernaehrung', 'mindset', 'wissen',
] as const;

export type CategoryId = (typeof CATEGORIES)[number];

export type CategoryScores = Record<CategoryId, number>;

export function emptyScores(): CategoryScores {
  return { nervensystem: 0, bewegung: 0, ernaehrung: 0, mindset: 0, wissen: 0 };
}

/**
 * The matching table from the concept document, section 2.2, verbatim.
 * Kept separate from WEIGHTS so the document's worked example stays checkable
 * after the Erschöpfung/Brain-Fog merge.
 */
export const CONCEPT_ROWS = {
  schlafstoerungen:      { nervensystem: 3, bewegung: 1, ernaehrung: 1, mindset: 2, wissen: 2 },
  hitzewallungen:        { nervensystem: 2, bewegung: 1, ernaehrung: 2, mindset: 1, wissen: 3 },
  erschoepfung:          { nervensystem: 2, bewegung: 3, ernaehrung: 2, mindset: 1, wissen: 1 },
  stimmungsschwankungen: { nervensystem: 2, bewegung: 2, ernaehrung: 1, mindset: 3, wissen: 1 },
  brainFog:              { nervensystem: 1, bewegung: 3, ernaehrung: 2, mindset: 2, wissen: 1 },
  gelenkschmerzen:       { nervensystem: 1, bewegung: 3, ernaehrung: 1, mindset: 1, wissen: 2 },
  gewichtszunahme:       { nervensystem: 1, bewegung: 3, ernaehrung: 3, mindset: 1, wissen: 2 },
  innereUnruhe:          { nervensystem: 3, bewegung: 2, ernaehrung: 1, mindset: 2, wissen: 1 },
  trockeneHaut:          { nervensystem: 0, bewegung: 1, ernaehrung: 3, mindset: 0, wissen: 2 },
  herzrasen:             { nervensystem: 3, bewegung: 1, ernaehrung: 1, mindset: 2, wissen: 2 },
} as const satisfies Record<string, CategoryScores>;

/** Per-column maximum of two concept rows. */
function mergeRows(a: CategoryScores, b: CategoryScores): CategoryScores {
  return {
    nervensystem: Math.max(a.nervensystem, b.nervensystem),
    bewegung:     Math.max(a.bewegung,     b.bewegung),
    ernaehrung:   Math.max(a.ernaehrung,   b.ernaehrung),
    mindset:      Math.max(a.mindset,      b.mindset),
    wissen:       Math.max(a.wissen,       b.wissen),
  };
}

/**
 * Production weights, keyed by our symptom ids.
 *
 * Two deliberate departures from the document:
 *  - `fatigue` is "Erschöpfung & Konzentration" and covers two concept rows,
 *    so it takes the per-column maximum of both.
 *  - "Stimmungsschwankungen" is one concept row; we split it into `depressed`
 *    and `irritable`, which therefore share it.
 *
 * "Trockene Haut" and "Herzrasen" have no entry: both are out-of-scope and
 * never become a routine step.
 */
export const WEIGHTS: Record<InScopeSymptomId, CategoryScores> = {
  sleep:      { ...CONCEPT_ROWS.schlafstoerungen },
  hotFlashes: { ...CONCEPT_ROWS.hitzewallungen },
  fatigue:    mergeRows(CONCEPT_ROWS.erschoepfung, CONCEPT_ROWS.brainFog),
  depressed:  { ...CONCEPT_ROWS.stimmungsschwankungen },
  irritable:  { ...CONCEPT_ROWS.stimmungsschwankungen },
  anxious:    { ...CONCEPT_ROWS.innereUnruhe },
  joints:     { ...CONCEPT_ROWS.gelenkschmerzen },
  weight:     { ...CONCEPT_ROWS.gewichtszunahme },
};
```

- [ ] **Step 4: Run tests**

```bash
npm test -- categories
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/categories.ts src/core/__tests__/categories.test.ts
git commit -m "feat(core): concept weighting matrix with verified row alignment"
```

---

## Task 4: Evidence levels and the efficacy-claim rule

**Files:**
- Create: `src/core/evidence.ts`
- Test: `src/core/__tests__/evidence.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { EVIDENCE, EVIDENCE_KEYS, mayClaimEfficacy } from '../evidence';

describe('evidence', () => {
  it('holds the 6 levels', () => {
    expect(EVIDENCE_KEYS).toHaveLength(6);
  });

  it('lets exactly one level claim efficacy', () => {
    const claiming = EVIDENCE_KEYS.filter((k) => EVIDENCE[k].claimsEfficacy);
    expect(claiming).toEqual(['hilft']);
  });

  it('exposes the rule as a predicate', () => {
    expect(mayClaimEfficacy('hilft')).toBe(true);
    expect(mayClaimEfficacy('kann_helfen')).toBe(false);
    expect(mayClaimEfficacy('tut_gut')).toBe(false);
  });

  it('never says "wirksam" on a level that may not claim efficacy', () => {
    for (const key of EVIDENCE_KEYS) {
      if (!EVIDENCE[key].claimsEfficacy) {
        expect(EVIDENCE[key].label.toLowerCase()).not.toContain('wirksam');
        expect(EVIDENCE[key].label.toLowerCase()).not.toContain('belegt');
      }
    }
  });

  it('marks the feel-good level as non-evidential in its subtext', () => {
    expect(EVIDENCE.tut_gut.subtext).toContain('nicht evidenzbasiert');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- evidence
```

Expected: FAIL — cannot resolve `../evidence`.

- [ ] **Step 3: Write `src/core/evidence.ts`**

```ts
export const EVIDENCE_KEYS = [
  'hilft', 'kann_helfen', 'tut_gut', 'mechanismus', 'anker', 'reflexion',
] as const;

export type EvidenceKey = (typeof EVIDENCE_KEYS)[number];

/** Icon shape the UI renders for a level. No colors or SVG live in core. */
export type EvidenceIcon = 'check' | 'star' | 'heart' | 'circadian' | 'drop' | 'pen';

export interface EvidenceLevel {
  readonly key: EvidenceKey;
  readonly label: string;
  readonly icon: EvidenceIcon;
  /**
   * The single language rule of the product: only a level with this flag may
   * state that something is proven effective. Everything else says
   * "kann unterstützen".
   */
  readonly claimsEfficacy: boolean;
  readonly subtext?: string;
}

export const EVIDENCE: Record<EvidenceKey, EvidenceLevel> = {
  hilft:       { key: 'hilft',       label: 'Studien belegen Wirksamkeit', icon: 'check',     claimsEfficacy: true },
  kann_helfen: { key: 'kann_helfen', label: 'Kann unterstützen',           icon: 'star',      claimsEfficacy: false },
  tut_gut:     { key: 'tut_gut',     label: 'Tut gut',                     icon: 'heart',     claimsEfficacy: false,
                 subtext: 'Wohlfühl-Baustein, nicht evidenzbasiert' },
  mechanismus: { key: 'mechanismus', label: 'Circadianer Anker',           icon: 'circadian', claimsEfficacy: false },
  anker:       { key: 'anker',       label: 'Täglicher Anker',             icon: 'drop',      claimsEfficacy: false },
  reflexion:   { key: 'reflexion',   label: 'Reflexion',                   icon: 'pen',       claimsEfficacy: false },
};

export function mayClaimEfficacy(key: EvidenceKey): boolean {
  return EVIDENCE[key].claimsEfficacy;
}

/** Symptom context that selects a level for graded modules. */
export type EvidenceContext =
  | 'hotFlashes' | 'sleep' | 'brainFog' | 'psych' | 'joints' | 'weight';
```

Colors moved out of core deliberately: they belong to the design system (`src/ui/`), and core must stay renderer-agnostic.

- [ ] **Step 4: Run tests**

```bash
npm test -- evidence
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/evidence.ts src/core/__tests__/evidence.test.ts
git commit -m "feat(core): evidence levels with the efficacy-claim rule under test"
```

---

## Task 5: Wirkziele

**Files:**
- Create: `src/core/goals.ts`
- Test: `src/core/__tests__/goals.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { GOALS, GOAL_IDS, goalById } from '../goals';

describe('goals', () => {
  it('holds the 6 Wirkziele', () => {
    expect(GOAL_IDS).toEqual(['calm', 'mood', 'clarity', 'energize', 'body', 'reflect']);
  });

  it('gives every goal a German label and blurb', () => {
    for (const g of GOALS) {
      expect(g.label.length).toBeGreaterThan(0);
      expect(g.blurb.length).toBeGreaterThan(0);
    }
  });

  it('looks a goal up by id', () => {
    expect(goalById('calm')?.label).toBe('Beruhigen');
    expect(goalById('nope' as never)).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- goals
```

Expected: FAIL — cannot resolve `../goals`.

- [ ] **Step 3: Write `src/core/goals.ts`**

```ts
export const GOAL_IDS = [
  'calm', 'mood', 'clarity', 'energize', 'body', 'reflect',
] as const;

export type GoalId = (typeof GOAL_IDS)[number];

/**
 * Wirkziele exist for the interface: they name and color a module card.
 * Selection runs on categories, not on these.
 */
export interface Goal {
  readonly id: GoalId;
  readonly label: string;
  readonly blurb: string;
}

export const GOALS: readonly Goal[] = [
  { id: 'calm',     label: 'Beruhigen',                 blurb: 'Nervensystem herunterfahren.' },
  { id: 'mood',     label: 'Stimmung heben',            blurb: 'Sanft den Tag aufhellen.' },
  { id: 'clarity',  label: 'Klarheit',                  blurb: 'Kopf sortieren, fokussieren.' },
  { id: 'energize', label: 'Energetisieren & Rhythmus', blurb: 'Biorhythmus & Antrieb wecken.' },
  { id: 'body',     label: 'Körper & Gelenke',          blurb: 'Beweglich und kräftig bleiben.' },
  { id: 'reflect',  label: 'Ankommen & Reflexion',      blurb: 'Einen Moment innehalten, ankommen.' },
];

export function goalById(id: GoalId): Goal | undefined {
  return GOALS.find((g) => g.id === id);
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- goals
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/goals.ts src/core/__tests__/goals.test.ts
git commit -m "feat(core): Wirkziele as presentation metadata"
```

---

## Task 6: Base scoring

**Files:**
- Create: `src/core/scoring.ts`
- Test: `src/core/__tests__/scoring.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { baseScores, rankCategories } from '../scoring';

describe('baseScores', () => {
  it('returns all zeros for an empty profile', () => {
    expect(baseScores({})).toEqual({
      nervensystem: 0, bewegung: 0, ernaehrung: 0, mindset: 0, wissen: 0,
    });
  });

  it('reproduces the concept example for sleep 4 + fatigue 3', () => {
    const s = baseScores({ sleep: 4, fatigue: 3 });
    expect(s.nervensystem).toBe(18);
    expect(s.bewegung).toBe(13);
  });

  it('ignores symptoms below the severity threshold', () => {
    expect(baseScores({ sleep: 1 })).toEqual(baseScores({}));
  });

  it('counts a symptom exactly at the threshold', () => {
    expect(baseScores({ sleep: 2 }).nervensystem).toBe(6);
  });

  it('ignores out-of-scope symptoms entirely', () => {
    expect(baseScores({ heart: 4 })).toEqual(baseScores({}));
  });

  it('adds contributions from several symptoms', () => {
    const s = baseScores({ sleep: 2, joints: 2 });
    expect(s.bewegung).toBe(2 * 1 + 2 * 3);
  });
});

describe('rankCategories', () => {
  it('sorts categories by score, highest first', () => {
    const ranked = rankCategories({
      nervensystem: 18, bewegung: 13, ernaehrung: 0, mindset: 11, wissen: 4,
    });
    expect(ranked.map((r) => r.category)).toEqual([
      'nervensystem', 'bewegung', 'mindset', 'wissen', 'ernaehrung',
    ]);
  });

  it('breaks ties by the fixed category order, so results are deterministic', () => {
    const ranked = rankCategories({
      nervensystem: 5, bewegung: 5, ernaehrung: 5, mindset: 5, wissen: 5,
    });
    expect(ranked.map((r) => r.category)).toEqual([
      'nervensystem', 'bewegung', 'ernaehrung', 'mindset', 'wissen',
    ]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- scoring
```

Expected: FAIL — cannot resolve `../scoring`.

- [ ] **Step 3: Write `src/core/scoring.ts`**

```ts
import { CATEGORIES, WEIGHTS, emptyScores } from './categories';
import type { CategoryId, CategoryScores } from './categories';
import { SEVERITY_THRESHOLD, inScopeSymptoms, severityOf } from './symptoms';
import type { InScopeSymptomId, SymptomScores } from './symptoms';

/**
 * Step 1 of the pipeline: symptom x severity, summed per category.
 * Symptoms below the threshold contribute nothing — a barely noticed
 * complaint should not shape the morning.
 */
export function baseScores(symptoms: SymptomScores): CategoryScores {
  const scores = emptyScores();

  for (const item of inScopeSymptoms()) {
    const severity = severityOf(symptoms, item.id);
    if (severity < SEVERITY_THRESHOLD) continue;

    const row = WEIGHTS[item.id as InScopeSymptomId];
    for (const category of CATEGORIES) {
      scores[category] += row[category] * severity;
    }
  }

  return scores;
}

export interface RankedCategory {
  readonly category: CategoryId;
  readonly score: number;
}

/**
 * Ties break by the declaration order of CATEGORIES rather than arbitrarily,
 * so the same profile always produces the same routine.
 */
export function rankCategories(scores: CategoryScores): RankedCategory[] {
  return CATEGORIES
    .map((category, index) => ({ category, score: scores[category], index }))
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(({ category, score }) => ({ category, score }));
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- scoring
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/scoring.ts src/core/__tests__/scoring.test.ts
git commit -m "feat(core): base category scoring with deterministic ranking"
```

---

## Task 7: Phase modifier

**Files:**
- Create: `src/core/phase.ts`
- Test: `src/core/__tests__/phase.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { PHASE_MODIFIERS, COLLECTED_PHASES, applyPhaseModifier } from '../phase';

const flat = { nervensystem: 10, bewegung: 10, ernaehrung: 10, mindset: 10, wissen: 10 };

describe('applyPhaseModifier', () => {
  it('leaves scores untouched when no phase is known', () => {
    expect(applyPhaseModifier(flat, null)).toEqual(flat);
  });

  it('raises Nervensystem by 30% and Mindset by 20% in perimenopause', () => {
    const s = applyPhaseModifier(flat, 'peri');
    expect(s.nervensystem).toBe(13);
    expect(s.mindset).toBe(12);
    expect(s.bewegung).toBe(10);
  });

  it('raises Bewegung and lowers Nervensystem after menopause', () => {
    const s = applyPhaseModifier(flat, 'post');
    expect(s.bewegung).toBe(13);
    expect(s.nervensystem).toBe(9);
  });

  it('raises Wissen when the phase is unclear', () => {
    expect(applyPhaseModifier(flat, 'unsure').wissen).toBe(13);
  });

  it('does not mutate its input', () => {
    const input = { ...flat };
    applyPhaseModifier(input, 'peri');
    expect(input).toEqual(flat);
  });

  it('defines early perimenopause but does not collect it in v1', () => {
    expect(PHASE_MODIFIERS.earlyPeri).toBeDefined();
    expect(COLLECTED_PHASES).toEqual(['peri', 'meno', 'post', 'unsure']);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- phase
```

Expected: FAIL — cannot resolve `../phase`.

- [ ] **Step 3: Write `src/core/phase.ts`**

```ts
import { CATEGORIES } from './categories';
import type { CategoryId, CategoryScores } from './categories';

export type Phase = 'earlyPeri' | 'peri' | 'meno' | 'post' | 'unsure';

/**
 * The four options the onboarding actually offers. `earlyPeri` is specified by
 * the concept but has no option in the interface, so its modifier is
 * unreachable in v1. Documented rather than deleted: the concept asks for five
 * phases and v2 may add the option.
 */
export const COLLECTED_PHASES = ['peri', 'meno', 'post', 'unsure'] as const;

/** Multipliers per category. Concept section 2.3. */
export const PHASE_MODIFIERS: Record<Phase, Partial<Record<CategoryId, number>>> = {
  earlyPeri: { nervensystem: 1.2 },
  peri:      { nervensystem: 1.3, mindset: 1.2 },
  meno:      { wissen: 1.2 },
  post:      { bewegung: 1.3, nervensystem: 0.9 },
  unsure:    { wissen: 1.3 },
};

export function applyPhaseModifier(
  scores: CategoryScores,
  phase: Phase | null,
): CategoryScores {
  if (phase === null) return { ...scores };

  const modifiers = PHASE_MODIFIERS[phase];
  const result = { ...scores };

  for (const category of CATEGORIES) {
    const factor = modifiers[category];
    if (factor !== undefined) {
      result[category] = scores[category] * factor;
    }
  }

  return result;
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- phase
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/phase.ts src/core/__tests__/phase.test.ts
git commit -m "feat(core): phase modifier, so the phase answer changes the routine"
```

---

## Task 8: Preference booster (F1)

**Files:**
- Create: `src/core/preferences.ts`
- Test: `src/core/__tests__/preferences.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import {
  PREFERENCES, PREFERENCE_BOOST, MAX_PREFERENCES, applyPreferenceBoost,
} from '../preferences';

const flat = { nervensystem: 10, bewegung: 10, ernaehrung: 10, mindset: 10, wissen: 10 };

describe('applyPreferenceBoost', () => {
  it('leaves scores untouched with no preferences', () => {
    expect(applyPreferenceBoost(flat, [])).toEqual(flat);
  });

  it('boosts the category of a chosen preference by 1.5', () => {
    expect(applyPreferenceBoost(flat, ['breathing']).nervensystem).toBe(15);
  });

  it('boosts a category only once even if two preferences map to it', () => {
    const s = applyPreferenceBoost(flat, ['breathing', 'meditation']);
    expect(s.nervensystem).toBe(15);
  });

  it('changes nothing for "open to anything"', () => {
    expect(applyPreferenceBoost(flat, ['open'])).toEqual(flat);
  });

  it('leaves unchosen categories alone', () => {
    expect(applyPreferenceBoost(flat, ['breathing']).bewegung).toBe(10);
  });

  it('does not mutate its input', () => {
    const input = { ...flat };
    applyPreferenceBoost(input, ['breathing']);
    expect(input).toEqual(flat);
  });

  it('offers 8 options and allows at most 3', () => {
    expect(PREFERENCES).toHaveLength(8);
    expect(MAX_PREFERENCES).toBe(3);
    expect(PREFERENCE_BOOST).toBe(1.5);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- preferences
```

Expected: FAIL — cannot resolve `../preferences`.

- [ ] **Step 3: Write `src/core/preferences.ts`**

```ts
import type { CategoryId, CategoryScores } from './categories';

export type PreferenceId =
  | 'breathing' | 'movement' | 'journaling' | 'gratitude'
  | 'knowledge' | 'nutrition' | 'meditation' | 'open';

export interface Preference {
  readonly id: PreferenceId;
  readonly label: string;
  /** null means the choice expresses openness and boosts nothing. */
  readonly category: CategoryId | null;
}

export const PREFERENCES: readonly Preference[] = [
  { id: 'breathing',  label: 'Atemübungen & Entspannung',              category: 'nervensystem' },
  { id: 'meditation', label: 'Meditation & Achtsamkeit',               category: 'nervensystem' },
  { id: 'movement',   label: 'Sanfte Bewegung & Stretching',           category: 'bewegung' },
  { id: 'journaling', label: 'Journaling & Reflexion',                 category: 'mindset' },
  { id: 'gratitude',  label: 'Dankbarkeit & positive Gedanken',        category: 'mindset' },
  { id: 'knowledge',  label: 'Wissensinputs über Hormone & Gesundheit', category: 'wissen' },
  { id: 'nutrition',  label: 'Gesunde Ernährung & Frühstücksideen',    category: 'ernaehrung' },
  { id: 'open',       label: 'Ich bin offen für alles',                category: null },
];

export const MAX_PREFERENCES = 3;
export const PREFERENCE_BOOST = 1.5;

/**
 * Concept section 2.5. The boost applies per category, not per preference:
 * choosing both breathing and meditation must not square the multiplier.
 */
export function applyPreferenceBoost(
  scores: CategoryScores,
  chosen: readonly PreferenceId[],
): CategoryScores {
  const boosted = new Set<CategoryId>();

  for (const id of chosen) {
    const preference = PREFERENCES.find((p) => p.id === id);
    if (preference?.category) boosted.add(preference.category);
  }

  const result = { ...scores };
  for (const category of boosted) {
    result[category] = scores[category] * PREFERENCE_BOOST;
  }
  return result;
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- preferences
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/preferences.ts src/core/__tests__/preferences.test.ts
git commit -m "feat(core): preference booster on the real F1 question"
```

---

## Task 9: Daily check-in modifier

**Files:**
- Create: `src/core/checkin.ts`
- Test: `src/core/__tests__/checkin.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { applyEnergyModifier, capsPhysicalTier } from '../checkin';

const flat = { nervensystem: 10, bewegung: 10, ernaehrung: 10, mindset: 10, wissen: 10 };

describe('applyEnergyModifier', () => {
  it('leaves scores untouched without a check-in', () => {
    expect(applyEnergyModifier(flat, null)).toEqual(flat);
  });

  it('shifts weight toward the nervous system on a low-energy morning', () => {
    const s = applyEnergyModifier(flat, 1);
    expect(s.nervensystem).toBeGreaterThan(10);
    expect(s.bewegung).toBeLessThan(10);
  });

  it('treats energy 3 as the planned standard', () => {
    expect(applyEnergyModifier(flat, 3)).toEqual(flat);
  });

  it('shifts weight toward movement on a high-energy morning', () => {
    expect(applyEnergyModifier(flat, 5).bewegung).toBeGreaterThan(10);
  });

  it('does not mutate its input', () => {
    const input = { ...flat };
    applyEnergyModifier(input, 1);
    expect(input).toEqual(flat);
  });
});

describe('capsPhysicalTier', () => {
  it('caps physical modules to gentle when energy is low', () => {
    expect(capsPhysicalTier(1)).toBe(true);
    expect(capsPhysicalTier(2)).toBe(true);
  });

  it('does not cap from energy 3 upward, nor without a check-in', () => {
    expect(capsPhysicalTier(3)).toBe(false);
    expect(capsPhysicalTier(5)).toBe(false);
    expect(capsPhysicalTier(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- checkin
```

Expected: FAIL — cannot resolve `../checkin`.

- [ ] **Step 3: Write `src/core/checkin.ts`**

```ts
import type { CategoryScores } from './categories';

/** Daily self-report on a 1-5 scale, 1 = exhausted, 5 = energetic. */
export type Energy = 1 | 2 | 3 | 4 | 5;
export type Mood = 1 | 2 | 3 | 4 | 5;

export interface DailyCheckin {
  readonly energy: Energy;
  readonly mood: Mood;
}

const LOW_ENERGY_MAX = 2;
const HIGH_ENERGY_MIN = 4;

/**
 * Concept section 2.6. A tired morning gets a shorter, calmer routine;
 * an energetic one may lean into movement. This shifts emphasis only —
 * it never overrides the symptom severities underneath.
 */
export function applyEnergyModifier(
  scores: CategoryScores,
  energy: Energy | null,
): CategoryScores {
  if (energy === null || (energy > LOW_ENERGY_MAX && energy < HIGH_ENERGY_MIN)) {
    return { ...scores };
  }

  if (energy <= LOW_ENERGY_MAX) {
    return { ...scores, nervensystem: scores.nervensystem * 1.3, bewegung: scores.bewegung * 0.7 };
  }

  return { ...scores, bewegung: scores.bewegung * 1.3 };
}

/**
 * On a low-energy morning, physical modules drop to the gentle variant
 * regardless of the fitness level. Separate from the score shift because it
 * constrains the variant, not the ranking.
 */
export function capsPhysicalTier(energy: Energy | null): boolean {
  return energy !== null && energy <= LOW_ENERGY_MAX;
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- checkin
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/checkin.ts src/core/__tests__/checkin.test.ts
git commit -m "feat(core): daily energy modifier and gentle cap"
```

---

## Task 10: Exercise catalog with contraindications

**Safety note for the implementer:** the contraindication assignments below are a first pass by a non-clinician. They must be reviewed by a physiotherapist before release, on the same footing as the medical article content. Do not loosen them without that review; tightening them is always safe.

**Files:**
- Create: `src/core/exercises.ts`
- Test: `src/core/__tests__/exercises.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { EXERCISES, exercisesForLevel, RESTRICTIONS } from '../exercises';

describe('exercises', () => {
  it('offers 5 gentle, 6 moderate and 6 active exercises', () => {
    expect(exercisesForLevel('gentle')).toHaveLength(5);
    expect(exercisesForLevel('moderate')).toHaveLength(6);
    expect(exercisesForLevel('active')).toHaveLength(6);
  });

  it('gives every exercise a positive duration', () => {
    for (const e of EXERCISES) {
      expect(e.sec).toBeGreaterThan(0);
    }
  });

  it('keeps exercise ids unique', () => {
    const ids = EXERCISES.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('flags the one-legged balance pose as a balance contraindication', () => {
    const tree = EXERCISES.find((e) => e.id === 'tree');
    expect(tree?.contraindications).toContain('balance');
  });

  it('flags squats and lunges for knees', () => {
    for (const id of ['squat-chair', 'squat', 'lunge']) {
      expect(EXERCISES.find((e) => e.id === id)?.contraindications).toContain('knees');
    }
  });

  it('leaves breathing free of physical contraindications', () => {
    expect(EXERCISES.find((e) => e.id === 'boxbreath')?.contraindications).toEqual([]);
  });

  it('only uses declared restriction ids', () => {
    for (const e of EXERCISES) {
      for (const c of e.contraindications) {
        expect(RESTRICTIONS).toContain(c);
      }
    }
  });

  it('marks which exercises actually have a video', () => {
    const withVideo = EXERCISES.filter((e) => e.media === 'video');
    expect(withVideo.map((e) => e.id).sort()).toEqual(
      ['catcow', 'fold', 'sidebend', 'tree'],
    );
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- exercises
```

Expected: FAIL — cannot resolve `../exercises`.

- [ ] **Step 3: Write `src/core/exercises.ts`**

```ts
export const RESTRICTIONS = ['back', 'knees', 'shoulders', 'balance'] as const;
export type RestrictionId = (typeof RESTRICTIONS)[number];

export type FitnessLevel = 'gentle' | 'moderate' | 'active';

/** What we can actually show today. Drives the fallback in the player. */
export type ExerciseMedia = 'video' | 'photo' | 'none';

export interface Exercise {
  readonly id: string;
  readonly level: FitnessLevel;
  readonly name: string;
  readonly dose: string;
  readonly description: string;
  readonly sec: number;
  readonly media: ExerciseMedia;
  /**
   * Restrictions that rule this exercise out. First-pass assignment by a
   * non-clinician — requires physiotherapist review before release.
   */
  readonly contraindications: readonly RestrictionId[];
}

export const EXERCISES: readonly Exercise[] = [
  // Stufe 1 — Sanftes Stretching
  { id: 'catcow',   level: 'gentle', name: 'Katze-Kuh-Stretch', dose: 'mobilisierend', description: 'Wirbelsäule mobilisieren', sec: 60, media: 'video', contraindications: ['knees'] },
  { id: 'sidebend', level: 'gentle', name: 'Sanfte Seitneige',  dose: 'dehnend',       description: 'Flanken öffnen',           sec: 45, media: 'video', contraindications: [] },
  { id: 'twist',    level: 'gentle', name: 'Stehende Drehung',  dose: 'lösend',        description: 'Rumpf sanft rotieren',     sec: 45, media: 'photo', contraindications: ['back'] },
  { id: 'fold',     level: 'gentle', name: 'Stehende Vorbeuge', dose: 'lösend',        description: 'Rücken & Beinrückseite',   sec: 60, media: 'video', contraindications: ['back'] },
  { id: 'tree',     level: 'gentle', name: 'Baum (Balance)',    dose: 'zentrierend',   description: 'Gleichgewicht & Fokus',    sec: 60, media: 'video', contraindications: ['balance'] },

  // Stufe 2 — Stretching + leichte Kräftigung
  { id: 'sunlight',    level: 'moderate', name: 'Sonnengruß light',          dose: 'fließend',   description: 'Ganzkörper aktivieren',    sec: 60, media: 'none', contraindications: ['back', 'shoulders'] },
  { id: 'wallpush',    level: 'moderate', name: 'Wandstützen',               dose: '2×10 Wdh',   description: 'Sanfte Armkraft',          sec: 45, media: 'none', contraindications: ['shoulders'] },
  { id: 'bridge',      level: 'moderate', name: 'Brücke',                    dose: '2×12 Wdh',   description: 'Po & unterer Rücken',      sec: 60, media: 'none', contraindications: ['back'] },
  { id: 'lunge',       level: 'moderate', name: 'Hüftöffner Ausfallschritt', dose: 'je Seite',   description: 'Mobilität',                sec: 60, media: 'none', contraindications: ['knees', 'balance'] },
  { id: 'boxbreath',   level: 'moderate', name: 'Box-Atmung',                dose: 'fokussiert', description: 'Fokus setzen',             sec: 60, media: 'none', contraindications: [] },
  { id: 'squat-chair', level: 'moderate', name: 'Stuhl-Squats',              dose: '2×12 Wdh',   description: 'Beine sanft kräftigen',    sec: 45, media: 'none', contraindications: ['knees'] },

  // Stufe 3 — Kraft + dynamisches Stretching
  { id: 'jacks',     level: 'active', name: 'Jumping Jacks',         dose: 'Warm-up',   description: 'Kreislauf hochfahren', sec: 45, media: 'none', contraindications: ['knees', 'balance'] },
  { id: 'pushup',    level: 'active', name: 'Push-ups',              dose: '3×12 Wdh',  description: 'Oberkörperkraft',      sec: 60, media: 'none', contraindications: ['shoulders'] },
  { id: 'squat',     level: 'active', name: 'Kniebeuge',             dose: '3×15 Wdh',  description: 'Beinpower',            sec: 60, media: 'none', contraindications: ['knees'] },
  { id: 'plank',     level: 'active', name: 'Plank',                 dose: '3×30 Sek',  description: 'Core-Stabilität',      sec: 45, media: 'none', contraindications: ['shoulders', 'back'] },
  { id: 'hipcircle', level: 'active', name: 'Dynamischer Hüftkreis', dose: 'Cool-down', description: 'Mobilität lösen',      sec: 45, media: 'none', contraindications: ['balance'] },
  { id: 'pigeon',    level: 'active', name: 'Pigeon Pose',           dose: 'je Seite',  description: 'Tiefes Dehnen',        sec: 90, media: 'none', contraindications: ['knees'] },
];

export function exercisesForLevel(level: FitnessLevel): Exercise[] {
  return EXERCISES.filter((e) => e.level === level);
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- exercises
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/exercises.ts src/core/__tests__/exercises.test.ts
git commit -m "feat(core): exercise catalog with contraindications and media state"
```

---

## Task 11: Restriction filter

**Files:**
- Create: `src/core/restrictions.ts`
- Test: `src/core/__tests__/restrictions.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { filterByRestrictions } from '../restrictions';
import { exercisesForLevel } from '../exercises';

describe('filterByRestrictions', () => {
  const gentle = exercisesForLevel('gentle');

  it('returns everything when there are no restrictions', () => {
    expect(filterByRestrictions(gentle, [])).toHaveLength(gentle.length);
  });

  it('removes the balance pose for someone with balance trouble', () => {
    const kept = filterByRestrictions(gentle, ['balance']);
    expect(kept.map((e) => e.id)).not.toContain('tree');
  });

  it('removes every exercise matching any listed restriction', () => {
    // catcow survives: it is contraindicated for knees, not for back.
    const kept = filterByRestrictions(gentle, ['back', 'balance']);
    expect(kept.map((e) => e.id)).toEqual(['catcow', 'sidebend']);
  });

  it('can return an empty list rather than an unsafe one', () => {
    const active = exercisesForLevel('active');
    expect(filterByRestrictions(active, ['knees', 'shoulders', 'balance', 'back'])).toEqual([]);
  });

  it('does not mutate its input', () => {
    const before = [...gentle];
    filterByRestrictions(gentle, ['balance']);
    expect(gentle).toEqual(before);
  });
});
```

The fourth test states the safety rule explicitly: when every exercise is contraindicated, the engine returns nothing. It must never fall back to "show something anyway".

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- restrictions
```

Expected: FAIL — cannot resolve `../restrictions`.

- [ ] **Step 3: Write `src/core/restrictions.ts`**

```ts
import type { Exercise, RestrictionId } from './exercises';

/**
 * Removes every exercise contraindicated by any declared restriction.
 *
 * Returning an empty list is a valid, intended outcome. The caller shows the
 * practice modules without a movement block rather than substituting an
 * exercise the user told us to avoid.
 */
export function filterByRestrictions(
  exercises: readonly Exercise[],
  restrictions: readonly RestrictionId[],
): Exercise[] {
  if (restrictions.length === 0) return [...exercises];

  const blocked = new Set(restrictions);
  return exercises.filter(
    (e) => !e.contraindications.some((c) => blocked.has(c)),
  );
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- restrictions
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/restrictions.ts src/core/__tests__/restrictions.test.ts
git commit -m "feat(core): restriction filter that may legitimately return nothing"
```

---

## Task 12: Weekly rotation

**Files:**
- Create: `src/core/rotation.ts`
- Test: `src/core/__tests__/rotation.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { rotate, weekIndexOf } from '../rotation';

const pool = ['a', 'b', 'c', 'd', 'e'];

describe('rotate', () => {
  it('is stable within the same week', () => {
    expect(rotate(pool, 7, 3)).toEqual(rotate(pool, 7, 3));
  });

  it('picks a different window the following week', () => {
    expect(rotate(pool, 7, 3)).not.toEqual(rotate(pool, 8, 3));
  });

  it('returns exactly the requested count', () => {
    expect(rotate(pool, 3, 2)).toHaveLength(2);
  });

  it('wraps around the end of the pool', () => {
    expect(rotate(pool, 4, 3)).toEqual(['e', 'a', 'b']);
  });

  it('returns the whole pool when asked for more than it holds', () => {
    expect(rotate(pool, 2, 99)).toHaveLength(5);
  });

  it('still rotates the order when asked for the whole pool', () => {
    expect(rotate(pool, 2, 5)).not.toEqual(rotate(pool, 3, 5));
    expect([...rotate(pool, 2, 5)].sort()).toEqual([...pool].sort());
  });

  it('returns nothing for an empty pool', () => {
    expect(rotate([], 1, 3)).toEqual([]);
  });
});

describe('weekIndexOf', () => {
  it('gives the same index for two days in one week', () => {
    expect(weekIndexOf(new Date('2026-08-24T06:00:00Z')))
      .toBe(weekIndexOf(new Date('2026-08-28T06:00:00Z')));
  });

  it('advances by one across a week boundary', () => {
    const a = weekIndexOf(new Date('2026-08-28T06:00:00Z')); // Friday
    const b = weekIndexOf(new Date('2026-08-31T06:00:00Z')); // Monday
    expect(b - a).toBe(1);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- rotation
```

Expected: FAIL — cannot resolve `../rotation`.

- [ ] **Step 3: Write `src/core/rotation.ts`**

```ts
const MS_PER_DAY = 86_400_000;
const MS_PER_WEEK = MS_PER_DAY * 7;

/**
 * Whole weeks since the Unix epoch, aligned to Monday.
 *
 * The date is always passed in, never read from a clock: core must stay pure
 * so that a routine is reproducible in a test and on a server.
 */
export function weekIndexOf(date: Date): number {
  // 1970-01-01 was a Thursday; shifting by 4 days aligns week starts to Monday.
  return Math.floor((date.getTime() + 4 * MS_PER_DAY) / MS_PER_WEEK);
}

/**
 * A sliding window over the pool, advancing one position per week, wrapping at
 * the end. Deterministic by design — the same week always yields the same
 * selection, so a routine does not reshuffle when the screen is reopened.
 */
export function rotate<T>(
  pool: readonly T[],
  weekIndex: number,
  count: number,
): T[] {
  if (pool.length === 0 || count <= 0) return [];

  // Note there is no `count >= pool.length` shortcut returning the pool as-is:
  // asking for everything must still rotate the ORDER, otherwise a small pool
  // produces the identical routine every week and the rotation does nothing.
  const take = Math.min(count, pool.length);
  const start = ((weekIndex % pool.length) + pool.length) % pool.length;

  const picked: T[] = [];
  for (let i = 0; i < take; i++) {
    picked.push(pool[(start + i) % pool.length]!);
  }
  return picked;
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- rotation
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/rotation.ts src/core/__tests__/rotation.test.ts
git commit -m "feat(core): deterministic weekly rotation without a clock"
```

---

## Task 13: Module catalog

**Files:**
- Create: `src/core/catalog.ts`
- Test: `src/core/__tests__/catalog.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { MODULES, moduleById, anchorModules, modulesForCategory } from '../catalog';
import { EVIDENCE } from '../evidence';

describe('catalog', () => {
  it('keeps water and light as the two anchors', () => {
    expect(anchorModules().map((m) => m.id).sort()).toEqual(['light', 'water']);
  });

  it('gives every non-anchor module a category', () => {
    for (const m of MODULES) {
      if (!m.anchor) expect(m.category).not.toBeNull();
    }
  });

  it('leaves anchors outside category scoring', () => {
    for (const m of anchorModules()) expect(m.category).toBeNull();
  });

  it('offers modules for the three categories that have them', () => {
    expect(modulesForCategory('nervensystem').map((m) => m.id)).toEqual(['breath', 'meditate']);
    expect(modulesForCategory('bewegung').map((m) => m.id)).toEqual(['movement', 'stretch']);
    expect(modulesForCategory('mindset').map((m) => m.id)).toEqual(['tagesanker', 'gratitude', 'affirm']);
  });

  it('has no module for Ernährung or Wissen in v1', () => {
    expect(modulesForCategory('ernaehrung')).toEqual([]);
    expect(modulesForCategory('wissen')).toEqual([]);
  });

  it('gives every module all three variants with positive minutes', () => {
    for (const m of MODULES) {
      for (const tier of ['gentle', 'standard', 'extended'] as const) {
        expect(m.variants[tier].minutes).toBeGreaterThan(0);
        expect(m.variants[tier].desc.length).toBeGreaterThan(0);
      }
    }
  });

  it('only lets graded modules reach the efficacy-claiming level', () => {
    for (const m of MODULES) {
      if (m.evidence && EVIDENCE[m.evidence].claimsEfficacy) {
        throw new Error(`fixed-evidence module ${m.id} must not claim efficacy`);
      }
    }
  });

  it('looks a module up by id', () => {
    expect(moduleById('breath')?.title).toBe('Atemübung');
    expect(moduleById('nope' as never)).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- catalog
```

Expected: FAIL — cannot resolve `../catalog`.

- [ ] **Step 3: Write `src/core/catalog.ts`**

```ts
import type { CategoryId } from './categories';
import type { EvidenceContext, EvidenceKey } from './evidence';
import type { GoalId } from './goals';

export const MODULE_IDS = [
  'water', 'light', 'breath', 'meditate',
  'movement', 'stretch', 'tagesanker', 'gratitude', 'affirm',
] as const;

export type ModuleId = (typeof MODULE_IDS)[number];

export type Tier = 'gentle' | 'standard' | 'extended';

export interface ModuleVariant {
  readonly desc: string;
  readonly minutes: number;
}

export interface CatalogModule {
  readonly id: ModuleId;
  readonly title: string;
  /** Presentation only — colors and labels. */
  readonly goal: GoalId;
  /** Selection axis. null for anchors, which bypass scoring. */
  readonly category: CategoryId | null;
  readonly anchor?: boolean;
  readonly feelgood?: boolean;
  readonly icon: string;
  /** Fixed level for modules that make no efficacy claim. */
  readonly evidence?: EvidenceKey;
  /** Graded level, chosen by the symptom context that put the module here. */
  readonly evidenceByContext?: Partial<Record<EvidenceContext | 'default', EvidenceKey>>;
  readonly variants: Record<Tier, ModuleVariant>;
}

export const MODULES: readonly CatalogModule[] = [
  {
    id: 'water', title: 'Ein Glas Wasser', goal: 'energize', category: null,
    anchor: true, icon: 'water', evidence: 'anker',
    variants: {
      gentle:   { desc: 'Ein großes Glas Wasser,\nin Ruhe getrunken.', minutes: 1 },
      standard: { desc: 'Ein großes Glas Wasser,\nin Ruhe getrunken.', minutes: 1 },
      extended: { desc: 'Ein großes Glas Wasser,\nin Ruhe getrunken.', minutes: 1 },
    },
  },
  {
    id: 'light', title: 'Morgenlicht', goal: 'energize', category: null,
    anchor: true, icon: 'sun', evidence: 'mechanismus',
    variants: {
      gentle:   { desc: 'Ans Fenster treten und 2 Minuten Licht tanken.',    minutes: 2 },
      standard: { desc: 'Kurz nach draußen, 5 Minuten Tageslicht.',          minutes: 5 },
      extended: { desc: 'Ein kleiner Gang an der frischen Luft, 8 Minuten.', minutes: 8 },
    },
  },
  {
    id: 'breath', title: 'Atemübung', goal: 'calm', category: 'nervensystem', icon: 'breath',
    evidenceByContext: { hotFlashes: 'kann_helfen', default: 'kann_helfen' },
    variants: {
      gentle:   { desc: 'Tiefe Bauchatmung, 6 ruhige Atemzüge.',              minutes: 2 },
      standard: { desc: '4-7-8 Atmung: ein 4, halten 7, aus 8 – 4 Runden.',   minutes: 2 },
      extended: { desc: '4-7-8 Atmung plus verlängerte Ausatmung, 8 Runden.', minutes: 2 },
    },
  },
  {
    id: 'meditate', title: 'Achtsamkeit', goal: 'calm', category: 'nervensystem', icon: 'meditate',
    evidenceByContext: { default: 'kann_helfen' },
    variants: {
      gentle:   { desc: 'Eine Minute still sitzen und nachspüren.', minutes: 2 },
      standard: { desc: 'Geführter Body-Scan von Kopf bis Fuß.',    minutes: 5 },
      extended: { desc: 'Body-Scan mit Achtsamkeit auf den Atem.',  minutes: 8 },
    },
  },
  {
    id: 'movement', title: 'Sanfte Bewegung', goal: 'energize', category: 'bewegung', icon: 'move',
    evidenceByContext: {
      sleep: 'hilft', psych: 'hilft', brainFog: 'kann_helfen',
      joints: 'kann_helfen', weight: 'kann_helfen', default: 'kann_helfen',
    },
    variants: {
      gentle:   { desc: 'Schultern kreisen, sanft den Körper wecken (5–10 Min).',     minutes: 6 },
      standard: { desc: 'Mobilisation für Rücken, Hüfte, Nacken – Yoga oder Gehen.',  minutes: 12 },
      extended: { desc: 'Mobilisation plus Kräftigung, etwas fordernder (15–20 Min).', minutes: 18 },
    },
  },
  {
    id: 'stretch', title: 'Dehnen & Yoga', goal: 'body', category: 'bewegung', icon: 'stretch',
    evidenceByContext: {
      sleep: 'hilft', psych: 'kann_helfen', hotFlashes: 'kann_helfen',
      joints: 'kann_helfen', default: 'kann_helfen',
    },
    variants: {
      gentle:   { desc: 'Sanftes Dehnen für die großen Gelenke.',   minutes: 3 },
      standard: { desc: 'Gelenkroutine für Hände, Knie, Schultern.', minutes: 5 },
      extended: { desc: 'Mobilisation plus leichte Kräftigung.',     minutes: 8 },
    },
  },
  {
    id: 'tagesanker', title: 'Tagesanker', goal: 'reflect', category: 'mindset',
    icon: 'anchor', evidence: 'reflexion',
    variants: {
      gentle:   { desc: 'Halte einen Moment inne und beantworte die Frage für Dich.', minutes: 1 },
      standard: { desc: 'Halte einen Moment inne und beantworte die Frage für Dich.', minutes: 1 },
      extended: { desc: 'Halte einen Moment inne und beantworte die Frage für Dich.', minutes: 1 },
    },
  },
  {
    id: 'gratitude', title: 'Dankbarkeit', goal: 'mood', category: 'mindset',
    icon: 'heart', evidence: 'tut_gut', feelgood: true,
    variants: {
      gentle:   { desc: 'Ein Gedanke, für den Du heute dankbar bist.', minutes: 2 },
      standard: { desc: 'Drei Dinge aufschreiben, die Dich tragen.',   minutes: 3 },
      extended: { desc: 'Drei Dinge plus ein kleiner Brief an Dich.',  minutes: 5 },
    },
  },
  {
    id: 'affirm', title: 'Affirmation', goal: 'mood', category: 'mindset',
    icon: 'affirm', evidence: 'tut_gut', feelgood: true,
    variants: {
      gentle:   { desc: 'Einen warmen Satz innerlich wiederholen.', minutes: 1 },
      standard: { desc: 'Affirmation sprechen, drei Atemzüge lang.', minutes: 2 },
      extended: { desc: 'Affirmation mit Spiegelblick und Atem.',    minutes: 3 },
    },
  },
];

export function moduleById(id: ModuleId): CatalogModule | undefined {
  return MODULES.find((m) => m.id === id);
}

export function anchorModules(): CatalogModule[] {
  return MODULES.filter((m) => m.anchor === true);
}

export function modulesForCategory(category: CategoryId): CatalogModule[] {
  return MODULES.filter((m) => !m.anchor && m.category === category);
}
```

The prototype gave `tagesanker` 0.75 minutes. Fractional minutes make the budget arithmetic and its invariant test murky for a step the user perceives as "about a minute", so it is 1 here.

- [ ] **Step 4: Run tests**

```bash
npm test -- catalog
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/catalog.ts src/core/__tests__/catalog.test.ts
git commit -m "feat(core): module catalog keyed by category"
```

---

## Task 14: Profile types and schema

**Files:**
- Create: `src/core/profile.ts`
- Test: `src/core/__tests__/profile.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { healthProfileSchema, finalizeProfile, EMPTY_PROFILE } from '../profile';

const answered = {
  ...EMPTY_PROFILE,
  phase: 'peri' as const,
  hrtStatus: 'no' as const,
  fitnessLevel: 'gentle' as const,
  budgetMin: 10 as const,
  symptoms: { sleep: 3 as const },
};

describe('healthProfileSchema', () => {
  it('accepts a fully answered profile', () => {
    expect(healthProfileSchema.safeParse(answered).success).toBe(true);
  });

  it('rejects a severity outside 0-4', () => {
    const bad = { ...answered, symptoms: { sleep: 7 } };
    expect(healthProfileSchema.safeParse(bad).success).toBe(false);
  });

  it('rejects an unknown phase', () => {
    expect(healthProfileSchema.safeParse({ ...answered, phase: 'later' }).success).toBe(false);
  });

  it('rejects more than 3 preferences', () => {
    const bad = { ...answered, preferences: ['breathing', 'movement', 'journaling', 'gratitude'] };
    expect(healthProfileSchema.safeParse(bad).success).toBe(false);
  });

  it('rejects more than 5 selected symptoms', () => {
    const bad = {
      ...answered,
      symptoms: { sleep: 2, fatigue: 2, anxious: 2, joints: 2, weight: 2, hotFlashes: 2 },
    };
    expect(healthProfileSchema.safeParse(bad).success).toBe(false);
  });
});

describe('finalizeProfile', () => {
  it('marks onboarding complete', () => {
    expect(finalizeProfile(answered).onboardingComplete).toBe(true);
  });

  it('derives the HRT flags from the status', () => {
    expect(finalizeProfile({ ...answered, hrtStatus: 'long' }).hrtActive).toBe(true);
    expect(finalizeProfile({ ...answered, hrtStatus: 'excluded' }).hrtExcluded).toBe(true);
    expect(finalizeProfile({ ...answered, hrtStatus: 'no' }).hrtActive).toBe(false);
  });

  it('does not mutate its input', () => {
    const input = { ...answered };
    finalizeProfile(input);
    expect(input.onboardingComplete).toBe(false);
  });

  it('starts empty with onboarding incomplete and nothing selected', () => {
    expect(EMPTY_PROFILE.onboardingComplete).toBe(false);
    expect(EMPTY_PROFILE.symptoms).toEqual({});
    expect(EMPTY_PROFILE.preferences).toEqual([]);
    expect(EMPTY_PROFILE.restrictions).toBeNull();
  });
});
```

`restrictions` starts as `null`, not `[]`: an empty array means "asked, nothing applies", while `null` means "not asked yet". The player uses that difference to decide whether to ask before the first exercise.

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- profile
```

Expected: FAIL — cannot resolve `../profile`.

- [ ] **Step 3: Write `src/core/profile.ts`**

```ts
import { z } from 'zod';
import { RESTRICTIONS } from './exercises';
import { PREFERENCES, MAX_PREFERENCES } from './preferences';
import { COLLECTED_PHASES } from './phase';
import type { Phase } from './phase';
import type { FitnessLevel, RestrictionId } from './exercises';
import type { PreferenceId } from './preferences';
import type { SymptomScores } from './symptoms';

export type HrtStatus = 'no' | 'recent' | 'long' | 'excluded';
export type BudgetMin = 5 | 10 | 15 | 20 | 30;

/** Concept C1 caps the symptom selection at five. */
export const MAX_SELECTED_SYMPTOMS = 5;

export interface HealthProfile {
  readonly onboardingComplete: boolean;
  readonly phase: Phase | null;
  readonly hrtStatus: HrtStatus | null;
  readonly hrtActive: boolean;
  readonly hrtExcluded: boolean;
  readonly fitnessLevel: FitnessLevel | null;
  readonly budgetMin: BudgetMin | null;
  readonly wakeWindow: string | null;
  readonly symptoms: SymptomScores;
  readonly preferences: readonly PreferenceId[];
  /** null = not asked yet; [] = asked, nothing applies. */
  readonly restrictions: readonly RestrictionId[] | null;
}

export const EMPTY_PROFILE: HealthProfile = {
  onboardingComplete: false,
  phase: null,
  hrtStatus: null,
  hrtActive: false,
  hrtExcluded: false,
  fitnessLevel: null,
  budgetMin: null,
  wakeWindow: null,
  symptoms: {},
  preferences: [],
  restrictions: null,
};

const severitySchema = z.union([
  z.literal(0), z.literal(1), z.literal(2), z.literal(3), z.literal(4),
]);

export const healthProfileSchema = z.object({
  onboardingComplete: z.boolean(),
  phase: z.enum(COLLECTED_PHASES).nullable(),
  hrtStatus: z.enum(['no', 'recent', 'long', 'excluded']).nullable(),
  hrtActive: z.boolean(),
  hrtExcluded: z.boolean(),
  fitnessLevel: z.enum(['gentle', 'moderate', 'active']).nullable(),
  budgetMin: z.union([
    z.literal(5), z.literal(10), z.literal(15), z.literal(20), z.literal(30),
  ]).nullable(),
  wakeWindow: z.string().nullable(),
  symptoms: z.record(severitySchema).refine(
    (s) => Object.keys(s).length <= MAX_SELECTED_SYMPTOMS,
    { message: `Höchstens ${MAX_SELECTED_SYMPTOMS} Symptome auswählbar` },
  ),
  preferences: z
    .array(z.enum(PREFERENCES.map((p) => p.id) as [PreferenceId, ...PreferenceId[]]))
    .max(MAX_PREFERENCES),
  restrictions: z.array(z.enum(RESTRICTIONS)).nullable(),
});

/**
 * Run once at the end of onboarding: derive the HRT flags and flip the
 * completion flag. Routing keys off the explicit flag only — never off a
 * heuristic over the fields, or the plan preview gets skipped the moment the
 * last question is answered.
 */
export function finalizeProfile(profile: HealthProfile): HealthProfile {
  const status = profile.hrtStatus ?? 'no';
  return {
    ...profile,
    onboardingComplete: true,
    hrtStatus: status,
    hrtActive: status === 'recent' || status === 'long',
    hrtExcluded: status === 'excluded',
    fitnessLevel: profile.fitnessLevel ?? 'gentle',
    budgetMin: profile.budgetMin ?? 10,
  };
}

export function isOnboardingComplete(profile: HealthProfile): boolean {
  return profile.onboardingComplete === true;
}

// Severity is NOT re-exported here on purpose: index.ts re-exports both
// ./symptoms and ./profile, and a duplicate export name breaks the build.
```

- [ ] **Step 4: Run tests**

```bash
npm test -- profile
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/profile.ts src/core/__tests__/profile.test.ts
git commit -m "feat(core): profile types, zod schema and finalize"
```

---

## Task 15: buildRoutine

The composition point. Everything above feeds it; nothing else composes.

**Files:**
- Create: `src/core/buildRoutine.ts`
- Test: `src/core/__tests__/buildRoutine.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { buildRoutine } from '../buildRoutine';
import { EMPTY_PROFILE } from '../profile';
import type { HealthProfile } from '../profile';

function profileWith(over: Partial<HealthProfile>): HealthProfile {
  return {
    ...EMPTY_PROFILE,
    onboardingComplete: true,
    phase: 'peri',
    hrtStatus: 'no',
    fitnessLevel: 'gentle',
    budgetMin: 15,
    symptoms: { sleep: 3, fatigue: 2 },
    restrictions: [],
    ...over,
  };
}

const input = (over: Partial<HealthProfile> = {}) => ({
  profile: profileWith(over),
  checkin: null,
  weekIndex: 100,
});

describe('buildRoutine', () => {
  it('always includes both anchors', () => {
    const r = buildRoutine(input());
    const ids = r.steps.filter((s) => s.kind === 'module').map((s) => s.moduleId);
    expect(ids).toContain('water');
    expect(ids).toContain('light');
  });

  it('never exceeds the time budget', () => {
    for (const budgetMin of [5, 10, 15, 20, 30] as const) {
      const r = buildRoutine(input({ budgetMin }));
      expect(r.totalMin).toBeLessThanOrEqual(budgetMin);
    }
  });

  it('never turns an out-of-scope symptom into a step', () => {
    const r = buildRoutine(input({ symptoms: { heart: 4, sleep: 3 } }));
    expect(r.outOfScope.map((s) => s.id)).toEqual(['heart']);
    expect(r.steps.some((s) => s.kind === 'module' && s.moduleId === 'breath')).toBe(true);
    expect(r.outOfScope[0]?.referral).toBeTruthy();
  });

  it('excludes every exercise the restrictions rule out', () => {
    const r = buildRoutine(input({ restrictions: ['balance'] }));
    const exerciseIds = r.steps.filter((s) => s.kind === 'exercise').map((s) => s.exerciseId);
    expect(exerciseIds).not.toContain('tree');
  });

  it('keeps only the exercises no restriction rules out', () => {
    const r = buildRoutine(input({ restrictions: ['back', 'knees', 'balance'] }));
    const exerciseIds = r.steps.filter((s) => s.kind === 'exercise').map((s) => s.exerciseId);
    expect(exerciseIds).toEqual(['sidebend']);
  });

  it('produces the same routine twice for the same inputs', () => {
    expect(buildRoutine(input())).toEqual(buildRoutine(input()));
  });

  it('changes the exercise selection across weeks', () => {
    const a = buildRoutine({ ...input(), weekIndex: 100 });
    const b = buildRoutine({ ...input(), weekIndex: 101 });
    const ids = (r: typeof a) => r.steps.filter((s) => s.kind === 'exercise').map((s) => s.exerciseId);
    expect(ids(a)).not.toEqual(ids(b));
  });

  it('reports the Wissen score for the Discover tab', () => {
    const r = buildRoutine(input({ symptoms: { hotFlashes: 4 } }));
    expect(r.categoryScores.wissen).toBeGreaterThan(0);
  });

  it('falls back to breathing when no symptom passes the threshold', () => {
    const r = buildRoutine(input({ symptoms: {} }));
    const ids = r.steps.filter((s) => s.kind === 'module').map((s) => s.moduleId);
    expect(ids).toContain('breath');
    expect(r.totalMin).toBeLessThanOrEqual(15);
  });

  it('adds the Tagesanker as a closing element from budget 10 upward', () => {
    const ids = (min: 5 | 10) =>
      buildRoutine(input({ budgetMin: min }))
        .steps.filter((s) => s.kind === 'module').map((s) => s.moduleId);
    expect(ids(10)).toContain('tagesanker');
    expect(ids(5)).not.toContain('tagesanker');
  });

  it('caps physical modules to gentle on a low-energy morning', () => {
    const r = buildRoutine({
      ...input({ fitnessLevel: 'active', symptoms: { joints: 4 } }),
      checkin: { energy: 1, mood: 3 },
    });
    const movement = r.steps.find((s) => s.kind === 'module' && s.moduleId === 'movement');
    if (movement && movement.kind === 'module') expect(movement.tier).toBe('gentle');
  });

  it('honours an excluded step but never drops an anchor', () => {
    const r = buildRoutine({
      ...input(),
      overrides: { excluded: ['breath', 'water'], added: [] },
    });
    const ids = r.steps.filter((s) => s.kind === 'module').map((s) => s.moduleId);
    expect(ids).toContain('water');
    expect(ids).not.toContain('breath');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- buildRoutine
```

Expected: FAIL — cannot resolve `../buildRoutine`.

- [ ] **Step 3: Write `src/core/buildRoutine.ts`**

```ts
import { anchorModules, modulesForCategory, moduleById } from './catalog';
import type { CatalogModule, ModuleId, Tier } from './catalog';
import { applyEnergyModifier, capsPhysicalTier } from './checkin';
import type { DailyCheckin } from './checkin';
import type { CategoryScores } from './categories';
import { EVIDENCE } from './evidence';
import type { EvidenceKey } from './evidence';
import { exercisesForLevel } from './exercises';
import type { Exercise } from './exercises';
import { applyPhaseModifier } from './phase';
import { applyPreferenceBoost } from './preferences';
import type { HealthProfile } from './profile';
import { filterByRestrictions } from './restrictions';
import { rotate } from './rotation';
import { baseScores, rankCategories } from './scoring';
import { SEVERITY_THRESHOLD, outOfScopeSymptoms, severityOf } from './symptoms';
import type { SymptomItem } from './symptoms';

const TIER_ORDER: readonly Tier[] = ['extended', 'standard', 'gentle'];
const FITNESS_TIER = { gentle: 'gentle', moderate: 'standard', active: 'extended' } as const;

/** Share of the budget reserved for the movement block. */
const MOVEMENT_SHARE = 0.5;
/** Below this budget there is no separate movement block at all. */
const MINI_BUDGET_MAX = 5;

export interface ModuleStep {
  readonly kind: 'module';
  readonly moduleId: ModuleId;
  readonly title: string;
  readonly desc: string;
  readonly minutes: number;
  readonly tier: Tier;
  readonly anchor: boolean;
  readonly evidence: EvidenceKey;
  readonly claimsEfficacy: boolean;
}

export interface ExerciseStep {
  readonly kind: 'exercise';
  readonly exerciseId: string;
  readonly name: string;
  readonly description: string;
  readonly minutes: number;
  readonly media: Exercise['media'];
}

export type RoutineStep = ModuleStep | ExerciseStep;

export interface RoutineOverrides {
  readonly excluded: readonly string[];
  readonly added: readonly ModuleId[];
}

export interface RoutineInput {
  readonly profile: HealthProfile;
  readonly checkin?: DailyCheckin | null;
  readonly weekIndex: number;
  readonly overrides?: RoutineOverrides;
}

export interface Routine {
  readonly steps: readonly RoutineStep[];
  readonly totalMin: number;
  readonly categoryScores: CategoryScores;
  readonly outOfScope: readonly SymptomItem[];
}

function minutesOf(module: CatalogModule, tier: Tier): number {
  return module.variants[tier].minutes;
}

function evidenceOf(module: CatalogModule): EvidenceKey {
  if (module.evidence) return module.evidence;
  return module.evidenceByContext?.default ?? 'kann_helfen';
}

function toStep(module: CatalogModule, tier: Tier): ModuleStep {
  const evidence = evidenceOf(module);
  return {
    kind: 'module',
    moduleId: module.id,
    title: module.title,
    desc: module.variants[tier].desc,
    minutes: minutesOf(module, tier),
    tier,
    anchor: module.anchor === true,
    evidence,
    claimsEfficacy: EVIDENCE[evidence].claimsEfficacy,
  };
}

function intendedTier(module: CatalogModule, profile: HealthProfile, capped: boolean): Tier {
  const physical = module.category === 'bewegung';
  if (physical && capped) return 'gentle';
  if (physical && profile.fitnessLevel) return FITNESS_TIER[profile.fitnessLevel];
  return 'standard';
}

export function buildRoutine(input: RoutineInput): Routine {
  const { profile, weekIndex } = input;
  const checkin = input.checkin ?? null;
  const overrides = input.overrides ?? { excluded: [], added: [] };
  const budget = profile.budgetMin ?? 10;
  const excluded = new Set(overrides.excluded);

  // 1-5. Score the categories through the modifier pipeline.
  const scores = applyEnergyModifier(
    applyPreferenceBoost(
      applyPhaseModifier(baseScores(profile.symptoms), profile.phase),
      profile.preferences,
    ),
    checkin?.energy ?? null,
  );

  // 6. Rank, keeping only categories that actually have modules.
  const ranked = rankCategories(scores)
    .filter((r) => r.score > 0 && modulesForCategory(r.category).length > 0);

  // 7. Movement block first — it competes for the same budget, not on top of it.
  const capped = capsPhysicalTier(checkin?.energy ?? null);
  const pool = filterByRestrictions(
    exercisesForLevel(profile.fitnessLevel ?? 'gentle'),
    profile.restrictions ?? [],
  );
  const exercises: Exercise[] = [];
  let movementSec = 0;

  if (budget > MINI_BUDGET_MAX && pool.length > 0) {
    const targetSec = Math.round(budget * MOVEMENT_SHARE) * 60;
    // 8. Rotation picks which of the eligible exercises show up this week.
    for (const exercise of rotate(pool, weekIndex, pool.length)) {
      if (excluded.has(`ex:${exercise.id}`)) continue;
      if (movementSec + exercise.sec > targetSec) break;
      exercises.push(exercise);
      movementSec += exercise.sec;
    }
  }

  const movementMin = Math.round(movementSec / 60);
  let remaining = budget - movementMin;

  // Anchors are placed before anything competes for the budget.
  const steps: RoutineStep[] = [];
  let totalMin = 0;

  for (const anchor of anchorModules()) {
    const step = toStep(anchor, 'gentle');
    steps.push(step);
    totalMin += step.minutes;
    remaining -= step.minutes;
  }

  // 9-10. Fill the remaining budget from the ranked categories, shortening a
  // module before dropping it.
  const placed = new Set<ModuleId>();
  const rankedModules = ranked.flatMap((r) => modulesForCategory(r.category).slice(0, 1));

  // No symptom cleared the threshold: fall back to the breathing module rather
  // than shipping a morning of nothing but anchors.
  const fallback = rankedModules.length === 0
    ? [moduleById('breath')].filter((m): m is CatalogModule => m !== undefined)
    : [];

  // Concept step 9: a closing element from budget 10 upward.
  //
  // Its minute is RESERVED before the practice modules compete, not appended
  // afterwards. At budget 10 the movement block takes half and the anchors take
  // three minutes, so a closer added last would never fit — the rule would hold
  // only when the budget happened to be generous.
  const closer = budget >= 10 && !excluded.has('tagesanker')
    ? moduleById('tagesanker')
    : undefined;
  const closerMin = closer ? minutesOf(closer, 'gentle') : 0;
  remaining -= closerMin;

  const candidates: CatalogModule[] = [
    ...rankedModules,
    ...fallback,
    ...overrides.added.map(moduleById).filter((m): m is CatalogModule => m !== undefined),
  ];

  for (const module of candidates) {
    if (placed.has(module.id) || excluded.has(module.id)) continue;
    // The closer is already reserved; it must not also win a practice slot.
    if (closer && module.id === closer.id) continue;

    const start = TIER_ORDER.indexOf(intendedTier(module, profile, capped));
    for (let i = Math.max(0, start); i < TIER_ORDER.length; i++) {
      const tier = TIER_ORDER[i]!;
      const minutes = minutesOf(module, tier);
      if (minutes <= remaining) {
        const step = toStep(module, tier);
        steps.push(step);
        totalMin += minutes;
        remaining -= minutes;
        placed.add(module.id);
        break;
      }
    }
  }

  if (closer) {
    steps.push(toStep(closer, 'gentle'));
    totalMin += closerMin;
    placed.add(closer.id);
  }

  for (const exercise of exercises) {
    steps.push({
      kind: 'exercise',
      exerciseId: exercise.id,
      name: exercise.name,
      description: exercise.description,
      minutes: Math.max(1, Math.round(exercise.sec / 60)),
      media: exercise.media,
    });
  }
  totalMin += movementMin;

  const outOfScope = outOfScopeSymptoms().filter(
    (s) => severityOf(profile.symptoms, s.id) >= SEVERITY_THRESHOLD,
  );

  return { steps, totalMin, categoryScores: scores, outOfScope };
}
```

- [ ] **Step 4: Run tests**

```bash
npm test -- buildRoutine
```

Expected: 12 tests pass. If the "changes across weeks" test fails because the eligible pool is smaller than the number of slots, adjust the fixture to use `fitnessLevel: 'moderate'` — do not weaken the assertion.

- [ ] **Step 5: Run the whole suite and typecheck**

```bash
npm test && npm run typecheck
```

Expected: all tests pass, typecheck clean.

- [ ] **Step 6: Commit**

```bash
git add src/core/buildRoutine.ts src/core/__tests__/buildRoutine.test.ts
git commit -m "feat(core): buildRoutine composing the full pipeline"
```

---

## Task 16: Invariant suite and public surface

A separate suite that states the product's safety rules directly, so a future refactor cannot quietly break one.

**Files:**
- Modify: `src/core/index.ts`
- Test: `src/core/__tests__/invariants.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { buildRoutine, EMPTY_PROFILE, EVIDENCE, EXERCISES } from '../index';
import type {
  BudgetMin, FitnessLevel, HealthProfile, Phase, RestrictionId,
} from '../index';

const PHASES: Phase[] = ['peri', 'meno', 'post', 'unsure'];
const BUDGETS: BudgetMin[] = [5, 10, 15, 20, 30];
const LEVELS: FitnessLevel[] = ['gentle', 'moderate', 'active'];
const RESTRICTION_SETS: RestrictionId[][] = [
  [], ['back'], ['knees'], ['balance'], ['back', 'knees', 'shoulders', 'balance'],
];

function* profiles(): Generator<HealthProfile> {
  for (const phase of PHASES) {
    for (const budgetMin of BUDGETS) {
      for (const fitnessLevel of LEVELS) {
        for (const restrictions of RESTRICTION_SETS) {
          yield {
            ...EMPTY_PROFILE,
            onboardingComplete: true,
            phase, budgetMin, fitnessLevel, restrictions,
            hrtStatus: 'no',
            symptoms: { sleep: 3, fatigue: 2, hotFlashes: 4 },
          };
        }
      }
    }
  }
}

describe('engine invariants', () => {
  it('never exceeds the budget, for any profile', () => {
    for (const profile of profiles()) {
      const r = buildRoutine({ profile, checkin: null, weekIndex: 42 });
      expect(r.totalMin).toBeLessThanOrEqual(profile.budgetMin!);
    }
  });

  it('always keeps both anchors, for any profile', () => {
    for (const profile of profiles()) {
      const r = buildRoutine({ profile, checkin: null, weekIndex: 42 });
      const ids = r.steps.filter((s) => s.kind === 'module').map((s) => s.moduleId);
      expect(ids).toContain('water');
      expect(ids).toContain('light');
    }
  });

  it('never contradicts a declared restriction', () => {
    for (const profile of profiles()) {
      const r = buildRoutine({ profile, checkin: null, weekIndex: 42 });
      const blocked = new Set(profile.restrictions ?? []);
      for (const step of r.steps) {
        if (step.kind !== 'exercise') continue;
        const exercise = EXERCISES.find((e) => e.id === step.exerciseId);
        expect(exercise).toBeDefined();
        for (const c of exercise!.contraindications) {
          expect(blocked.has(c)).toBe(false);
        }
      }
    }
  });

  it('never turns an out-of-scope symptom into a step', () => {
    for (const profile of profiles()) {
      const withMedical: HealthProfile = {
        ...profile,
        symptoms: { ...profile.symptoms, heart: 4, bladder: 3 },
      };
      const r = buildRoutine({ profile: withMedical, checkin: null, weekIndex: 42 });
      const ids = r.steps.map((s) => (s.kind === 'module' ? s.moduleId : s.exerciseId));
      expect(ids).not.toContain('heart');
      expect(ids).not.toContain('bladder');
      expect(r.outOfScope.map((o) => o.id).sort()).toEqual(['bladder', 'heart']);
    }
  });

  it('never claims efficacy on a step whose level may not', () => {
    for (const profile of profiles()) {
      const r = buildRoutine({ profile, checkin: null, weekIndex: 42 });
      for (const step of r.steps) {
        if (step.kind !== 'module') continue;
        expect(step.claimsEfficacy).toBe(EVIDENCE[step.evidence].claimsEfficacy);
      }
    }
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- invariants
```

Expected: FAIL — `EXERCISES`, `BudgetMin`, `Phase` and others are not exported from `../index`.

- [ ] **Step 3: Write the public surface in `src/core/index.ts`**

```ts
export const CORE_VERSION = '1.0.0';

export * from './symptoms';
export * from './categories';
export * from './goals';
export * from './evidence';
export * from './scoring';
export * from './phase';
export * from './preferences';
export * from './checkin';
export * from './exercises';
export * from './restrictions';
export * from './rotation';
export * from './catalog';
export * from './profile';
export * from './buildRoutine';
```

- [ ] **Step 4: Run the whole suite and typecheck**

```bash
npm test && npm run typecheck
```

Expected: all tests pass, typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add src/core/index.ts src/core/__tests__/invariants.test.ts
git commit -m "test(core): safety invariants across the profile space"
```

---

## Task 17: README for the core package

**Files:**
- Create: `src/core/README.md`

- [ ] **Step 1: Write the README**

````markdown
# `src/core`

The MorningGlow personalization engine. Pure TypeScript — no React, no Supabase,
no clock, no randomness. Everything is a total function over its arguments.

## Why it is separate

This is the part of the product that decides what a woman with symptoms is shown
in the morning. It has to be testable without a renderer, and it has to be able
to move to the server later so routines can be computed for push notifications.

## Pipeline

```
symptoms + severity
  -> baseScores          (weighting matrix, concept 2.2)
  -> applyPhaseModifier  (concept 2.3)
  -> applyPreferenceBoost(concept 2.5)
  -> applyEnergyModifier (concept 2.6)
  -> rankCategories
  -> buildRoutine        (budget, rotation, restrictions)
```

## Invariants

Enforced by `__tests__/invariants.test.ts` across the whole profile space:

1. The total never exceeds the time budget.
2. Both anchors — water and morning light — are always present.
3. No exercise contradicts a declared physical restriction.
4. No out-of-scope symptom ever becomes a routine step.
5. Only the `hilft` evidence level may claim efficacy.

## Open review items

- Exercise contraindications in `exercises.ts` are a first pass by a
  non-clinician and require physiotherapist review before release.
- `PHASE_MODIFIERS.earlyPeri` is unreachable: the concept defines five phases,
  the onboarding collects four.
- `ernaehrung` and `wissen` receive scores but have no modules in v1. The
  Wissen score is consumed by the Discover tab.
- The concept's "Entdeckungs-Element" — at least one non-top category per week —
  needs no machinery in v1. Only three categories carry modules, and all three
  are already candidates on every build; the budget, not the ranking, decides
  which get in. Revisit when Ernährung gains modules in v2.
````

- [ ] **Step 2: Commit**

```bash
git add src/core/README.md
git commit -m "docs(core): pipeline, invariants and open review items"
```

---

## Definition of done

- [ ] `npm test` passes with every task's suite green
- [ ] `npm run typecheck` is clean under `strict` and `noUncheckedIndexedAccess`
- [ ] `src/core/` contains no import of React, React Native, Supabase, or any I/O
- [ ] `grep -rn "Date.now\|Math.random\|new Date()" src/core --include=*.ts` returns
      nothing outside `__tests__` — the engine must stay reproducible
