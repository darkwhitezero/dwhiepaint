import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PalettePanel } from './PalettePanel'
import type { PaletteColor } from './api'

const palette: PaletteColor[] = [
  { index: 1, hex: '#101010', lab: [10, 0, 0], name_ru: 'чёрный', name_en: 'black' },
  { index: 2, hex: '#f0f0f0', lab: [95, 0, 0], name_ru: 'белый', name_en: 'white' },
]

describe('PalettePanel', () => {
  it('renders a swatch per colour with its number', () => {
    render(<PalettePanel palette={palette} activeColor={null} onSelect={() => {}} />)
    expect(screen.getByText('чёрный')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('selects a colour on click and toggles it off on a second click', () => {
    const onSelect = vi.fn()
    const { rerender } = render(
      <PalettePanel palette={palette} activeColor={null} onSelect={onSelect} />,
    )
    fireEvent.click(screen.getByTitle(/чёрный/))
    expect(onSelect).toHaveBeenCalledWith(1)

    rerender(<PalettePanel palette={palette} activeColor={1} onSelect={onSelect} />)
    fireEvent.click(screen.getByTitle(/чёрный/))
    expect(onSelect).toHaveBeenLastCalledWith(null)
  })

  it('marks the active swatch pressed and dims the others', () => {
    render(<PalettePanel palette={palette} activeColor={1} onSelect={() => {}} />)
    expect(screen.getByTitle(/чёрный/)).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTitle(/белый/).className).toContain('is-dimmed')
  })
})
