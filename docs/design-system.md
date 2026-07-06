# dwhiepaint — Design System

**Refined Apple Glass.** A calm, premium light/dark interface built on
glassmorphism over a soft aurora background, with editorial serif display type.
Not glitchcore, not neon — the reference is apple.com marketing pages.

This document is the canonical description of the design language. The live
source of truth is [`frontend/src/index.css`](../frontend/src/index.css) (tokens
+ background) and [`frontend/src/App.css`](../frontend/src/App.css) (components).
A portable, copy-into-a-new-project starter lives in
[`design-tokens/`](design-tokens/).

---

## 1. Principles

1. **Tokens, never hard-codes.** Every colour, radius, shadow and easing is a CSS
   custom property. Glass is translucent, so contrast depends on the token — a
   raw hex would break one of the two themes.
2. **Both themes are first-class.** Dark is a deep blue-graphite (`#080a0f`), not
   pure black. Light is airy and cool, with the aurora dialed *down* so it never
   "hits the eyes."
3. **One accent.** `--accent` drives primary actions, focus rings and active
   states. No competing hues.
4. **Depth comes from glass + shadow, not borders.** Surfaces are `--glass-bg`
   with a hairline `--glass-border`, an inner top highlight (`--glass-hi`), and a
   soft ambient shadow. The blurred backdrop refracts the aurora underneath.
5. **Motion is meaningful and quiet.** 150–250ms micro-interactions, springy
   thumbs, orchestrated entrances — all gated behind `prefers-reduced-motion`.
6. **Accessible by construction.** ≥44px touch targets, visible focus rings,
   `tabular-nums` for numbers, contrast checked on glass in both themes.

---

## 2. Typography

| Role | Font | Usage |
|---|---|---|
| Interface / body | **Manrope** (400–800) | Everything: controls, labels, body copy |
| Display / wordmark | **Cormorant** (500–700, incl. italic) | `h1`, hero titles, the `dwhiepaint` wordmark — the "keynote" voice |

Both have full Cyrillic. Load via Google Fonts (`display=swap`). `h1` uses the
serif at weight 600 with neutral tracking; `h2`/`h3` stay sans with `-0.02em`.
Body is 16px / line-height 1.5.

```
font-family: var(--font);          /* Manrope stack */
font-family: var(--font-display);  /* Cormorant stack */
```

---

## 3. Colour tokens

Semantic, not literal. Full values in [`design-tokens/tokens.json`](design-tokens/tokens.json).

| Token | Light | Dark | Role |
|---|---|---|---|
| `--bg` / `--bg-2` | `#f4f6fb` / `#eef1f8` | `#080a0f` / `#0d1017` | Page base gradient |
| `--surface` / `--surface-2` | `#ffffff` / `#f2f4f9` | `#161a22` / `#1e232d` | Opaque panels, inputs, tracks |
| `--text` / `-secondary` / `-tertiary` | `#14161c` / `#5b6170` / `#878d9c` | `#f2f4f8` / `#a2a9b8` / `#767d8c` | Text hierarchy |
| `--border` / `--border-soft` | `#d7dbe6` / `#e6e9f2` | `#2b313d` / `#222834` | Hairlines |
| `--accent` / `-hover` / `-press` | `#0a74f0` / `#1e82ff` / `#0064d6` | `#3d9bff` / `#5aabff` / `#2b86ff` | Primary action, focus |
| `--on-accent` | `#ffffff` | `#ffffff` | Text on accent |
| `--danger` | `#d70015` | `#ff453a` | Errors, destructive |
| `--ok` | `#1d8a3f` | `#30d158` | Success, healthy status |

**Theme selection:** default is light. `@media (prefers-color-scheme: dark)
:root:not([data-theme='light'])` applies dark from the OS; `:root[data-theme=…]`
forces a manual choice that beats the system. `index.html` sets the attribute
before first paint (from `localStorage`) to avoid a theme flash.

---

## 4. Glass

The signature surface. Theme-adaptive because it's `color-mix`ed from the current
theme's own `--surface`, so the same rule works in light and dark.

```css
--glass-bg:     color-mix(in srgb, var(--surface) 66%, transparent);
--glass-2:      color-mix(in srgb, var(--surface-2) 62%, transparent);
--glass-border: color-mix(in srgb, var(--text) 12%, transparent);
--glass-hi:     color-mix(in srgb, #ffffff 60%, transparent);  /* 22% in dark */
--glass-blur:   22px;
```

The primitive (class `.panel` in the app, `.glass` in the starter kit):

```css
background: var(--glass-bg);
border: 1px solid var(--glass-border);
border-radius: var(--radius-xl);
box-shadow: var(--shadow), inset 0 1px 0 var(--glass-hi);  /* ambient + top specular */
backdrop-filter: blur(var(--glass-blur)) saturate(160%);
```

Applied to: nav, controls, palette panel, result viewer, cards, auth card,
account/stat cards, toasts, dropzone, segmented control, inputs. Lighter blur
(8–16px) on smaller controls, heavier (22px) on big panels.

> **Gotcha:** always pair `backdrop-filter` with `-webkit-backdrop-filter`.

---

## 5. Aurora background

Ambient colour that gives glass "something to refract." Baked directly into the
`body` `background-image` as a **fixed layer stack** — grain tile on top, five
soft radial aurora blobs, base gradient at the bottom.

