import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import useModal from '../useModal'

describe('useModal', () => {
  it('starts closed by default and exposes modal props', () => {
    const { result } = renderHook(() => useModal())

    expect(result.current.isOpen).toBe(false)
    expect(result.current.modalProps).toEqual({
      open: false,
      onClose: result.current.close,
    })
  })

  it('supports opening, closing, and toggling the modal state', () => {
    const { result } = renderHook(() => useModal())

    act(() => {
      result.current.open()
    })
    expect(result.current.isOpen).toBe(true)
    expect(result.current.modalProps.open).toBe(true)

    act(() => {
      result.current.toggle()
    })
    expect(result.current.isOpen).toBe(false)

    act(() => {
      result.current.toggle()
      result.current.close()
    })
    expect(result.current.isOpen).toBe(false)
  })

  it('can start open when requested', () => {
    const { result } = renderHook(() => useModal(true))

    expect(result.current.isOpen).toBe(true)
    expect(result.current.modalProps.open).toBe(true)
  })
})
