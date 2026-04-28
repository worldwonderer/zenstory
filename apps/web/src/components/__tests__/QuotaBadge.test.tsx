import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as subscriptionApi from '../../lib/subscriptionApi'
import { QuotaBadge } from '../subscription/QuotaBadge'

vi.mock('../../lib/subscriptionApi', () => ({
  subscriptionApi: {
    getQuota: vi.fn(),
  },
  subscriptionQueryKeys: {
    status: () => ['subscription-status', 'test-user'],
    quota: () => ['subscription-quota', 'test-user'],
    quotaLite: () => ['quota', 'test-user'],
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue: string) => {
      if (key === 'subscription.unlimited') {
        return '无限'
      }
      return defaultValue
    },
  }),
}))

const mockGetQuota = vi.mocked(subscriptionApi.subscriptionApi.getQuota)

function renderWithQuery(ui: JSX.Element) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('QuotaBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders normal quota usage with success variant', async () => {
    mockGetQuota.mockResolvedValue({
      ai_conversations: {
        used: 5,
        limit: 20,
        reset_at: '2026-03-08T00:00:00Z',
      },
      projects: {
        used: 1,
        limit: 3,
      },
    })

    renderWithQuery(<QuotaBadge />)

    const usage = await screen.findByText('5/20')
    expect(usage).toBeInTheDocument()
    expect(usage.parentElement?.className).toContain('bg-[hsl(var(--success)/0.15)]')
  })

  it('renders warning variant when usage reaches 80%', async () => {
    mockGetQuota.mockResolvedValue({
      ai_conversations: {
        used: 16,
        limit: 20,
        reset_at: '2026-03-08T00:00:00Z',
      },
      projects: {
        used: 1,
        limit: 3,
      },
    })

    renderWithQuery(<QuotaBadge />)

    const usage = await screen.findByText('16/20')
    expect(usage.parentElement?.className).toContain('bg-[hsl(var(--warning)/0.15)]')
  })

  it('renders info variant when usage reaches 50%', async () => {
    mockGetQuota.mockResolvedValue({
      ai_conversations: {
        used: 10,
        limit: 20,
        reset_at: '2026-03-08T00:00:00Z',
      },
      projects: {
        used: 1,
        limit: 3,
      },
    })

    renderWithQuery(<QuotaBadge />)

    const usage = await screen.findByText('10/20')
    expect(usage.parentElement?.className).toContain('bg-[hsl(var(--info)/0.15)]')
  })

  it('renders error variant when usage is exhausted', async () => {
    mockGetQuota.mockResolvedValue({
      ai_conversations: {
        used: 20,
        limit: 20,
        reset_at: '2026-03-08T00:00:00Z',
      },
      projects: {
        used: 3,
        limit: 3,
      },
    })

    renderWithQuery(<QuotaBadge />)

    const usage = await screen.findByText('20/20')
    expect(usage.parentElement?.className).toContain('bg-[hsl(var(--error)/0.15)]')
  })

  it('renders unlimited label when quota limit is -1', async () => {
    mockGetQuota.mockResolvedValue({
      ai_conversations: {
        used: 999,
        limit: -1,
        reset_at: '2026-03-08T00:00:00Z',
      },
      projects: {
        used: 10,
        limit: -1,
      },
    })

    renderWithQuery(<QuotaBadge />)

    expect(await screen.findByText('无限')).toBeInTheDocument()
  })
})