> **Hard-won lesson:** a negative-`z-index` `body::before` pseudo-element did
> *not* render reliably behind the app. Baking the layers into `body`'s own
> `background-image` (with `background-attachment: fixed`) is robust. Don't
> "refactor" it back into a pseudo-element.

Aurora opacity is the main lever between "premium" and "eye-searing":
- **Light:** α ≈ 0.13–0.16 — a soft tint. (Originally 0.58–0.72; that was too
  loud and got dialed back — see [`design-aesthetic`] memory.)
- **Dark (OS):** α ≈ 0.42–0.62 — richer, since it reads against near-black.
- **Dark (manual toggle):** calmer α ≈ 0.22–0.30.

Grain is an inline `feTurbulence` SVG at `--grain-opacity` (0.035 light / 0.05–0.06 dark).

---

## 6. Shape, shadow, motion

**Radii ladder:** `--radius-sm` 8px (controls, inputs) · `--radius` 12px (images,
toasts) · `--radius-lg` 18px (cards) · `--radius-xl` 26px (glass panels) ·
`--radius-pill` 980px (buttons, tabs, track fills).

**Shadows:** `--shadow-sm` (resting hairline lift) · `--shadow` (glass ambient) ·
`--shadow-lg` (hover/toast/elevated). Dark shadows are deeper (α up to 0.8).

**Easing:** `--ease` `cubic-bezier(.4,0,.2,1)` (default) · `--ease-out`
`cubic-bezier(.16,1,.3,1)` (entrances) · `--ease-spring` `cubic-bezier(.34,1.56,.64,1)`
(thumbs, swatches, playful pops).

**Timing:** micro-interactions 150–250ms; layer/opacity transitions 300–400ms;
hover lift `translateY(-1px…-6px)`; press `scale(0.97)`.

**Named keyframes:** `reveal` (orchestrated section entrance), `card-in` (staggered
by `--i * 40ms`), `panel-in`, `toast-in`, `float` (dropzone icon), `shimmer`
(skeletons), `spin`, `k-pulse`, `border-chase` (running CTA border),
`progress-indeterminate`.

Everything is frozen by the global `prefers-reduced-motion` block in `index.css`.
Genuine progress indicators (spinner, loading bar) are re-exempted locally with a
higher-specificity `!important` rule — motion there conveys real state.

---

## 7. Component patterns

- **Buttons** — pill-shaped, min-height 44px. `.btn-primary` is a vertical accent
  gradient with a coloured glow, a hover lift, and a diagonal sheen sweep via
  `::after`. `.btn-ghost` is glass. `.btn-danger` is an outlined danger tint.
- **`.btn-cta`** — the running white border: an `@property --border-angle` +
  `conic-gradient` `::before` chased by `@keyframes border-chase`, revealed on
  hover; `::after` re-paints the fill so only the ring shows. Used on auth submit.
- **Segmented control** — glass track, an absolutely-positioned `--surface` thumb
  translated by `--seg-index` with spring easing. Active label brightens to
  `--text`. Labels accept a `ReactNode` (icon + text).
- **Auth tabs** — two *separate* pills (`.auth-tabs`/`.auth-tab`), not a joined
  segmented control; active tab gets the accent gradient.
- **Cards** — glass, staggered `card-in` entrance, hover lifts `-6px` to
  `--shadow-lg`, and the thumbnail scales `1.05` inside `overflow:hidden`.
- **Palette items** — swatch pops `scale(1.08)` on hover (spring); active item
  gets an accent ring + glow; unrelated items dim to 0.45 opacity.
- **Nav** — sticky, heavy glass (`blur(24px) saturate(180%)`), serif wordmark.
- **Inputs** — glass fill; focus swaps border to `--accent` + a 3px accent halo.
- **Skeletons** — `--skeleton` gradient + `shimmer`. **Toasts** — glass, bottom-
  centre, `aria-live`, auto-dismiss.
- **Icons** — [lucide-react](https://lucide.dev), one line-icon set. No emoji.

---

## 8. Accessibility checklist

- Contrast ≥ 4.5:1 for body text **on the glass surface** in *both* themes (the
  translucency means you must check the composited result, not the token alone).
- `:focus-visible` → 2px `--accent` outline, 2px offset. Never removed.
- Touch targets ≥ 44px; `.btn` enforces `min-height: 44px`.
- Numbers use `font-variant-numeric: tabular-nums` (palette, stats, progress %).
- Status/feedback never relies on colour alone (icon + text accompany it).
- `prefers-reduced-motion` disables all decorative motion globally.
- Test at **375px** — the nav is the usual overflow culprit; the mobile theme
  toggle is intentionally hidden there (full control lives on the Account page).

---

## 9. How to reuse

- **Same project (dwhiepaint):** edit `frontend/src/index.css` /
  `frontend/src/App.css`. This doc explains intent; those files are truth.
- **New project (copy the look):** grab [`design-tokens/`](design-tokens/) —
  `tokens.css` is drop-in, `tokens.json` feeds Tailwind/Style-Dictionary/Figma.
  Follow its README (fonts → import → build on the vars).
- **Ask Claude to reproduce it elsewhere:** the global skill
  `apple-glass-design-system` packages this language so it can be applied in a
  fresh session/project without this repo. Say e.g. *"apply the apple-glass
  design system to this app."*
