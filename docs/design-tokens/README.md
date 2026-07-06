# Design tokens — Refined Apple Glass

Portable starter kit extracted from the dwhiepaint frontend. Copy this folder
into a new project to reproduce the same look (light/dark glassmorphism, aurora
background, Manrope + Cormorant type) from scratch.

For the full "why" and component patterns, see [../design-system.md](../design-system.md).

## Files

| File | What it is |
|---|---|
| `tokens.css` | Self-contained stylesheet: all CSS custom properties, light + dark themes, the aurora `body` background, global resets, `prefers-reduced-motion`, and a `.glass` primitive. Drop-in ready. |
| `tokens.json` | Machine-readable mirror of the same values (for Tailwind config, Style Dictionary, Figma import, or another agent to read). |

## Use it in 3 steps

**1. Add the fonts** to your `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Cormorant:ital,wght@0,500;0,600;0,700;1,500;1,600&display=swap" />
```

**2. Import the tokens** before your component styles:

```css
@import './design-tokens/tokens.css';
```

**3. Build surfaces on the vars.** Never hard-code a hex — reference a token so
both themes and the glass effect keep working:

```css
.card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow), inset 0 1px 0 var(--glass-hi);
  backdrop-filter: blur(var(--glass-blur)) saturate(160%);
}
/* …or just add class="glass" — the primitive is in tokens.css. */
```

## Theming

- Default is **light**.
- No `data-theme` attribute → the OS preference (`prefers-color-scheme`) decides.
- Force a theme with `<html data-theme="light">` or `<html data-theme="dark">` —
  a manual choice always beats the system preference.
- To avoid a flash of the wrong theme, set the attribute before first paint:

```html
<script>
  var t = localStorage.getItem('theme');
  if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
</script>
```

## Rules that keep it coherent

- **Text on glass** uses `--text` / `--text-secondary`, never a raw grey — glass
  is translucent, so contrast depends on the token, not a fixed value.
- **One accent.** `--accent` drives primary actions, focus rings, active states.
- **Radii ladder:** controls `--radius-sm`/`--radius`, cards `--radius-lg`, glass
  panels `--radius-xl`, buttons/pills `--radius-pill`.
- **Motion:** 150–250ms micro-interactions with `--ease`; entrances with
  `--ease-out`; springy thumbs/swatches with `--ease-spring`. Everything is
  frozen by the global `prefers-reduced-motion` block — exempt only real
  progress indicators, locally, with `!important`.
