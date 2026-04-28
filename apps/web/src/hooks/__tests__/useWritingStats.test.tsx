import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useWritingStats } from '../useWritingStats'
import * as writingStatsApi from '@/lib/writingStatsApi'
import type {
  ProjectDashboardStatsResponse,
  RecordStatsResponse,
} from '@/types/writingStats'

// Mock writingStatsApi
vi.mock('@/lib/writingStatsApi', () => ({
  writingStatsApi: {
    getDashboardStats: vi.fn(),
    recordStats: vi.fn(),
  },
}))

const mockGetDashboardStats = vi.mocked(
  writingStatsApi.writingStatsApi.getDashboardStats
)
const mockRecordStats = vi.mocked(writingStatsApi.writingStatsApi.recordStats)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

function createMockDashboardStats(
  overrides?: Partial<ProjectDashboardStatsResponse>
): ProjectDashboardStatsResponse {
  return {
    project_id: 'project-123',
    project_name: 'Test Project',
    total_word_count: 10000,
    words_today: 500,
    words_this_week: 2000,
    words_this_month: 5000,
    chapter_completion: {
      total_chapters: 10,
      completed_chapters: 3,
      in_progress_chapters: 2,
      not_started_chapters: 5,
      completion_percentage: 30,
      chapter_details: [],
    },
    streak: {
      current_streak: 5,
      longest_streak: 10,
      streak_status: 'active',
      days_until_break: null,
      last_writing_date: '2025-01-15',
      streak_start_date: '2025-01-11',
      streak_recovery_count: 0,
    },
    ai_usage: {
      current: {
        total_sessions: 1,
        active_session_id: null,
        total_messages: 10,
        user_messages: 5,
        assistant_messages: 4,
        tool_messages: 1,
        estimated_tokens: 500,
        first_interaction_at: '2025-01-01T00:00:00Z',
        last_interaction_at: '2025-01-15T12:00:00Z',
      },
      today: { total: 5, user: 3, ai: 2, estimated_tokens: 100 },
      this_week: { total: 20, user: 12, ai: 8, estimated_tokens: 400 },
      this_month: { total: 50, user: 30, ai: 20, estimated_tokens: 1000 },
    },
    generated_at: '2025-01-15T12:00:00Z',
    ...overrides,
  }
}

function createMockRecordStatsResponse(
  overrides?: Partial<RecordStatsResponse>
): RecordStatsResponse {
  return {
    id: 'record-123',
    user_id: 'user-123',
    project_id: 'project-123',
    stats_date: '2025-01-15',
    word_count: 1500,
    words_added: 500,
    words_deleted: 100,
    edit_sessions: 1,
    total_edit_time_seconds: 1800,
    streak_updated: true,
    new_streak: 6,
    ...overrides,
  }
}

