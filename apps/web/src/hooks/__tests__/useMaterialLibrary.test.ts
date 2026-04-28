import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useMaterialLibrary } from '../useMaterialLibrary'
import * as materialsApi from '@/lib/materialsApi'
import type { LibrarySummaryItem, MaterialPreviewResponse } from '@/lib/materialsApi'

// Mock materialsApi
vi.mock('@/lib/materialsApi', () => ({
  materialsApi: {
    getLibrarySummary: vi.fn(),
    getPreview: vi.fn(),
  },
}))

// Mock @tanstack/react-query
const mockUseQuery = vi.fn()
vi.mock('@tanstack/react-query', () => ({
  useQuery: (args: unknown) => mockUseQuery(args),
}))

describe('useMaterialLibrary', () => {
  const mockLibraries: LibrarySummaryItem[] = [
    {
      id: 1,
      title: 'Novel 1',
      status: 'completed',
      counts: {
        characters: 10,
        worldview: 1,
        golden_fingers: 2,
        storylines: 5,
        relationships: 8,
      },
    },
    {
      id: 2,
      title: 'Novel 2',
      status: 'completed',
      counts: {
        characters: 5,
        worldview: 1,
        golden_fingers: 0,
        storylines: 3,
        relationships: 4,
      },
    },
  ]

  const mockPreview: MaterialPreviewResponse = {
    title: 'Character: Hero',
    markdown: '# Hero\n\nA brave warrior...',
    novel_title: 'Novel 1',
    suggested_file_type: 'character',
    suggested_folder_name: 'Characters',
    suggested_file_name: 'hero',
  }

  beforeEach(() => {
    vi.clearAllMocks()

    // Default mock implementation for useQuery
    mockUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    })
  })

  describe('initial state', () => {
    it('initializes with correct default state', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      expect(result.current.libraries).toEqual([])
      expect(result.current.isLoading).toBe(false)
      expect(result.current.error).toBe(null)
      expect(result.current.isExpanded).toBe(false)
      expect(result.current.expandedNovels).toBeInstanceOf(Set)
      expect(result.current.expandedTypes).toBeInstanceOf(Map)
      expect(result.current.preview).toBe(null)
      expect(result.current.previewEntityInfo).toBe(null)
      expect(result.current.isPreviewLoading).toBe(false)
    })

    it('initializes summary query config', () => {
      renderHook(() => useMaterialLibrary())

      // Hook always initializes the summary query (cached by react-query)
      expect(mockUseQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ['material-library-summary'],
          queryFn: expect.any(Function),
        })
      )
    })
  })

  describe('toggleExpanded', () => {
    it('toggles isExpanded state', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      expect(result.current.isExpanded).toBe(false)

      act(() => {
        result.current.toggleExpanded()
      })

      expect(result.current.isExpanded).toBe(true)

      act(() => {
        result.current.toggleExpanded()
      })

      expect(result.current.isExpanded).toBe(false)
    })

    it('keeps summary query configured after expand', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleExpanded()
      })

      expect(mockUseQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ['material-library-summary'],
          queryFn: expect.any(Function),
        })
      )
    })
  })

  describe('library fetching', () => {
    it('fetches library summary when expanded', async () => {
      mockUseQuery.mockReturnValue({
        data: mockLibraries,
        isLoading: false,
        error: null,
      })

      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleExpanded()
      })

      // The hook should have enabled the query
      expect(mockUseQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ['material-library-summary'],
          queryFn: expect.any(Function),
        })
      )
    })

    it('returns loading state correctly', () => {
      mockUseQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      })

      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleExpanded()
      })

      expect(result.current.isLoading).toBe(true)
    })

    it('handles fetch error', () => {
      const error = new Error('Network error')
      mockUseQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error,
      })

      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleExpanded()
      })

      expect(result.current.error).toBe(error)
    })
  })

  describe('toggleNovel', () => {
    it('adds novel to expanded set when not present', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleNovel(1)
      })

      expect(result.current.expandedNovels.has(1)).toBe(true)
    })

    it('removes novel from expanded set when present', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleNovel(1)
      })
      expect(result.current.expandedNovels.has(1)).toBe(true)

      act(() => {
        result.current.toggleNovel(1)
      })
      expect(result.current.expandedNovels.has(1)).toBe(false)
    })

    it('handles multiple novels independently', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleNovel(1)
        result.current.toggleNovel(2)
      })

      expect(result.current.expandedNovels.has(1)).toBe(true)
      expect(result.current.expandedNovels.has(2)).toBe(true)

      act(() => {
        result.current.toggleNovel(1)
      })

      expect(result.current.expandedNovels.has(1)).toBe(false)
      expect(result.current.expandedNovels.has(2)).toBe(true)
    })
  })

  describe('toggleEntityType', () => {
    it('toggles entity type expansion for a novel', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      const key = '1:characters'
      expect(result.current.expandedTypes.get(key)).toBe(undefined)

      act(() => {
        result.current.toggleEntityType(1, 'characters')
      })

      expect(result.current.expandedTypes.get(key)).toBe(true)

      act(() => {
        result.current.toggleEntityType(1, 'characters')
      })

      expect(result.current.expandedTypes.get(key)).toBe(false)
    })

    it('handles different entity types for same novel', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleEntityType(1, 'characters')
        result.current.toggleEntityType(1, 'worldview')
      })

      expect(result.current.expandedTypes.get('1:characters')).toBe(true)
      expect(result.current.expandedTypes.get('1:worldview')).toBe(true)
    })

    it('handles same entity type for different novels', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.toggleEntityType(1, 'characters')
        result.current.toggleEntityType(2, 'characters')
      })

      expect(result.current.expandedTypes.get('1:characters')).toBe(true)
      expect(result.current.expandedTypes.get('2:characters')).toBe(true)
    })
  })

  describe('loadPreview', () => {
    it('loads preview for an entity', async () => {
      vi.mocked(materialsApi.materialsApi.getPreview).mockResolvedValueOnce(mockPreview)

      const { result } = renderHook(() => useMaterialLibrary())

      await act(async () => {
        await result.current.loadPreview(1, 'characters', 123)
      })

      expect(materialsApi.materialsApi.getPreview).toHaveBeenCalledWith(
        1,
        'characters',
        123
      )
      expect(result.current.preview).toEqual(mockPreview)
      expect(result.current.previewEntityInfo).toEqual({
        novelId: 1,
        entityType: 'characters',
        entityId: 123,
      })
    })

    it('sets isPreviewLoading during load', async () => {
      let resolvePreview: (value: MaterialPreviewResponse) => void
      vi.mocked(materialsApi.materialsApi.getPreview).mockImplementationOnce(
        () => new Promise((resolve) => {
          resolvePreview = resolve
        })
      )

      const { result } = renderHook(() => useMaterialLibrary())

      act(() => {
        result.current.loadPreview(1, 'characters', 123)
      })

      expect(result.current.isPreviewLoading).toBe(true)

      await act(async () => {
        resolvePreview!(mockPreview)
      })

      expect(result.current.isPreviewLoading).toBe(false)
    })

    it('handles preview load error', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      vi.mocked(materialsApi.materialsApi.getPreview).mockRejectedValueOnce(
        new Error('Preview failed')
      )

      const { result } = renderHook(() => useMaterialLibrary())

      await act(async () => {
        await result.current.loadPreview(1, 'characters', 123)
      })

      expect(result.current.isPreviewLoading).toBe(false)
      expect(result.current.preview).toBe(null)
      expect(consoleErrorSpy).toHaveBeenCalled()

      consoleErrorSpy.mockRestore()
    })
  })

  describe('clearPreview', () => {
    it('clears preview state', async () => {
      vi.mocked(materialsApi.materialsApi.getPreview).mockResolvedValueOnce(mockPreview)

      const { result } = renderHook(() => useMaterialLibrary())

      await act(async () => {
        await result.current.loadPreview(1, 'characters', 123)
      })

      expect(result.current.preview).not.toBe(null)

      act(() => {
        result.current.clearPreview()
      })

      expect(result.current.preview).toBe(null)
      expect(result.current.previewEntityInfo).toBe(null)
    })
  })

  describe('query configuration', () => {
    it('uses correct stale time', () => {
      renderHook(() => useMaterialLibrary())

      expect(mockUseQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          staleTime: 5 * 60 * 1000, // 5 minutes
        })
      )
    })

    it('uses correct query key', () => {
      renderHook(() => useMaterialLibrary())

      expect(mockUseQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ['material-library-summary'],
        })
      )
    })
  })

  describe('state updates', () => {
    it('returns libraries from query data', () => {
      mockUseQuery.mockReturnValue({
        data: mockLibraries,
        isLoading: false,
        error: null,
      })

      const { result } = renderHook(() => useMaterialLibrary())

      expect(result.current.libraries).toEqual(mockLibraries)
    })

    it('returns empty array when no data', () => {
      mockUseQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
      })

      const { result } = renderHook(() => useMaterialLibrary())

      expect(result.current.libraries).toEqual([])
    })
  })

  describe('return values', () => {
    it('returns all expected properties', () => {
      const { result } = renderHook(() => useMaterialLibrary())

      expect(result.current).toHaveProperty('libraries')
      expect(result.current).toHaveProperty('isLoading')
      expect(result.current).toHaveProperty('error')
      expect(result.current).toHaveProperty('expandedNovels')
      expect(result.current).toHaveProperty('expandedTypes')
      expect(result.current).toHaveProperty('toggleNovel')
      expect(result.current).toHaveProperty('toggleEntityType')
      expect(result.current).toHaveProperty('isExpanded')
      expect(result.current).toHaveProperty('toggleExpanded')
      expect(result.current).toHaveProperty('preview')
      expect(result.current).toHaveProperty('previewEntityInfo')
      expect(result.current).toHaveProperty('isPreviewLoading')
      expect(result.current).toHaveProperty('loadPreview')
      expect(result.current).toHaveProperty('clearPreview')
    })
  })
})
