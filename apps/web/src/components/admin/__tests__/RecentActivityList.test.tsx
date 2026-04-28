import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RecentActivityList } from '../RecentActivityList'

let queryState: Record<string, unknown> = {}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      (
        {
          'admin:dashboard.loadError': 'Failed to load activity',
          'admin:dashboard.noActivity': 'No recent activity',
          'admin:auditLogs.actionCreate': 'Created',
          'admin:auditLogs.resourceUser': 'User',
        } as Record<string, string>
      )[key] ?? (options?.defaultValue as string) ?? key,
    i18n: {
      language: 'en',
    },
  }),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => queryState,
}))

vi.mock('@/lib/adminApi', () => ({
  adminApi: {
    getAuditLogs: vi.fn(),
  },
}))

vi.mock('../../ui/Skeleton', () => ({
  Skeleton: () => <div data-testid="skeleton" />,
}))

vi.mock('../../ui/IconWrapper', () => ({
  IconWrapper: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

describe('RecentActivityList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryState = {
      data: null,
      isLoading: false,
      isFetching: false,
      error: null,
    }
  })

  it('renders loading, error, and empty states', () => {
    queryState = { data: null, isLoading: true, isFetching: false, error: null }
    const { rerender } = render(<RecentActivityList />)
    expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)

    queryState = { data: null, isLoading: false, isFetching: false, error: new Error('boom') }
    rerender(<RecentActivityList />)
    expect(screen.getByText('Failed to load activity')).toBeInTheDocument()

    queryState = { data: { items: [] }, isLoading: false, isFetching: false, error: null }
    rerender(<RecentActivityList />)
    expect(screen.getByText('No recent activity')).toBeInTheDocument()
  })

  it('renders recent audit activity entries', () => {
    queryState = {
      data: {
        items: [
          {
            id: 'event-1',
            admin_name: 'Admin User',
            action: 'create_user',
            resource_type: 'user',
            created_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
    }

    render(<RecentActivityList />)

    expect(screen.getByText('Admin User')).toBeInTheDocument()
    expect(screen.getByText('Created')).toBeInTheDocument()
    expect(screen.getByText('User')).toBeInTheDocument()
  })
})
