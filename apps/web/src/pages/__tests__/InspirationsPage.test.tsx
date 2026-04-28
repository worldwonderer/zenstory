import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InspirationsPage from '../InspirationsPage'

let mockSubmissions = {
  items: [] as Array<Record<string, unknown>>,
  total: 0,
  isLoading: false,
  isFetching: false,
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      (
        {
          title: 'Inspirations',
          subtitle: 'Discover and manage inspirations',
          'mySubmissions.title': 'My submissions',
          'mySubmissions.count': `${options?.count ?? 0} submissions`,
          'mySubmissions.loading': 'Loading submissions',
          'mySubmissions.empty': 'No submissions yet',
          'mySubmissions.submittedAt': `Submitted ${options?.date ?? ''}`,
          'mySubmissions.rejectionReason': `Reason: ${options?.reason ?? ''}`,
          'mySubmissions.status.pending': 'Pending',
          'mySubmissions.status.approved': 'Approved',
          'mySubmissions.status.rejected': 'Rejected',
          copyCount: `${options?.count ?? 0} copies`,
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

vi.mock('../../hooks/useInspirations', () => ({
  useMyInspirationSubmissions: () => mockSubmissions,
}))

vi.mock('../../lib/i18n-helpers', () => ({
  getLocaleCode: () => 'en-US',
}))

vi.mock('../../components/dashboard/DashboardPageHeader', () => ({
  DashboardPageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}))

vi.mock('../../components/inspirations', () => ({
  InspirationGrid: ({ pageSize }: { pageSize: number }) => <div>Grid size {pageSize}</div>,
}))

describe('InspirationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSubmissions = {
      items: [],
      total: 0,
      isLoading: false,
      isFetching: false,
    }
  })

  it('renders loading and empty submission states', () => {
    mockSubmissions = {
      items: [],
      total: 0,
      isLoading: true,
      isFetching: false,
    }

    const { rerender } = render(<InspirationsPage />)
    expect(screen.getByText('Loading submissions')).toBeInTheDocument()

    mockSubmissions = {
      items: [],
      total: 0,
      isLoading: false,
      isFetching: false,
    }
    rerender(<InspirationsPage />)

    expect(screen.getByText('No submissions yet')).toBeInTheDocument()
  })

  it('renders submission cards and the inspiration grid', () => {
    mockSubmissions = {
      items: [
        {
          id: 'submission-1',
          name: 'Battle Scene',
          created_at: '2026-04-07T00:00:00Z',
          status: 'rejected',
          rejection_reason: 'Needs more context',
          copy_count: 4,
        },
      ],
      total: 1,
      isLoading: false,
      isFetching: false,
    }

    render(<InspirationsPage />)

    expect(screen.getByText('Battle Scene')).toBeInTheDocument()
    expect(screen.getByText('Reason: Needs more context')).toBeInTheDocument()
    expect(screen.getByText('4 copies')).toBeInTheDocument()
    expect(screen.getByText('Grid size 12')).toBeInTheDocument()
  })
})
