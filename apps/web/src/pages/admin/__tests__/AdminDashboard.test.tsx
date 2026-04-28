import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetDashboardStats = vi.fn();
const mockGetActivationFunnel = vi.fn();
const mockGetUpgradeFunnelStats = vi.fn();
const mockGetUpgradeConversionStats = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: string | { defaultValue?: string }) => {
      if (typeof options === 'string') {
        return options;
      }
      return options?.defaultValue ?? key;
    },
  }),
}));

vi.mock('@/lib/adminApi', () => ({
  adminApi: {
    getDashboardStats: () => mockGetDashboardStats(),
    getActivationFunnel: (days: number) => mockGetActivationFunnel(days),
    getUpgradeFunnelStats: (days: number) => mockGetUpgradeFunnelStats(days),
    getUpgradeConversionStats: (days: number) => mockGetUpgradeConversionStats(days),
  },
}));

vi.mock('@/components/admin/RecentActivityList', () => ({
  RecentActivityList: () => <div data-testid="recent-activity-placeholder" />,
}));

import AdminDashboard from '../AdminDashboard';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

describe('AdminDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockGetDashboardStats.mockResolvedValue({
      total_users: 100,
      total_projects: 40,
      total_inspirations: 22,
      active_subscriptions: 12,
      total_points_in_circulation: 5000,
      today_check_ins: 20,
      active_invite_codes: 9,
      week_referrals: 4,
    });

    mockGetActivationFunnel.mockResolvedValue({
      window_days: 7,
      period_start: '2026-03-01T00:00:00Z',
      period_end: '2026-03-08T00:00:00Z',
      activation_rate: 0.5,
      steps: [],
    });

    mockGetUpgradeFunnelStats.mockResolvedValue({
      window_days: 7,
      period_start: '2026-03-01T00:00:00Z',
      period_end: '2026-03-08T00:00:00Z',
      totals: { expose: 20, click: 10, conversion: 4 },
      sources: [],
    });

    mockGetUpgradeConversionStats.mockResolvedValue({
      window_days: 7,
      period_start: '2026-03-01T00:00:00Z',
      period_end: '2026-03-08T00:00:00Z',
      total_conversions: 5,
      unattributed_conversions: 2,
      sources: [
        {
          source: 'chat_quota_blocked',
          conversions: 2,
          share: 0.4,
        },
        {
          source: 'settings_subscription_upgrade',
          conversions: 1,
          share: 0.2,
        },
      ],
    });
  });

  it('renders paid conversion attribution and refetches on window change', async () => {
    render(<AdminDashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('付费转化归因')).toBeInTheDocument();
    });

    expect(mockGetUpgradeConversionStats).toHaveBeenCalledWith(7);
    expect(screen.getByText('Attributed sources: 2')).toBeInTheDocument();
    expect(screen.getByText('chat_quota_blocked')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '14天' }));

    await waitFor(() => {
      expect(mockGetUpgradeConversionStats).toHaveBeenCalledWith(14);
    });
  });
});
