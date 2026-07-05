import { Monitor, Moon, Sun } from 'lucide-react'
import { SegmentedControl } from './SegmentedControl'
import type { Theme } from './useTheme'

const LABELS: Record<Theme, string> = {
  system: 'Система',
  light: 'Светлая',
  dark: 'Тёмная',
}

const ICONS: Record<Theme, typeof Sun> = {
  system: Monitor,
  light: Sun,
  dark: Moon,
}

const ORDER: Theme[] = ['system', 'light', 'dark']

function icon(theme: Theme) {
  const Ico = ICONS[theme]
  return <Ico size={16} strokeWidth={1.9} aria-hidden="true" />
}

/** Compact icon-only variant for the nav bar. */
export function ThemeToggleCompact({
  theme,
  onChange,
}: {
  theme: Theme
  onChange: (t: Theme) => void
}) {
  return (
    <SegmentedControl
      ariaLabel="Тема оформления"
      value={theme}
      onChange={onChange}
      options={ORDER.map((v) => ({ value: v, label: icon(v), ariaLabel: LABELS[v] }))}
    />
  )
}

/** Labeled variant for the Кабинет page. */
export function ThemeToggleFull({
  theme,
  onChange,
}: {
  theme: Theme
  onChange: (t: Theme) => void
}) {
  return (
    <SegmentedControl
      ariaLabel="Тема оформления"
      value={theme}
      onChange={onChange}
      options={ORDER.map((v) => ({
        value: v,
        label: (
          <span className="seg-icon-label">
            {icon(v)} {LABELS[v]}
          </span>
        ),
        ariaLabel: LABELS[v],
      }))}
    />
  )
}
