# MorningGlow Design System — Implementation Plan (Etappe 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the Expo app and build `src/ui/` — the token set and the component vocabulary every later screen is assembled from — plus a gallery screen that renders all of it on a device.

**Architecture:** Tokens are plain data in one module; components consume tokens and never hard-code a color or a size. The design system knows nothing about the engine, the database, or navigation. A gallery route renders every component and every state, so a regression is visible rather than inferred.

**Tech Stack:** Expo SDK 54 (RN 0.81, New Architecture), expo-router, react-native-svg, expo-linear-gradient, expo-blur, @expo-google-fonts/plus-jakarta-sans, react-native-reanimated.

**Spec:** `docs/superpowers/specs/2026-08-29-morningglow-design.md`

**Depends on:** nothing. Runs in the same repo as Etappen 1–2 but touches no file they own.

---

## The three risks this stage exists to settle

The spec flagged three places where the prototype cannot port literally. Each gets decided here, once, in a token — not rediscovered per screen.

**Shadows — resolved, verified against the docs.** `boxShadow` ships with the New Architecture (RN 0.76+, default in Expo SDK 54), accepts a color, and works on Android 9+. The prototype's warm amber glow ports as-is. On Android 8 and older the shadow is simply absent; nothing breaks. So: **one `boxShadow` token per elevation, no `elevation` fallback, no gradient trickery.**

**Fonts — static weights.** Plus Jakarta Sans is a variable font in the bundle, and variable axes are unreliable on Android in RN. `@expo-google-fonts/plus-jakarta-sans` ships static cuts. The prototype uses 400/600/700/800; we load exactly those four and no others, because every extra cut is bytes on a cold start.

**Blur — `expo-blur`, and only where it earns it.** The prototype uses `backdropFilter` in exactly two places: the modal layer and the floating back button. `expo-blur` covers both. It is not free on Android, so it stays confined to those two components rather than becoming a decorative habit.

### Why some components come in two files

vitest runs in Node and cannot resolve `react-native`. Any test that imports a
`.tsx` component fails on the import rather than on the assertion — so every
piece of logic worth testing (the ring arithmetic, the slider's value mapping,
the evidence palette) lives in a plain `.ts` module beside the component, and
the component imports it. Same rule the engine already follows: the part worth
testing does not depend on a renderer.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/_layout.tsx` | Root layout: font loading, splash gate |
| `app/gallery.tsx` | Every component, every state — the visual regression surface |
| `src/ui/tokens.ts` | Colors, gradients, shadows, radii, spacing, type scale |
| `src/ui/typography.ts` | Font family map + `Text` presets |
| `src/ui/Text.tsx` | The only text primitive; no raw `<Text>` elsewhere |
| `src/ui/Screen.tsx` | Gradient ground + safe area |
| `src/ui/Button.tsx` | 4 variants × 3 sizes |
| `src/ui/Card.tsx` | Surface with the amber glow |
| `src/ui/Chip.tsx` | Selectable pill |
| `src/ui/OptionCard.tsx` | Large single-choice tile used all through onboarding |
| `src/ui/evidencePalette.ts` | Colour per evidence level — pure, so it is testable in Node |
| `src/ui/Badge.tsx` | Evidence badge, driven by `core/evidence` |
| `src/ui/ringGeometry.ts` | Ring arithmetic — pure |
| `src/ui/ProgressRing.tsx` | SVG ring with the coral→amber sweep |
| `src/ui/severityScale.ts` | Track ratio → 0–4 step and its colour — pure |
| `src/ui/SeveritySlider.tsx` | The 0–4 gesture control |
| `src/ui/Sun.tsx` | The brand mark, real path from the prototype |
| `src/ui/icons.tsx` | Module line icons |
| `src/ui/index.ts` | Public surface |

---

## Task 1: Expo scaffold beside the existing core

The repo already holds `src/core`, `src/data`, `tests/` and a vitest setup. Expo must move in without disturbing them — in particular without vitest and jest fighting over the same test files.

**Files:**
- Modify: `package.json`
- Create: `app.json`, `babel.config.js`, `metro.config.js`, `index.ts`
- Modify: `tsconfig.json`

- [ ] **Step 1: Install Expo and the UI dependencies**

Do **not** pin versions by hand. `npx expo install` resolves what the SDK
actually ships; pinning gave reanimated 4.6, which demands RN 0.83+, while SDK
54 is on 0.81 — an unsolvable peer conflict produced by a guess.

`app.json` (Step 2) must exist before `expo install` runs, or its plugin step
throws. Write it first, then come back here.

```
npm install expo@~54.0.0
npx expo install react react-dom react-native expo-router react-native-safe-area-context react-native-screens react-native-svg expo-linear-gradient expo-blur expo-font expo-splash-screen expo-status-bar react-native-reanimated react-native-gesture-handler
npx expo install @expo-google-fonts/plus-jakarta-sans
npx expo install --dev @types/react
npx expo install --dev babel-preset-expo
```

`babel-preset-expo` is installed explicitly. It arrives transitively, but Babel
resolves presets from the project's own `package.json` and otherwise fails with
"Cannot find module 'babel-preset-expo'".

It must go through `expo install`, never `npm install -D`. Plain npm takes the
latest major (57), which is built for a newer Hermes that already parses
private class fields and so leaves `#private` untranspiled. SDK 54's Hermes
cannot read it, and the app dies before it starts with "private properties are
not supported" — thrown by React Native's own modules, not by ours. The same
mismatch also breaks `expo export`. Verify with `npx expo install --check`.

- [ ] **Step 2: Write `app.json`**

```json
{
  "expo": {
    "name": "MorningGlow",
    "slug": "morningglow",
    "version": "0.1.0",
    "orientation": "portrait",
    "scheme": "morningglow",
    "userInterfaceStyle": "light",
    "newArchEnabled": true,
    "backgroundColor": "#FFF8E1",
    "ios": { "supportsTablet": false, "bundleIdentifier": "com.morningglow.app" },
    "android": {
      "package": "com.morningglow.app",
      "adaptiveIcon": { "backgroundColor": "#FFF8E1" }
    },
    "plugins": ["expo-router", "expo-font"],
    "experiments": { "typedRoutes": true }
  }
}
```

