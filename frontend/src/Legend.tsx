import type { PaletteColor } from './api'

export function Legend({ palette }: { palette: PaletteColor[] }) {
  return (
    <ul className="legend">
      {palette.map((c) => (
        <li key={c.index}>
          <span className="swatch" style={{ background: c.hex }} />
          <span className="num">{c.index}</span>
          <span className="name">{c.name_ru}</span>
          <span className="hex">{c.hex}</span>
        </li>
      ))}
    </ul>
  )
}
