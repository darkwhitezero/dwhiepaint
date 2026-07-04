import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SegmentedControl } from './SegmentedControl'

const options = [
  { value: 'a', label: 'A' },
  { value: 'b', label: 'B' },
] as const

describe('SegmentedControl', () => {
  it('marks the active option via aria-checked', () => {
    render(<SegmentedControl value="b" onChange={() => {}} options={[...options]} />)
    expect(screen.getByRole('radio', { name: 'A' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('radio', { name: 'B' })).toHaveAttribute('aria-checked', 'true')
  })

  it('calls onChange with the clicked option value', () => {
    const onChange = vi.fn()
    render(<SegmentedControl value="a" onChange={onChange} options={[...options]} />)
    fireEvent.click(screen.getByRole('radio', { name: 'B' }))
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('exposes the active index as a CSS variable for the sliding thumb', () => {
    const { container } = render(
      <SegmentedControl value="b" onChange={() => {}} options={[...options]} />,
    )
    const el = container.querySelector('.segmented') as HTMLElement
    expect(el.style.getPropertyValue('--seg-index')).toBe('1')
    expect(el.style.getPropertyValue('--seg-count')).toBe('2')
  })
})