`userInterfaceStyle` is pinned to `light` deliberately: the brand is a single warm cream world and there is no dark palette in the prototype. A dark theme is a design project, not a toggle, and inventing one here would produce a second look nobody has approved.

`newArchEnabled` is what makes `boxShadow` available. Without it the shadow decision above does not hold.

- [ ] **Step 3: Write `babel.config.js`**

```js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: ['react-native-reanimated/plugin'],
  };
};
```

The reanimated plugin must be last in the list. It rewrites worklets, and anything appended after it will not be transformed.

- [ ] **Step 4: Write `metro.config.js`**

```js
const { getDefaultConfig } = require('expo/metro-config');

module.exports = getDefaultConfig(__dirname);
```

- [ ] **Step 5: Write `index.ts`**

```ts
import 'expo-router/entry';
```

- [ ] **Step 6: Point `package.json` at Expo without breaking vitest**

Etappe 1 set `"type": "module"`. It has to go: `babel.config.js` and
`metro.config.js` are CommonJS and fail to load under it.

```json
{
  "main": "expo-router/entry",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "test": "vitest run --exclude tests/db",
    "test:watch": "vitest",
    "test:db": "vitest run tests/db",
    "typecheck": "tsc --noEmit",
    "db:push": "supabase db push",
    "db:seed": "tsx scripts/gen-seed.ts",
    "db:migrate": "tsx scripts/migrate.ts"
  }
}
```

- [ ] **Step 7: Widen `tsconfig.json` for JSX and the app directory**

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noEmit": true,
    "skipLibCheck": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals"],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src", "app", "scripts", "tests", "index.ts"]
}
```

- [ ] **Step 8: Verify the core suite still passes and types still check**

```bash
npm test && npm run typecheck
```

Expected: 131 tests pass, typecheck clean. If `tsc` now complains about React types in `src/core`, the core has picked up a dependency it must not have — fix that rather than loosening the config.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore(ui): Expo scaffold with the New Architecture enabled"
```

---

## Task 2: Tokens

Every color, radius and shadow the app will ever use, in one file, taken from the prototype's `MG` object.

**Files:**
- Create: `src/ui/tokens.ts`
- Test: `src/ui/__tests__/tokens.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { colors, shadows, radii, space, typeScale } from '../tokens';

describe('tokens', () => {
  it('carries the brand palette from the prototype', () => {
    expect(colors.bg).toBe('#FFF8E1');
    expect(colors.primary).toBe('#FF9494');
    expect(colors.textPrimary).toBe('#43311E');
  });

  it('states every shadow as a boxShadow string, never elevation', () => {
    for (const value of Object.values(shadows)) {
      expect(typeof value).toBe('string');
      expect(value).toMatch(/rgba?\(/);
    }
  });

  it('keeps the shadows warm rather than black', () => {
    // The prototype's glow is amber; a black shadow would read as a different product.
    for (const value of Object.values(shadows)) {
      expect(value).not.toMatch(/rgba\(0, ?0, ?0/);
    }
  });

  it('uses a 4-point spacing rhythm', () => {
    for (const value of Object.values(space)) {
      expect(value % 4).toBe(0);
    }
  });

  it('orders the type scale from small to large', () => {
    const sizes = Object.values(typeScale).map((t) => t.size);
    expect([...sizes].sort((a, b) => a - b)).toEqual(sizes);
  });

  it('offers the radii the prototype uses', () => {
    expect(radii.md).toBe(12);
    expect(radii.lg).toBe(20);
    expect(radii.pill).toBeGreaterThan(100);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- tokens
```

Expected: FAIL — cannot resolve `../tokens`.

- [ ] **Step 3: Write `src/ui/tokens.ts`**

```ts
/**
 * The whole visual vocabulary, taken from the prototype's MG object.
 *
 * Nothing outside this file may name a color, a radius or a shadow. When a
 * screen needs a shade that is not here, the answer is to add it here with a
 * name, not to inline a hex value at the call site.
 */

export const colors = {
  bg:            '#FFF8E1',
  card:          '#FFFCF0',
  cardPlain:     '#FFFFFF',
  muted:         '#FFEFB8',
  primary:       '#FF9494',
  medium:        '#FF9E80',
  light:         '#FFB74D',
  darkest:       '#FF6666',
  textPrimary:   '#43311E',
  textSecondary: '#6F5B42',
  textMuted:     '#9C8870',
  success:       '#D4A422',
  border:        '#F1E2BE',
  borderSoft:    '#F6E9CD',
  white:         '#FFFFFF',
  scrim:         'rgba(48,30,16,0.42)',
} as const;

/** Gradient stop pairs. Consumed by expo-linear-gradient, never by a `background`. */
export const gradients = {
  golden:  ['#FF9494', '#FFB74D'],
  deep:    ['#FF6666', '#FF9E80'],
  sunrise: ['#FFE8D6', '#FFF0DE', '#FFF6E6'],
  dawn:    ['#FFE8D6', '#FFF4DC', '#FFF8E1'],
  warm:    ['#FFEAD0', '#FFF5DF'],
} as const;

/**
 * boxShadow strings, not elevation.
 *
 * The New Architecture (default in Expo SDK 54) supports boxShadow with a
 * color on Android 9+, so the prototype's amber glow survives the port. On
 * Android 8 and older the shadow is dropped entirely — the surface stays
 * clean, it just loses depth.
 */
export const shadows = {
  card:   '0px 2px 8px rgba(245,185,66,0.10)',
  medium: '0px 4px 16px rgba(245,185,66,0.15)',
  strong: '0px 8px 32px rgba(184,125,13,0.18)',
  glow:   '0px 0px 24px rgba(255,148,148,0.35)',
  button: '0px 6px 18px rgba(255,148,148,0.35)',
} as const;

export const radii = { sm: 8, md: 12, lg: 20, xl: 28, pill: 999 } as const;

/** A 4-point rhythm. Every gap and padding in the app comes from here. */
export const space = {
  xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32, huge: 48,
} as const;

export interface TypeStyle {
  readonly size: number;
  readonly lineHeight: number;
  readonly weight: '400' | '600' | '700' | '800';
  readonly letterSpacing?: number;
}

/** Ordered small to large; a test enforces the ordering. */
export const typeScale = {
  caption: { size: 11.5, lineHeight: 16, weight: '600', letterSpacing: 0.6 },
  small:   { size: 12.5, lineHeight: 18, weight: '400' },
  body:    { size: 14.5, lineHeight: 21, weight: '400' },
  bodyLg:  { size: 16,   lineHeight: 24, weight: '400' },
  title:   { size: 20,   lineHeight: 27, weight: '700', letterSpacing: -0.2 },
  heading: { size: 24,   lineHeight: 31, weight: '700', letterSpacing: -0.3 },
  display: { size: 30,   lineHeight: 37, weight: '800', letterSpacing: -0.5 },
} as const satisfies Record<string, TypeStyle>;

export type TypeVariant = keyof typeof typeScale;
export type ColorToken = keyof typeof colors;
```

