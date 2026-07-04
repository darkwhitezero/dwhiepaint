import { SegmentedControl } from './SegmentedControl'
import type { Theme } from './useTheme'

const OPTIONS: { value: Theme; label: string }[] = [
  { value: 'system', label: '⟳' },
  { value: 'light', label: '☀' },
  { value: 'dark', label: '☾' },
]
const LABELS: Record<Theme, string> = {
  system: 'Система',
  light: 'Светлая',
  dark: 'Тёмная',
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
      options={OPTIONS}
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
      options={OPTIONS.map((o) => ({ ...o, label: `${o.label} ${LABELS[o.value]}` }))}
    />
  )
}
