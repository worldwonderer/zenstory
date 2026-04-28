import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useExport } from '../useExport'

// Mock the api module
const mockExportDrafts = vi.fn()

vi.mock('@/lib/api', () => ({
  exportApi: {
    exportDrafts: (...args: unknown[]) => mockExportDrafts(...args),
  },
}))

describe('useExport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockExportDrafts.mockReset()
  })

  describe('initial state', () => {
    it('initializes with idle state', () => {
      const { result } = renderHook(() => useExport('project-123'))

      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBe(null)
    })

    it('handles null projectId', () => {
      const { result } = renderHook(() => useExport(null))

      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBe(null)
    })
  })

  describe('exportDrafts', () => {
    it('returns early when projectId is null', async () => {
      const { result } = renderHook(() => useExport(null))

      await act(async () => {
        await result.current.exportDrafts()
      })

      expect(mockExportDrafts).not.toHaveBeenCalled()
    })

    it('calls export API with correct projectId', async () => {
      mockExportDrafts.mockResolvedValueOnce(undefined)

      const { result } = renderHook(() => useExport('project-123'))

      await act(async () => {
        await result.current.exportDrafts()
      })

      expect(mockExportDrafts).toHaveBeenCalledWith('project-123')
    })

    it('sets loading to true during export', async () => {
      let resolveExport: () => void
      mockExportDrafts.mockImplementationOnce(
        () => new Promise<void>((resolve) => {
          resolveExport = resolve
        })
      )

      const { result } = renderHook(() => useExport('project-123'))

      // Start the export but don't await yet
      let exportPromise: Promise<void>
      act(() => {
        exportPromise = result.current.exportDrafts()
      })

      // Check loading immediately after starting
      expect(result.current.loading).toBe(true)

      // Now resolve and wait
      await act(async () => {
        resolveExport!()
        await exportPromise!
      })

      expect(result.current.loading).toBe(false)
    })

    it('handles successful export', async () => {
      mockExportDrafts.mockResolvedValueOnce(undefined)

      const { result } = renderHook(() => useExport('project-123'))

      await act(async () => {
        await result.current.exportDrafts()
      })

      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBe(null)
    })

    it('handles export error', async () => {
      mockExportDrafts.mockRejectedValueOnce(new Error('Export failed'))

      const { result } = renderHook(() => useExport('project-123'))

      await act(async () => {
        try {
          await result.current.exportDrafts()
        } catch {
          // Expected to throw
        }
      })

      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBe('Export failed')
    })

    it('handles non-Error rejection', async () => {
      mockExportDrafts.mockRejectedValueOnce('Unknown error')

      const { result } = renderHook(() => useExport('project-123'))

      await act(async () => {
        try {
          await result.current.exportDrafts()
        } catch {
          // Expected to throw
        }
      })

      expect(result.current.error).toBe('Export failed')
    })

    it('re-throws error for callers to handle', async () => {
      mockExportDrafts.mockRejectedValueOnce(new Error('Export failed'))

      const { result } = renderHook(() => useExport('project-123'))

      let thrownError: Error | null = null
      await act(async () => {
        try {
          await result.current.exportDrafts()
        } catch (e) {
          thrownError = e as Error
        }
      })

      expect(thrownError?.message).toBe('Export failed')
    })

    it('clears previous error on new export attempt', async () => {
      // First export fails
      mockExportDrafts.mockRejectedValueOnce(new Error('First error'))

      const { result } = renderHook(() => useExport('project-123'))

      await act(async () => {
        try {
          await result.current.exportDrafts()
        } catch {
          // Expected
        }
      })

      expect(result.current.error).toBe('First error')

      // Second export succeeds
      mockExportDrafts.mockResolvedValueOnce(undefined)

      await act(async () => {
        await result.current.exportDrafts()
      })

      expect(result.current.error).toBe(null)
    })

    it('resets loading state after error', async () => {
      mockExportDrafts.mockRejectedValueOnce(new Error('Export failed'))

      const { result } = renderHook(() => useExport('project-123'))

      await act(async () => {
        try {
          await result.current.exportDrafts()
        } catch {
          // Expected
        }
      })

      expect(result.current.loading).toBe(false)
    })
  })

  describe('state stability', () => {
    it('returns stable exportDrafts function', () => {
      const { result, rerender } = renderHook(() => useExport('project-123'))

      const firstExportDrafts = result.current.exportDrafts

      rerender()

      expect(result.current.exportDrafts).toBe(firstExportDrafts)
    })

    it('has exportDrafts function that depends on projectId', () => {
      const { result, rerender } = renderHook(
        ({ projectId }) => useExport(projectId),
        { initialProps: { projectId: 'project-123' as string | null } }
      )

      expect(typeof result.current.exportDrafts).toBe('function')

      rerender({ projectId: 'project-456' })

      // Function should still be a function
      expect(typeof result.current.exportDrafts).toBe('function')
    })
  })
})