- [ ] **Step 4: Run tests and commit**

```bash
npm test -- tokens && npm run typecheck
git add src/ui/tokens.ts src/ui/__tests__/tokens.test.ts
git commit -m "feat(ui): design tokens, shadows as colored boxShadow"
```

Expected: 6 tests pass.

---

## Task 3: Fonts and the text primitive

**Files:**
- Create: `src/ui/typography.ts`, `src/ui/Text.tsx`
- Create: `app/_layout.tsx`
- Test: `src/ui/__tests__/typography.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { fontFamilyFor, FONT_WEIGHTS } from '../typography';

describe('typography', () => {
  it('loads exactly the four weights the prototype uses', () => {
    expect(FONT_WEIGHTS).toEqual(['400', '600', '700', '800']);
  });

  it('maps a weight to a named static family, never a variable axis', () => {
    // Variable font axes are unreliable on Android in React Native, so each
    // weight is its own file and the family name carries the weight.
    expect(fontFamilyFor('400')).toBe('PlusJakartaSans_400Regular');
    expect(fontFamilyFor('700')).toBe('PlusJakartaSans_700Bold');
  });

  it('falls back to regular for a weight that was not loaded', () => {
    expect(fontFamilyFor('300' as never)).toBe('PlusJakartaSans_400Regular');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- typography
```

Expected: FAIL — cannot resolve `../typography`.

- [ ] **Step 3: Write `src/ui/typography.ts`**

```ts
import { typeScale } from './tokens';
import type { TypeVariant } from './tokens';

/**
 * Four static cuts, not a variable font.
 *
 * The bundle ships Plus Jakarta Sans as a single variable TTF spanning 200–800.
 * React Native does not drive variable axes reliably on Android, so each weight
 * is its own file. Four is what the prototype actually uses; every further cut
 * is bytes on a cold start for a weight nobody asked for.
 */
export const FONT_WEIGHTS = ['400', '600', '700', '800'] as const;
export type FontWeight = (typeof FONT_WEIGHTS)[number];

const FAMILIES: Record<FontWeight, string> = {
  '400': 'PlusJakartaSans_400Regular',
  '600': 'PlusJakartaSans_600SemiBold',
  '700': 'PlusJakartaSans_700Bold',
  '800': 'PlusJakartaSans_800ExtraBold',
};

export function fontFamilyFor(weight: FontWeight): string {
  return FAMILIES[weight] ?? FAMILIES['400'];
}

export function styleFor(variant: TypeVariant) {
  const t = typeScale[variant];
  return {
    fontFamily: fontFamilyFor(t.weight),
    fontSize: t.size,
    lineHeight: t.lineHeight,
    ...(('letterSpacing' in t && t.letterSpacing !== undefined)
      ? { letterSpacing: t.letterSpacing }
      : {}),
  };
}
```

- [ ] **Step 4: Write `src/ui/Text.tsx`**

```tsx
import { Text as RNText } from 'react-native';
import type { TextProps as RNTextProps } from 'react-native';
import { colors } from './tokens';
import type { ColorToken, TypeVariant } from './tokens';
import { styleFor } from './typography';

export interface TextProps extends RNTextProps {
  readonly variant?: TypeVariant;
  readonly color?: ColorToken;
  readonly center?: boolean;
}

/**
 * The only text primitive in the app.
 *
 * A raw <Text> silently falls back to the system font, and that failure is
 * invisible in a screenshot until someone compares it to the prototype. Going
 * through one component means the font can never be forgotten.
 */
export function Text({
  variant = 'body',
  color = 'textPrimary',
  center = false,
  style,
  ...rest
}: TextProps) {
  return (
    <RNText
      {...rest}
      style={[
        styleFor(variant),
        { color: colors[color] },
        center && { textAlign: 'center' },
        style,
      ]}
    />
  );
}
```

- [ ] **Step 5: Write `app/_layout.tsx`**

```tsx
import { useFonts } from 'expo-font';
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
  PlusJakartaSans_800ExtraBold,
} from '@expo-google-fonts/plus-jakarta-sans';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { colors } from '../src/ui/tokens';

void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    PlusJakartaSans_400Regular,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    PlusJakartaSans_800ExtraBold,
  });

  useEffect(() => {
    // Hide on error too: a missing font must not leave the user staring at a
    // splash screen forever. The app degrades to the system face instead.
    if (loaded || error) void SplashScreen.hideAsync();
  }, [loaded, error]);

  if (!loaded && !error) return null;

  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.bg },
        }}
      />
    </>
  );
}
```

- [ ] **Step 6: Run and commit**

