import type { PaletteColor } from './api'

// Pick black/white text for legibility on a given swatch colour.
function readableText(hex: string): string {
  const h = hex.replace('#', '')
  if (h.length < 6) return '#ffffff'
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return lum > 0.62 ? '#1d1d1f' : '#ffffff'
}

/**
 * Interactive palette: click a colour to highlight all of its regions in the
 * outline layer (click again, or "Показать все", to clear). Purely presentational
 * — the highlight itself lives in ResultViewer via `activeColor`.
 */
export function PalettePanel({
  palette,
  activeColor,
  onSelect,
}: {
  palette: PaletteColor[]
  activeColor: number | null
  onSelect: (index: number | null) => void
}) {
  return (
    <div className="palette-panel">
      <div className="palette-head">
        <h3>Палитра · {palette.length}</h3>
        {activeColor != null && (
          <button type="button" className="palette-clear" onClick={() => onSelect(null)}>
            Показать все
          </button>
        )}
      </div>
      <ul className="palette-grid">
        {palette.map((c) => {
          const active = c.index === activeColor
          const dimmed = activeColor != null && !active
          return (
            <li key={c.index}>
              <button
                type="button"
                className={`palette-item${active ? ' is-active' : ''}${dimmed ? ' is-dimmed' : ''}`}
                aria-pressed={active}
                onClick={() => onSelect(active ? null : c.index)}
                title={`${c.name_ru} · ${c.hex}`}
              >
                <span
                  className="palette-swatch"
                  style={{ background: c.hex, color: readableText(c.hex) }}
                >
                  {c.index}
                </span>
                <span className="palette-meta">
                  <span className="palette-name">{c.name_ru}</span>
                  <span className="palette-hex">{c.hex}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