describe('useWritingStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('initializes with loading state when fetching', () => {
      mockGetDashboardStats.mockImplementation(() => new Promise(() => {}))

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      expect(result.current.isLoading).toBe(true)
      expect(result.current.stats).toBe(null)
      expect(result.current.error).toBe(null)
    })

    it('initializes with correct default values when enabled is false', () => {
      const { result } = renderHook(
        () =>
          useWritingStats({ projectId: 'project-123', enabled: false }),
        { wrapper: createWrapper() }
      )

      expect(result.current.isLoading).toBe(false)
      expect(result.current.stats).toBe(null)
      expect(result.current.isRecording).toBe(false)
    })
  })

  describe('fetch dashboard stats', () => {
    it('fetches and returns dashboard stats successfully', async () => {
      const mockStats = createMockDashboardStats()
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockGetDashboardStats).toHaveBeenCalledTimes(1)
      expect(mockGetDashboardStats).toHaveBeenCalledWith('project-123')
      expect(result.current.stats).not.toBe(null)
      expect(result.current.stats?.project_id).toBe('project-123')
      expect(result.current.stats?.total_word_count).toBe(10000)
    })

    it('does not fetch when projectId is undefined', async () => {
      const { result } = renderHook(
        () => useWritingStats({ projectId: undefined }),
        { wrapper: createWrapper() }
      )

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(mockGetDashboardStats).not.toHaveBeenCalled()
      expect(result.current.isLoading).toBe(false)
      expect(result.current.stats).toBe(null)
    })

    it('does not fetch when enabled is false', async () => {
      const { result } = renderHook(
        () =>
          useWritingStats({ projectId: 'project-123', enabled: false }),
        { wrapper: createWrapper() }
      )

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(mockGetDashboardStats).not.toHaveBeenCalled()
      expect(result.current.stats).toBe(null)
    })

    it('returns null stats when projectId is undefined', async () => {
      const { result } = renderHook(
        () => useWritingStats({ projectId: undefined }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toBe(null)
    })
  })

  describe('stats data structure', () => {
    it('returns word count data correctly', async () => {
      const mockStats = createMockDashboardStats({
        total_word_count: 25000,
        words_today: 1000,
        words_this_week: 5000,
        words_this_month: 12000,
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.total_word_count).toBe(25000)
      expect(result.current.stats?.words_today).toBe(1000)
      expect(result.current.stats?.words_this_week).toBe(5000)
      expect(result.current.stats?.words_this_month).toBe(12000)
    })

    it('returns chapter completion data correctly', async () => {
      const mockStats = createMockDashboardStats({
        chapter_completion: {
          total_chapters: 20,
          completed_chapters: 8,
          in_progress_chapters: 5,
          not_started_chapters: 7,
          completion_percentage: 40,
          chapter_details: [],
        },
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.chapter_completion.total_chapters).toBe(20)
      expect(result.current.stats?.chapter_completion.completed_chapters).toBe(
        8
      )
      expect(result.current.stats?.chapter_completion.completion_percentage).toBe(
        40
      )
    })

    it('returns streak data correctly', async () => {
      const mockStats = createMockDashboardStats({
        streak: {
          current_streak: 15,
          longest_streak: 30,
          streak_status: 'active',
          days_until_break: null,
          last_writing_date: '2025-01-15',
          streak_start_date: '2025-01-01',
          streak_recovery_count: 2,
        },
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.streak.current_streak).toBe(15)
      expect(result.current.stats?.streak.longest_streak).toBe(30)
      expect(result.current.stats?.streak.streak_status).toBe('active')
    })

    it('returns AI usage data correctly', async () => {
      const mockStats = createMockDashboardStats({
        ai_usage: {
          current: {
            total_sessions: 5,
            active_session_id: 'session-123',
            total_messages: 100,
            user_messages: 50,
            assistant_messages: 40,
            tool_messages: 10,
            estimated_tokens: 5000,
            first_interaction_at: '2025-01-01T00:00:00Z',
            last_interaction_at: '2025-01-15T12:00:00Z',
          },
          today: { total: 10, user: 6, ai: 4, estimated_tokens: 200 },
          this_week: { total: 50, user: 30, ai: 20, estimated_tokens: 1000 },
          this_month: {
            total: 200,
            user: 120,
            ai: 80,
            estimated_tokens: 4000,
          },
        },
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.ai_usage.current.total_sessions).toBe(5)
      expect(result.current.stats?.ai_usage.current.total_messages).toBe(100)
      expect(result.current.stats?.ai_usage.today.total).toBe(10)
    })
  })

  describe('recordStats', () => {
    it('records stats successfully', async () => {
      const mockStats = createMockDashboardStats()
      const mockRecordResponse = createMockRecordStatsResponse()

      mockGetDashboardStats.mockResolvedValue(mockStats)
      mockRecordStats.mockResolvedValue(mockRecordResponse)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      let recordResult: RecordStatsResponse | undefined

      await act(async () => {
        recordResult = await result.current.recordStats({
          word_count: 1500,
          words_added: 500,
        })
      })

      expect(mockRecordStats).toHaveBeenCalledWith('project-123', {
        word_count: 1500,
        words_added: 500,
      })
      expect(recordResult?.id).toBe('record-123')
      expect(recordResult?.streak_updated).toBe(true)
      expect(recordResult?.new_streak).toBe(6)
    })

    it('throws error when projectId is undefined', async () => {
      const { result } = renderHook(
        () => useWritingStats({ projectId: undefined }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      await expect(
        result.current.recordStats({ word_count: 1500 })
      ).rejects.toThrow('Project ID is required to record stats')
    })

    it('sets isRecording to true during mutation', async () => {
      const mockStats = createMockDashboardStats()
      const mockRecordResponse = createMockRecordStatsResponse()

      mockGetDashboardStats.mockResolvedValue(mockStats)
      mockRecordStats.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockRecordResponse), 100))
      )

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isRecording).toBe(false)

      act(() => {
        result.current.recordStats({ word_count: 1500 })
      })

      // During mutation, isRecording should be true
      await waitFor(() => {
        expect(result.current.isRecording).toBe(true)
      })

      // After mutation completes
      await waitFor(() => {
        expect(result.current.isRecording).toBe(false)
      })
    })

    it('invalidates stats query after successful record', async () => {
      const mockStats = createMockDashboardStats()
      const mockRecordResponse = createMockRecordStatsResponse()

      mockGetDashboardStats.mockResolvedValue(mockStats)
      mockRecordStats.mockResolvedValue(mockRecordResponse)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Clear the mock to count new calls
      mockGetDashboardStats.mockClear()

      await act(async () => {
        await result.current.recordStats({ word_count: 1500 })
      })

      // The query should be invalidated (refetched)
      await waitFor(() => {
        expect(mockGetDashboardStats).toHaveBeenCalled()
      })
    })
  })

  describe('refetch', () => {
    it('refetches stats data', async () => {
      const mockStats1 = createMockDashboardStats({ total_word_count: 10000 })
      const mockStats2 = createMockDashboardStats({ total_word_count: 12000 })

      mockGetDashboardStats
        .mockResolvedValueOnce(mockStats1)
        .mockResolvedValueOnce(mockStats2)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.total_word_count).toBe(10000)
      expect(mockGetDashboardStats).toHaveBeenCalledTimes(1)

      await act(async () => {
        await result.current.refetch()
      })

      await waitFor(() => {
        expect(mockGetDashboardStats).toHaveBeenCalledTimes(2)
      })
    })
  })

  describe('loading state', () => {
    it('sets isLoading to true while fetching', () => {
      mockGetDashboardStats.mockImplementation(() => new Promise(() => {}))

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      expect(result.current.isLoading).toBe(true)
    })

    it('sets isLoading to false after successful fetch', async () => {
      const mockStats = createMockDashboardStats()
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
    })

    it('sets isLoading to false after error', async () => {
      mockGetDashboardStats.mockRejectedValue(new Error('Network error'))

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      // Hook has retry: 2, so we need to wait for retries to complete
      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false)
        },
        { timeout: 5000 }
      )
    })
  })

  describe('error handling', () => {
    it('sets error when fetch fails', async () => {
      mockGetDashboardStats.mockRejectedValue(new Error('Network error'))

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      // Hook has retry: 2, so we need to wait for retries to complete
      await waitFor(
        () => {
          expect(result.current.error).not.toBe(null)
        },
        { timeout: 5000 }
      )

      expect(result.current.error?.message).toBe('Network error')
    })

    it('clears error on successful refetch', async () => {
      mockGetDashboardStats.mockRejectedValue(new Error('Network error'))

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      // Wait for error state
      await waitFor(
        () => {
          expect(result.current.error).not.toBe(null)
        },
        { timeout: 5000 }
      )

      const mockStats = createMockDashboardStats()
      mockGetDashboardStats.mockResolvedValue(mockStats)

      await act(async () => {
        await result.current.refetch()
      })

      await waitFor(() => {
        expect(result.current.error).toBe(null)
      })
    })

    it('handles non-Error rejection', async () => {
      mockGetDashboardStats.mockRejectedValue('String error')

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      // Hook has retry: 2, so we need to wait for retries to complete
      await waitFor(
        () => {
          expect(result.current.error).not.toBe(null)
        },
        { timeout: 5000 }
      )
    })
  })

  describe('options', () => {
    it('respects staleTime option', async () => {
      const mockStats = createMockDashboardStats()
      mockGetDashboardStats.mockResolvedValue(mockStats)

      // Use a long staleTime
      renderHook(
        () =>
          useWritingStats({
            projectId: 'project-123',
            staleTime: 5 * 60 * 1000, // 5 minutes
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(mockGetDashboardStats).toHaveBeenCalledTimes(1)
      })
    })

    it('fetches when enabled changes from false to true', async () => {
      const mockStats = createMockDashboardStats()
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { rerender } = renderHook(
        ({ enabled }: { enabled: boolean }) =>
          useWritingStats({ projectId: 'project-123', enabled }),
        {
          wrapper: createWrapper(),
          initialProps: { enabled: false },
        }
      )

      // No fetch initially
      expect(mockGetDashboardStats).not.toHaveBeenCalled()

      // Enable fetching
      rerender({ enabled: true })

      await waitFor(() => {
        expect(mockGetDashboardStats).toHaveBeenCalledWith('project-123')
      })
    })
  })

  describe('edge cases', () => {
    it('handles zero word count', async () => {
      const mockStats = createMockDashboardStats({
        total_word_count: 0,
        words_today: 0,
        words_this_week: 0,
        words_this_month: 0,
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.total_word_count).toBe(0)
      expect(result.current.stats?.words_today).toBe(0)
    })

    it('handles broken streak status', async () => {
      const mockStats = createMockDashboardStats({
        streak: {
          current_streak: 0,
          longest_streak: 5,
          streak_status: 'broken',
          days_until_break: null,
          last_writing_date: '2025-01-10',
          streak_start_date: null,
          streak_recovery_count: 0,
        },
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.streak.current_streak).toBe(0)
      expect(result.current.stats?.streak.streak_status).toBe('broken')
    })

    it('handles empty chapter completion', async () => {
      const mockStats = createMockDashboardStats({
        chapter_completion: {
          total_chapters: 0,
          completed_chapters: 0,
          in_progress_chapters: 0,
          not_started_chapters: 0,
          completion_percentage: 0,
          chapter_details: [],
        },
      })
      mockGetDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.stats).not.toBe(null)
      })

      expect(result.current.stats?.chapter_completion.total_chapters).toBe(0)
      expect(result.current.stats?.chapter_completion.completion_percentage).toBe(
        0
      )
    })

    it('handles recordStats with all optional fields', async () => {
      const mockStats = createMockDashboardStats()
      const mockRecordResponse = createMockRecordStatsResponse()

      mockGetDashboardStats.mockResolvedValue(mockStats)
      mockRecordStats.mockResolvedValue(mockRecordResponse)

      const { result } = renderHook(
        () => useWritingStats({ projectId: 'project-123' }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      await act(async () => {
        await result.current.recordStats({
          word_count: 2000,
          words_added: 800,
          words_deleted: 200,
          edit_time_seconds: 3600,
          stats_date: '2025-01-15',
        })
      })

      expect(mockRecordStats).toHaveBeenCalledWith('project-123', {
        word_count: 2000,
        words_added: 800,
        words_deleted: 200,
        edit_time_seconds: 3600,
        stats_date: '2025-01-15',
      })
    })
  })
})