```bash
npm test -- typography && npm run typecheck
git add src/ui/typography.ts src/ui/Text.tsx app/_layout.tsx src/ui/__tests__/typography.test.ts
git commit -m "feat(ui): static font weights, single text primitive, font gate"
```

Expected: 3 tests pass.

---

## Task 4: Screen and Card

**Files:**
- Create: `src/ui/Screen.tsx`, `src/ui/Card.tsx`

- [ ] **Step 1: Write `src/ui/Screen.tsx`**

```tsx
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StyleSheet, View } from 'react-native';
import type { ReactNode } from 'react';
import { colors, gradients, space } from './tokens';

export interface ScreenProps {
  readonly children: ReactNode;
  /** The sunrise wash. Off for surfaces that sit inside a modal. */
  readonly gradient?: boolean;
  readonly padded?: boolean;
}

export function Screen({ children, gradient = true, padded = true }: ScreenProps) {
  const body = (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <View style={[styles.inner, padded && styles.padded]}>{children}</View>
    </SafeAreaView>
  );

  if (!gradient) return <View style={styles.plain}>{body}</View>;

  return (
    <LinearGradient
      colors={gradients.dawn}
      locations={[0, 0.55, 1]}
      style={StyleSheet.absoluteFill}
    >
      {body}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  inner: { flex: 1 },
  padded: { paddingHorizontal: space.xl },
  plain: { flex: 1, backgroundColor: colors.bg },
});
```

- [ ] **Step 2: Write `src/ui/Card.tsx`**

```tsx
import { StyleSheet, View } from 'react-native';
import type { ViewProps } from 'react-native';
import type { ReactNode } from 'react';
import { colors, radii, shadows, space } from './tokens';

export interface CardProps extends ViewProps {
  readonly children: ReactNode;
  readonly elevation?: 'card' | 'medium' | 'strong' | 'none';
  readonly padded?: boolean;
}

export function Card({
  children,
  elevation = 'card',
  padded = true,
  style,
  ...rest
}: CardProps) {
  return (
    <View
      {...rest}
      style={[
        styles.base,
        padded && styles.padded,
        // boxShadow, not elevation: the glow is amber and elevation is grey.
        elevation !== 'none' && { boxShadow: shadows[elevation] },
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.card,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.borderSoft,
  },
  padded: { padding: space.xl },
});
```

- [ ] **Step 3: Typecheck and commit**

```bash
npm run typecheck
git add src/ui/Screen.tsx src/ui/Card.tsx
git commit -m "feat(ui): screen shell and card surface"
```

---

## Task 5: Button

**Files:**
- Create: `src/ui/Button.tsx`

- [ ] **Step 1: Write it**

```tsx
import { LinearGradient } from 'expo-linear-gradient';
import { Pressable, StyleSheet, View } from 'react-native';
import type { ReactNode } from 'react';
import { colors, gradients, radii, shadows, space } from './tokens';
import { Text } from './Text';

export type ButtonVariant = 'primary' | 'strong' | 'outline' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps {
  readonly label: string;
  readonly onPress?: () => void;
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly disabled?: boolean;
  readonly leading?: ReactNode;
}

const SIZES = {
  sm: { paddingVertical: space.sm,  paddingHorizontal: space.lg,  minHeight: 36 },
  md: { paddingVertical: space.md,  paddingHorizontal: space.xl,  minHeight: 44 },
  lg: { paddingVertical: space.lg,  paddingHorizontal: space.xxl, minHeight: 52 },
} as const;

export function Button({
  label, onPress, variant = 'primary', size = 'lg', disabled = false, leading,
}: ButtonProps) {
  const gradient = variant === 'primary' || variant === 'strong';

  const content = (
    <View style={styles.row}>
      {leading}
      <Text
        variant={size === 'sm' ? 'small' : 'bodyLg'}
        color={gradient ? 'white' : 'textPrimary'}
        style={styles.label}
      >
        {label}
      </Text>
    </View>
  );

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        SIZES[size],
        variant === 'outline' && styles.outline,
        variant === 'ghost' && styles.ghost,
        gradient && { boxShadow: shadows.button },
        disabled && styles.disabled,
        // A press should read as a press without a spring: this is a calm app.
        pressed && !disabled && styles.pressed,
      ]}
    >
      {gradient ? (
        <LinearGradient
          colors={variant === 'strong' ? gradients.deep : gradients.golden}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[StyleSheet.absoluteFill, { borderRadius: radii.md }]}
        />
      ) : null}
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  label: { fontWeight: undefined },
  outline: { borderWidth: 1.5, borderColor: colors.light, backgroundColor: 'transparent' },
  ghost: { backgroundColor: 'transparent' },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.85 },
});
```

- [ ] **Step 2: Typecheck and commit**

```bash
npm run typecheck
git add src/ui/Button.tsx
git commit -m "feat(ui): button with gradient, outline and ghost variants"
```

---

## Task 6: Chip and OptionCard

**Files:**
- Create: `src/ui/Chip.tsx`, `src/ui/OptionCard.tsx`

- [ ] **Step 1: Write `src/ui/Chip.tsx`**

```tsx
import { Pressable, StyleSheet } from 'react-native';
import { colors, radii, space } from './tokens';
import { Text } from './Text';

export interface ChipProps {
  readonly label: string;
  readonly selected?: boolean;
  readonly onPress?: () => void;
}

export function Chip({ label, selected = false, onPress }: ChipProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.base, selected && styles.selected]}
    >
      <Text variant="small" color={selected ? 'white' : 'textSecondary'}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    paddingVertical: space.sm,
    paddingHorizontal: space.lg,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  selected: { backgroundColor: colors.primary, borderColor: colors.primary },
});
```

- [ ] **Step 2: Write `src/ui/OptionCard.tsx`**

