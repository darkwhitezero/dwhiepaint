interface Option<T extends string> {
  value: T
  label: string
}

/** Apple-style segmented control (radiogroup) with a sliding active pill. */
export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
}: {
  value: T
  onChange: (v: T) => void
  options: Option<T>[]
  ariaLabel?: string
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value))
  const style = { '--seg-count': options.length, '--seg-index': index } as React.CSSProperties

  return (
    <div className="segmented" role="radiogroup" aria-label={ariaLabel} style={style}>
      <span className="segmented-thumb" aria-hidden="true" />
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          className={`segmented-item${value === o.value ? ' is-active' : ''}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
