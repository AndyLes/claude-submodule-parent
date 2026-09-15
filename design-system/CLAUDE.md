# GlassBase Design System Rules

Design tokens extracted from Figma file `GlassBase` (pmgXsGgWF6m5IkhQebIYat).

## Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | `#0E76E4` | Brand blue — links, CTAs, active states |
| `primary-light` | `#F3F7FC` | Blue-tinted section backgrounds |
| `primary-light-2` | `#E9F3FD` | Deeper blue tint — hover/selected states |
| `neutral-black` | `#0B0B0B` | Primary text |
| `neutral-sub` | `#717191` | Secondary/muted text, labels |
| `neutral-border` | `#BDBDCA` | Input borders, card outlines |
| `neutral-line` | `#DADADA` | Dividers, horizontal rules |
| `neutral-light-grey` | `#FAF8F8` | Page/surface background |
| `neutral-white` | `#FFFFFF` | Cards, overlays |
| `attention` | `#FB822C` | Warnings, highlights, urgent CTAs |

### Rules
- Use `primary` for interactive elements (buttons, links, focus rings).
- Use `neutral-sub` for helper text and secondary labels — never for primary content.
- Use `neutral-line` for `<hr>` and section dividers, `neutral-border` for input/card borders.
- Background layering: white card on `light-grey` surface, or `primary-light` for blue sections.

## Typography

Three font families, each with a specific role:

| Family | Role | Tailwind class |
|--------|------|----------------|
| **Inter** | Desktop headings | `font-heading` |
| **IBM Plex Sans** | Body text, buttons, labels | `font-body` |
| **Montserrat** | Mobile headings | `font-mobile-heading` |

### Type Scale (Desktop)

| Style | Size | Weight | Line Height | Tailwind |
|-------|------|--------|-------------|----------|
| Big Text | 40px | Medium (500) | 120% | `text-big font-body` |
| H1 Title | 48px | Medium (500) | 120% | `text-h1t font-heading` |
| H1 | 32px | Medium / Bold | 150% / 130% | `text-h1 font-heading` |
| H2 | 24px | Regular / Medium | 150% | `text-h2 font-heading` |
| H3 | 20px | Bold / Medium | 120% | `text-h3 font-heading` |
| H4 | 18px | Medium | 120% | `text-h4 font-heading` |
| H5 | 16px | Medium | 120% | `text-h5 font-heading` |
| H6 | 14px | Bold | 140% | `text-h6 font-heading` |
| H7 | 12px | Regular | 120% | `text-h7 font-heading` |
| Body 1 | 24px | Regular | 150% | `text-body-1 font-body` |
| Body 2 | 16px | Regular / Medium / Bold | 150% | `text-body-2 font-body` |
| Body 3 | 14px | Regular / Medium | 140% | `text-body-3 font-body` |
| Body 4 | 12px | Regular / Medium | 120% | `text-body-4 font-body` |

### Rules
- Always pair `font-heading` with heading sizes and `font-body` with body/button sizes.
- Never use `font-heading` for body text or `font-body` for headings.
- At mobile breakpoints, switch headings from Inter to Montserrat (`font-mobile-heading`).
- Default body text is `text-body-2 font-body text-neutral-black`.
- Secondary text is `text-body-3 font-body text-neutral-sub`.

## Spacing System

4px base grid. Use Tailwind spacing scale:

| Token | Value | Common use |
|-------|-------|------------|
| `0.5` | 2px | Tight icon gaps |
| `1` | 4px | Inline spacing |
| `1.5` | 6px | Small padding |
| `2` | 8px | Default gap between small elements |
| `2.5` | 10px | Icon+label gap |
| `3` | 12px | Card internal padding (small) |
| `4` | 16px | Standard padding, section gap |
| `5` | 20px | Medium section padding |
| `6` | 24px | Card padding, row gap |
| `8` | 32px | Section padding |
| `12` | 48px | Large section spacing |
| `16` | 64px | Page-level section gaps |

### Rules
- Prefer spacing tokens over arbitrary values. `p-4` not `p-[15px]`.
- Card inner padding: `p-4` (16px) or `p-6` (24px).
- Section vertical spacing: `py-8` (32px) to `py-16` (64px).
- Gap between grid items: `gap-4` (16px) or `gap-6` (24px).

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `rounded-sm` | 4px | Small chips, tags |
| `rounded` | 6px | Default — inputs, small cards |
| `rounded-md` | 8px | Buttons, dropdowns |
| `rounded-lg` | 14px | Cards, modals |
| `rounded-xl` | 18px | Large cards |
| `rounded-2xl` | 24px | Hero cards, image containers |
| `rounded-3xl` | 28px | Feature panels |
| `rounded-pill` | 60px | Pill buttons, badges |
| `rounded-full` | 80px | Avatars, circular elements |

### Rules
- Buttons use `rounded-sm` (4px).
- Cards use `rounded-md` (8px).
- Inputs and dropdowns use `rounded` (6px) or `rounded-md` (8px).
- Never mix radius sizes within the same component group.

## Shadows

No box-shadows in this design system. Cards and components rely on borders and background contrast for visual separation — not elevation.

### Rules
- Do not add `shadow-*` classes to cards or any components.
- Use `border border-neutral-line` or background contrast (`neutral-light-grey` vs `white`) for depth.

## Component Patterns

### Buttons
Three tiers, each with solid/border/text variants:

| Component | Variants | Primary use |
|-----------|----------|-------------|
| **Button v1** | Solid, Border, Text | Primary actions |
| **Button v2** | Solid, Border, Text | Secondary actions |
| **Button 3** | Border, Text-line | Tertiary/inline actions |

- Solid: `bg-primary text-white rounded-sm`
- Border: `border border-primary text-primary bg-white rounded-sm`
- Text: `text-primary bg-transparent` (no border)
- Button font: `font-body text-btn-3b` (14px SemiBold) or `text-btn-1` (18px SemiBold) for large.

### Dropdowns
Three visual styles: `Border` (outlined), `Classic` (filled), `Line` (underline-only).

### Form Controls
- **Toggle**: Enable/Disable states — uses `primary` blue for active.
- **Checkbox**: On/Off — uses `primary` blue fill when checked.

### Navigation
- **Header**: Desktop default and a secondary variant, plus a dedicated mobile variant.
- Uses `primary` blue as the header background bar.

### Cards
- White background, `rounded-md`, no shadow.
- Image at top, content padded `p-4` or `p-6`.
- Use `border border-neutral-line` for card outlines when needed.
- Property/parameter cards use `neutral-light-grey` background with `rounded` border.

## General Rules for AI-Assisted Development

1. **Always use Tailwind classes** from `tailwind.config.js` — never write raw CSS values that duplicate a token.
2. **Responsive headings**: Switch `font-heading` (Inter) to `font-mobile-heading` (Montserrat) below `md` breakpoint.
3. **Color usage**: Stick to the semantic palette above. Do not invent grays or blues outside the token set.
4. **Interactive states**: Hover = darker shade or border change. Focus = `ring-2 ring-primary ring-offset-2`. No shadows.
5. **Layout max-width**: Desktop content containers cap at `max-w-7xl` (1280px) centered with `mx-auto`.
6. **Images**: Use `rounded-lg` or `rounded-xl` with `object-cover`. Never leave images unstyled.
7. **Consistency**: All similar elements (cards in a grid, items in a list) must use identical spacing, radius, and shadow.
8. **Accessibility**: Maintain WCAG AA contrast. `neutral-sub` (#717191) on white passes for large text only — use `neutral-black` for small body text.