```tsx
import { Pressable, StyleSheet, View } from 'react-native';
import type { ReactNode } from 'react';
import { colors, radii, shadows, space } from './tokens';
import { Text } from './Text';

export interface OptionCardProps {
  readonly label: string;
  readonly sublabel?: string;
  readonly icon?: ReactNode;
  readonly selected?: boolean;
  readonly onPress?: () => void;
}

/**
 * The single-choice tile the onboarding leans on. Large by intent: the
 * audience is 45–70 and these are answered on a phone before coffee.
 */
export function OptionCard({
  label, sublabel, icon, selected = false, onPress,
}: OptionCardProps) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[
        styles.base,
        selected && styles.selected,
        selected && { boxShadow: shadows.glow },
      ]}
    >
      {icon ? <View style={styles.icon}>{icon}</View> : null}
      <View style={styles.body}>
        <Text variant="bodyLg" color="textPrimary">{label}</Text>
        {sublabel ? (
          <Text variant="small" color="textMuted">{sublabel}</Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.lg,
    padding: space.xl,
    minHeight: 72,
    borderRadius: radii.lg,
    borderWidth: 1.5,
    borderColor: colors.borderSoft,
    backgroundColor: colors.card,
  },
  selected: { borderColor: colors.primary, backgroundColor: colors.white },
  icon: { width: 32, alignItems: 'center' },
  body: { flex: 1, gap: 2 },
});
```

- [ ] **Step 3: Typecheck and commit**

```bash
npm run typecheck
git add src/ui/Chip.tsx src/ui/OptionCard.tsx
git commit -m "feat(ui): chip and option card"
```

---

## Task 7: The brand sun

**Files:**
- Create: `src/ui/Sun.tsx`

- [ ] **Step 1: Write it, with the path lifted verbatim from the prototype**

```tsx
import Svg, { G, Path } from 'react-native-svg';
import { colors } from './tokens';

export interface SunProps {
  readonly size?: number;
  readonly color?: string;
}

/**
 * The MorningGlow sun: a rising dome over two horizon lines.
 *
 * The path is copied verbatim from the prototype rather than redrawn — it is
 * the registered brand mark, and an approximation would be a different logo.
 */
export function Sun({ size = 28, color = colors.primary }: SunProps) {
  return (
    <Svg width={size} height={size} viewBox="-6 -6 112 109" fill="none" accessibilityRole="image">
      <G translateX={-59.5778} translateY={0}>
        <Path
          d="M127.578 97H91.5778V90H127.578V97ZM143.578 87H75.5778V80H143.578V87ZM109.578 0C137.192 0 159.578 22.3858 159.578 50C159.578 59.9455 156.674 69.2125 151.668 77H67.4879C62.482 69.2125 59.5778 59.9455 59.5778 50C59.5778 22.3858 81.9635 0 109.578 0ZM109.578 7C85.8295 7 66.5778 26.2518 66.5778 50C66.5778 57.2218 68.3619 64.0254 71.5084 70H147.647C150.794 64.0254 152.578 57.2218 152.578 50C152.578 26.2518 133.326 7 109.578 7Z"
          fill={color}
        />
      </G>
    </Svg>
  );
}
```

- [ ] **Step 2: Typecheck and commit**

```bash
npm run typecheck
git add src/ui/Sun.tsx
git commit -m "feat(ui): brand sun, path taken verbatim from the prototype"
```

---

## Task 8: Evidence badge

Driven by `core/evidence` so the language rule cannot drift between engine and interface.

**Files:**
- Create: `src/ui/evidencePalette.ts`, `src/ui/Badge.tsx`
- Test: `src/ui/__tests__/evidencePalette.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { EVIDENCE_KEYS } from '../../core/evidence';
// From the pure module, not from Badge.tsx: vitest runs in Node and cannot
// resolve 'react-native', so importing the component would fail on the import.
import { evidencePalette } from '../evidencePalette';

describe('evidence palette', () => {
  it('has a colour pair for every level the engine defines', () => {
    for (const key of EVIDENCE_KEYS) {
      expect(evidencePalette[key]).toBeDefined();
      expect(evidencePalette[key].fg).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(evidencePalette[key].bg).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('gives only the efficacy-claiming level the green treatment', () => {
    expect(evidencePalette.hilft.fg).toBe('#3F7D5A');
    for (const key of EVIDENCE_KEYS) {
      if (key !== 'hilft') expect(evidencePalette[key].fg).not.toBe('#3F7D5A');
    }
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- evidencePalette
```

Expected: FAIL — cannot resolve `../evidencePalette`.

- [ ] **Step 3: Write `src/ui/evidencePalette.ts`**

```ts
import type { EvidenceKey } from '../core/evidence';

/**
 * Colour per evidence level, from the prototype.
 *
 * Not in core: core must stay renderer-agnostic, and a hex value is a
 * presentation decision. Not in Badge.tsx either, so a Node test can import it
 * without dragging react-native along. Keyed by EvidenceKey, so adding a level
 * to the engine breaks this file at compile time rather than rendering
 * colourless at runtime.
 */
export const evidencePalette: Record<EvidenceKey, { fg: string; bg: string }> = {
  hilft:       { fg: '#3F7D5A', bg: '#E3F1E7' },
  kann_helfen: { fg: '#B07A1C', bg: '#FBEFD4' },
  tut_gut:     { fg: '#8C8579', bg: '#EFECE4' },
  mechanismus: { fg: '#4E7C92', bg: '#E5EFF3' },
  anker:       { fg: '#8C7B62', bg: '#F1E9D8' },
  reflexion:   { fg: '#7E6BA8', bg: '#ECE6F5' },
};
```

- [ ] **Step 4: Write `src/ui/Badge.tsx`**

```tsx
import { StyleSheet, View } from 'react-native';
import { EVIDENCE } from '../core/evidence';
import type { EvidenceKey } from '../core/evidence';
import { evidencePalette } from './evidencePalette';
import { radii, space } from './tokens';
import { Text } from './Text';

export interface BadgeProps {
  readonly evidence: EvidenceKey;
}

export function Badge({ evidence }: BadgeProps) {
  const level = EVIDENCE[evidence];
  const palette = evidencePalette[evidence];

  return (
    <View style={[styles.base, { backgroundColor: palette.bg }]}>
      <Text variant="caption" style={{ color: palette.fg }}>
        {level.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    alignSelf: 'flex-start',
    paddingVertical: 3,
    paddingHorizontal: space.md,
    borderRadius: radii.pill,
  },
});
```

