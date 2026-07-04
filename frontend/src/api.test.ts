import { describe, expect, it } from 'vitest'
import { validateImageFile } from './api'

function makeFile(type: string, size: number): File {
  return new File([new Uint8Array(size)], 'test-file', { type })
}

describe('validateImageFile', () => {
  it('accepts a small image file', () => {
    expect(validateImageFile(makeFile('image/jpeg', 1024))).toBeNull()
  })

  it('rejects a non-image file', () => {
    expect(validateImageFile(makeFile('application/pdf', 1024))).toMatch(/изображения/)
  })

  it('rejects a file over the 15MB cap', () => {
    expect(validateImageFile(makeFile('image/png', 16 * 1024 * 1024))).toMatch(/15/)
  })
})
