import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastContainer } from '../Toast'
import { toast } from '../../lib/toast'

describe('ToastContainer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders toast messages and auto-dismisses them', async () => {
    render(<ToastContainer />)

    act(() => {
      toast.success('Saved successfully')
    })

    expect(screen.getByText('Saved successfully')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    expect(screen.queryByText('Saved successfully')).not.toBeInTheDocument()
  })

  it('deduplicates identical toasts and keeps only the latest three', () => {
    render(<ToastContainer />)

    act(() => {
      toast.info('Duplicate')
      toast.info('Duplicate')
      toast.error('Second')
      toast.success('Third')
      toast.info('Fourth')
    })

    expect(screen.queryByText('Duplicate')).not.toBeInTheDocument()
    expect(screen.getByText('Second')).toBeInTheDocument()
    expect(screen.getByText('Third')).toBeInTheDocument()
    expect(screen.getByText('Fourth')).toBeInTheDocument()
  })
})