- [ ] **Step 5: Run and commit**

```bash
npm test -- evidencePalette && npm run typecheck
git add src/ui/evidencePalette.ts src/ui/Badge.tsx src/ui/__tests__/evidencePalette.test.ts
git commit -m "feat(ui): evidence badge driven by the engine's levels"
```

Expected: 2 tests pass.

---

## Task 9: Progress ring

**Files:**
- Create: `src/ui/ringGeometry.ts`, `src/ui/ProgressRing.tsx`
- Test: `src/ui/__tests__/ringGeometry.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { ringGeometry } from '../ringGeometry';

describe('ringGeometry', () => {
  it('leaves the ring empty at zero', () => {
    const g = ringGeometry({ value: 0, total: 5, size: 160, stroke: 14 });
    expect(g.dashOffset).toBe(g.circumference);
  });

  it('closes the ring when everything is done', () => {
    const g = ringGeometry({ value: 5, total: 5, size: 160, stroke: 14 });
    expect(g.dashOffset).toBe(0);
  });

  it('is half drawn at half progress', () => {
    const g = ringGeometry({ value: 2, total: 4, size: 100, stroke: 10 });
    expect(g.dashOffset).toBeCloseTo(g.circumference / 2, 5);
  });

  it('keeps the stroke inside the viewbox', () => {
    const g = ringGeometry({ value: 1, total: 5, size: 100, stroke: 20 });
    expect(g.radius + 20 / 2).toBeLessThanOrEqual(50);
  });

  it('clamps a value beyond the total instead of overdrawing', () => {
    const g = ringGeometry({ value: 9, total: 5, size: 100, stroke: 10 });
    expect(g.dashOffset).toBe(0);
  });

  it('treats a total of zero as empty rather than dividing by zero', () => {
    const g = ringGeometry({ value: 3, total: 0, size: 100, stroke: 10 });
    expect(Number.isFinite(g.dashOffset)).toBe(true);
    expect(g.dashOffset).toBe(g.circumference);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- ringGeometry
```

Expected: FAIL — cannot resolve `../ringGeometry`.

- [ ] **Step 3: Write `src/ui/ringGeometry.ts`**

```ts
export interface RingInput {
  readonly value: number;
  readonly total: number;
  readonly size: number;
  readonly stroke: number;
}

export interface RingGeometry {
  readonly radius: number;
  readonly circumference: number;
  readonly dashOffset: number;
}

/**
 * Pure geometry, separated so it can be tested without a renderer — the
 * arithmetic is where an off-by-one shows up as a ring that never closes.
 */
export function ringGeometry({ value, total, size, stroke }: RingInput): RingGeometry {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const ratio = total > 0 ? Math.min(1, Math.max(0, value / total)) : 0;
  return { radius, circumference, dashOffset: circumference * (1 - ratio) };
}

```

- [ ] **Step 4: Write `src/ui/ProgressRing.tsx`**

```tsx
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
import { View } from 'react-native';
import type { ReactNode } from 'react';
import { ringGeometry } from './ringGeometry';
import type { RingInput } from './ringGeometry';
import { colors, gradients } from './tokens';

export interface ProgressRingProps extends RingInput {
  readonly children?: ReactNode;
}

export function ProgressRing({
  value, total, size = 160, stroke = 14, children,
}: Partial<ProgressRingProps> & { value: number; total: number }) {
  const g = ringGeometry({ value, total, size, stroke });
  const centre = size / 2;

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute' }}>
        <Defs>
          <LinearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor={gradients.golden[0]} />
            <Stop offset="1" stopColor={gradients.golden[1]} />
          </LinearGradient>
        </Defs>
        <Circle
          cx={centre} cy={centre} r={g.radius}
          stroke={colors.borderSoft} strokeWidth={stroke} fill="none"
        />
        <Circle
          cx={centre} cy={centre} r={g.radius}
          stroke="url(#ring)" strokeWidth={stroke} fill="none"
          strokeDasharray={g.circumference}
          strokeDashoffset={g.dashOffset}
          strokeLinecap="round"
          // Start at twelve o'clock rather than three.
          transform={`rotate(-90 ${centre} ${centre})`}
        />
      </Svg>
      {children}
    </View>
  );
}
```

- [ ] **Step 5: Run and commit**

```bash
npm test -- ringGeometry && npm run typecheck
git add src/ui/ringGeometry.ts src/ui/ProgressRing.tsx src/ui/__tests__/ringGeometry.test.ts
git commit -m "feat(ui): progress ring with testable geometry"
```

Expected: 6 tests pass.

---

## Task 10: Severity slider

The one control with real interaction. Its value mapping is pure and tested; the gesture layer is thin on top.

**Files:**
- Create: `src/ui/severityScale.ts`, `src/ui/SeveritySlider.tsx`
- Test: `src/ui/__tests__/severityScale.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest';
import { severityFromRatio, severityFillColor } from '../severityScale';

describe('severityFromRatio', () => {
  it('maps the ends of the track to the ends of the scale', () => {
    expect(severityFromRatio(0)).toBe(0);
    expect(severityFromRatio(1)).toBe(4);
  });

  it('snaps to the nearest step', () => {
    expect(severityFromRatio(0.24)).toBe(1);
    expect(severityFromRatio(0.26)).toBe(1);
    expect(severityFromRatio(0.5)).toBe(2);
  });

  it('clamps a drag past either end', () => {
    expect(severityFromRatio(-3)).toBe(0);
    expect(severityFromRatio(7)).toBe(4);
  });
});

describe('severityFillColor', () => {
  it('stays neutral below the threshold and warms above it', () => {
    expect(severityFillColor(0)).toBe(severityFillColor(0));
    expect(severityFillColor(3)).not.toBe(severityFillColor(1));
  });

  it('has a distinct colour for every step', () => {
    const seen = new Set([0, 1, 2, 3, 4].map(severityFillColor));
    expect(seen.size).toBe(5);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
npm test -- severityScale
```

