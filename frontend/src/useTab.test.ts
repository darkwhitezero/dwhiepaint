import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTab } from './useTab'

describe('useTab', () => {
  beforeEach(() => {
    window.location.hash = ''
  })

  it('defaults to create when there is no hash', () => {
    const { result } = renderHook(() => useTab())
    expect(result.current[0]).toBe('create')
  })

  it('reads an existing valid hash on mount', () => {
    window.location.hash = 'history'
    const { result } = renderHook(() => useTab())
    expect(result.current[0]).toBe('history')
  })

  it('falls back to create for an unrecognized hash', () => {
    window.location.hash = 'nonsense'
    const { result } = renderHook(() => useTab())
    expect(result.current[0]).toBe('create')
  })

  it('setTab updates location.hash, which reacts back into state', async () => {
    const { result } = renderHook(() => useTab())

    act(() => {
      result.current[1]('account')
    })

    await waitFor(() => expect(result.current[0]).toBe('account'))
    expect(window.location.hash).toBe('#account')
  })
})