Expected: FAIL — cannot resolve `../severityScale`.

- [ ] **Step 3: Write `src/ui/severityScale.ts`**

```ts
import type { Severity } from '../core/symptoms';

export const SEVERITY_STEPS = 4;

/** Track position 0–1 to a 0–4 step. Pure, so the mapping is testable. */
export function severityFromRatio(ratio: number): Severity {
  const clamped = Math.min(1, Math.max(0, ratio));
  return Math.round(clamped * SEVERITY_STEPS) as Severity;
}

/**
 * One colour per step, warming as the burden grows. From the prototype; the
 * first value is the neutral rail, not a warm tone, because "gar nicht" should
 * not look like a symptom.
 */
const FILL = ['#F1E2BE', '#FFD79B', '#FFC078', '#FF9E80', '#FF7A6E'] as const;

export function severityFillColor(value: Severity): string {
  return FILL[value] ?? FILL[0];
}
```

- [ ] **Step 4: Write `src/ui/SeveritySlider.tsx`**

```tsx
import { useRef, useState } from 'react';
import { PanResponder, StyleSheet, View } from 'react-native';
import { SEVERITY_LABELS, SEVERITY_THRESHOLD } from '../core/symptoms';
import type { Severity } from '../core/symptoms';
import { SEVERITY_STEPS, severityFillColor, severityFromRatio } from './severityScale';
import { colors, radii, space } from './tokens';
import { Text } from './Text';

const STEPS = SEVERITY_STEPS;

export interface SeveritySliderProps {
  readonly label: string;
  readonly value: Severity;
  readonly onChange: (value: Severity) => void;
}

export function SeveritySlider({ label, value, onChange }: SeveritySliderProps) {
  const [width, setWidth] = useState(0);
  const widthRef = useRef(0);
  widthRef.current = width;

  const responder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => {
        if (widthRef.current > 0) onChange(severityFromRatio(e.nativeEvent.locationX / widthRef.current));
      },
      onPanResponderMove: (e) => {
        if (widthRef.current > 0) onChange(severityFromRatio(e.nativeEvent.locationX / widthRef.current));
      },
    }),
  ).current;

  const active = value >= SEVERITY_THRESHOLD;
  const fill = severityFillColor(value);

  return (
    <View style={styles.wrap}>
      <View style={styles.head}>
        <Text variant="body" color="textPrimary">{label}</Text>
        <Text variant="small" color={active ? 'darkest' : 'textMuted'}>
          {SEVERITY_LABELS[value]}
        </Text>
      </View>

      <View
        style={styles.track}
        onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
        accessibilityRole="adjustable"
        accessibilityValue={{ min: 0, max: STEPS, now: value, text: SEVERITY_LABELS[value] }}
        {...responder.panHandlers}
      >
        <View style={styles.rail} />
        <View style={[styles.railFill, { width: `${(value / STEPS) * 100}%`, backgroundColor: fill }]} />
        <View
          style={[
            styles.knob,
            { left: `${(value / STEPS) * 100}%`, borderColor: active ? fill : colors.border },
          ]}
        />
      </View>
    </View>
  );
}

const KNOB = 26;

const styles = StyleSheet.create({
  wrap: { gap: space.sm, paddingVertical: space.sm },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  track: { height: 30, justifyContent: 'center' },
  rail: {
    position: 'absolute', left: 0, right: 0, height: 7,
    borderRadius: radii.pill, backgroundColor: colors.muted,
  },
  railFill: { position: 'absolute', left: 0, height: 7, borderRadius: radii.pill },
  knob: {
    position: 'absolute',
    width: KNOB, height: KNOB, marginLeft: -KNOB / 2,
    borderRadius: radii.pill,
    backgroundColor: colors.white,
    borderWidth: 2,
    boxShadow: '0px 2px 7px rgba(67,49,30,0.18)',
  },
});
```

- [ ] **Step 5: Run and commit**

```bash
npm test -- severityScale && npm run typecheck
git add src/ui/severityScale.ts src/ui/SeveritySlider.tsx src/ui/__tests__/severityScale.test.ts
git commit -m "feat(ui): severity slider with a pure, tested value mapping"
```

Expected: 5 tests pass.

---

## Task 11: Public surface and the gallery

**Files:**
- Create: `src/ui/index.ts`, `app/index.tsx`, `app/gallery.tsx`

- [ ] **Step 1: Write `src/ui/index.ts`**

```ts
export * from './tokens';
export * from './typography';
export * from './Text';
export * from './Screen';
export * from './Card';
export * from './Button';
export * from './Chip';
export * from './OptionCard';
export * from './evidencePalette';
export * from './Badge';
export * from './ringGeometry';
export * from './ProgressRing';
export * from './severityScale';
export * from './SeveritySlider';
export * from './Sun';
```

- [ ] **Step 2: Write `app/index.tsx`**

```tsx
import { Link } from 'expo-router';
import { View } from 'react-native';
import { Screen, Sun, Text, space } from '../src/ui';

export default function Home() {
  return (
    <Screen>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.xl }}>
        <Sun size={72} />
        <Text variant="display" center>MorningGlow</Text>
        <Text variant="body" color="textSecondary" center>
          Etappe 3 — das Designsystem steht.
        </Text>
        <Link href="/gallery">
          <Text variant="bodyLg" color="primary">Komponenten ansehen →</Text>
        </Link>
      </View>
    </Screen>
  );
}
```

- [ ] **Step 3: Write `app/gallery.tsx`**

```tsx
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { EVIDENCE_KEYS } from '../src/core/evidence';
import type { Severity } from '../src/core/symptoms';
import {
  Badge, Button, Card, Chip, OptionCard, ProgressRing, Screen,
  SeveritySlider, Sun, Text, space,
} from '../src/ui';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: space.md, marginBottom: space.xxxl }}>
      <Text variant="caption" color="textMuted">{title.toUpperCase()}</Text>
      {children}
    </View>
  );
}

export default function Gallery() {
  const [severity, setSeverity] = useState<Severity>(2);
  const [chips, setChips] = useState<string[]>(['Schlaf']);
  const [choice, setChoice] = useState('peri');

  const toggle = (s: string) =>
    setChips((c) => (c.includes(s) ? c.filter((x) => x !== s) : [...c, s]));

  return (
    <Screen>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingVertical: space.xxl }}>
        <Text variant="heading" style={{ marginBottom: space.xxl }}>Komponenten</Text>

        <Section title="Marke">
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.xl }}>
            <Sun size={56} />
            <Sun size={36} />
            <Sun size={24} />
          </View>
        </Section>

        <Section title="Typografie">
          <Text variant="display">Guten Morgen</Text>
          <Text variant="heading">Deine Routine</Text>
          <Text variant="title">Ein Glas Wasser</Text>
          <Text variant="bodyLg" color="textSecondary">
            Ein großes Glas Wasser, in Ruhe getrunken.
          </Text>
          <Text variant="small" color="textMuted">ca. 15 Minuten · 5 Schritte</Text>
        </Section>

        <Section title="Buttons">
          <Button label="Los geht's" variant="primary" />
          <Button label="Jetzt starten" variant="strong" />
          <Button label="Später" variant="outline" />
          <Button label="Überspringen" variant="ghost" />
          <Button label="Nicht verfügbar" disabled />
          <View style={{ flexDirection: 'row', gap: space.md }}>
            <Button label="Klein" size="sm" />
            <Button label="Mittel" size="md" />
          </View>
        </Section>

        <Section title="Karten">
          <Card>
            <Text variant="title">Morgenlicht</Text>
            <Text variant="body" color="textSecondary">
              Ans Fenster treten und 2 Minuten Licht tanken.
            </Text>
          </Card>
          <Card elevation="strong">
            <Text variant="body">Stärkerer Schatten</Text>
          </Card>
        </Section>

        <Section title="Evidenzstufen">
          <View style={{ gap: space.sm }}>
            {EVIDENCE_KEYS.map((k) => <Badge key={k} evidence={k} />)}
          </View>
        </Section>

        <Section title="Auswahl">
          <OptionCard
            label="Perimenopause"
            sublabel="Erste Veränderungen, Zyklus noch da"
            selected={choice === 'peri'}
            onPress={() => setChoice('peri')}
          />
          <OptionCard
            label="Postmenopause"
            sublabel="Mehr als ein Jahr keine Blutung mehr"
            selected={choice === 'post'}
            onPress={() => setChoice('post')}
          />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>
            {['Schlaf', 'Hitzewallungen', 'Unruhe', 'Gelenke'].map((s) => (
              <Chip key={s} label={s} selected={chips.includes(s)} onPress={() => toggle(s)} />
            ))}
          </View>
        </Section>

        <Section title="Fortschritt">
          <View style={{ alignItems: 'center' }}>
            <ProgressRing value={3} total={5} size={160} stroke={14}>
              <Text variant="display">3</Text>
              <Text variant="small" color="textMuted">von 5</Text>
            </ProgressRing>
          </View>
        </Section>

        <Section title="Beschwerden 0–4">
          <Card>
            <SeveritySlider label="Schlafprobleme" value={severity} onChange={setSeverity} />
          </Card>
        </Section>
      </ScrollView>
    </Screen>
  );
}
```

- [ ] **Step 4: Typecheck and commit**

```bash
npm run typecheck
git add src/ui/index.ts app/index.tsx app/gallery.tsx
git commit -m "feat(ui): public surface and a component gallery"
```

---

## Task 12: See it on a device

The design system cannot be signed off from a type check. Someone has to look at it.

- [ ] **Step 1: Start the dev server — the human runs this, not an agent**

```bash
cd C:\SuperWork\projects\morningglow
npx expo start
```

Scan the QR code with Expo Go, or press `a` for an Android emulator, `i` for an iOS simulator.

An agent must not spawn this: a backgrounded dev server outlives the turn, and orphaned Metro processes corrupt the bundler cache.

- [ ] **Step 2: Check the three risk decisions on the real device**

- **Shadows.** The cards should carry a warm amber glow, not a grey drop. On Android below 9 there will be no shadow at all — that is expected, not a bug.
- **Fonts.** Compare the display heading against the prototype: if it looks like the system face, the font gate failed and everything fell back silently.
- **Blur.** Not yet exercised — the modal layer arrives in Etappe 5.

- [ ] **Step 3: Check what a type check cannot catch**

- The gradient runs top-to-bottom without banding.
- The severity slider tracks a drag, not only a tap.
- The progress ring starts at twelve o'clock and closes clockwise.
- Text never clips at the largest system font size (Settings → Display → Font size, maximum).

- [ ] **Step 4: Record what was seen**

Note anything that differs from the prototype in `docs/superpowers/plans/` as a follow-up. A screenshot beats a description.

---

## Definition of done

- [ ] `npm test` passes — core suite plus the new token, typography, badge, ring and slider tests
- [ ] `npm run typecheck` clean
- [ ] `npx expo start` boots and the gallery renders every component
- [ ] `grep -rn "#[0-9A-Fa-f]\{6\}" src/ui --include=*.tsx` returns nothing outside `tokens.ts`, `evidencePalette.ts` and `severityScale.ts` — no colour is inlined at a call site
- [ ] `grep -rn "elevation:" src/ui` returns nothing — shadows are `boxShadow` throughout
- [ ] `grep -rn "from 'react-native'" src/core` returns nothing — the design system did not leak into the engine
