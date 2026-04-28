import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubscriptionManagement from "../SubscriptionManagement";
import { toast } from "../../../lib/toast";

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const invalidateQueriesMock = vi.fn();
const mutateMock = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "zh-CN" },
  }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
  useMutation: (...args: unknown[]) => useMutationMock(...args),
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
}));

vi.mock("../../../lib/subscriptionEntitlements", () => ({
  getLocalizedPlanDisplayName: (plan: { display_name?: string; display_name_en?: string; name?: string }) =>
    plan.display_name ?? plan.display_name_en ?? plan.name ?? "",
}));

vi.mock("../../../lib/toast", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const defaultPlan = [
  {
    id: "plan-pro",
    name: "pro",
    display_name: "Pro",
    display_name_en: "Pro",
    price_monthly_cents: 1999,
    price_yearly_cents: 19999,
    features: {},
    is_active: true,
  },
];

const subscriptionItem = {
  id: "sub-1",
  user_id: "user-1",
  username: "writer",
  email: "writer@example.com",
  plan_name: "pro",
  plan_display_name: "Pro",
  plan_display_name_en: "Pro",
  status: "active",
  current_period_start: "2026-03-01T00:00:00Z",
  current_period_end: "2026-04-01T00:00:00Z",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  has_subscription_record: true,
};

const mockQueries = ({
  subscriptionsData,
  subscriptionsLoading = false,
  subscriptionsError = false,
  subscriptionsErrorMessage,
  plansData = defaultPlan,
}: {
  subscriptionsData?: unknown;
  subscriptionsLoading?: boolean;
  subscriptionsError?: boolean;
  subscriptionsErrorMessage?: string;
  plansData?: unknown;
}) => {
  const refetchMock = vi.fn();

  useQueryMock.mockImplementation(({ queryKey }: { queryKey?: unknown[] }) => {
    if (Array.isArray(queryKey) && queryKey[1] === "subscriptions") {
      return {
        data: subscriptionsData,
        isLoading: subscriptionsLoading,
        isFetching: false,
        isError: subscriptionsError,
        error: subscriptionsErrorMessage ? new Error(subscriptionsErrorMessage) : null,
        refetch: refetchMock,
      };
    }

    if (Array.isArray(queryKey) && queryKey[1] === "plans") {
      return {
        data: plansData,
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      };
    }

    return {
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    };
  });

  return { refetchMock };
};

describe("SubscriptionManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMutationMock.mockReturnValue({
      mutate: mutateMock,
      isPending: false,
    });
  });

  it("shows loading state", () => {
    mockQueries({ subscriptionsLoading: true });

    render(<SubscriptionManagement />);
    expect(screen.getByText("common:loading")).toBeInTheDocument();
  });

  it("shows error state and supports retry", () => {
    const { refetchMock } = mockQueries({
      subscriptionsError: true,
      subscriptionsErrorMessage: "load subscriptions failed",
    });

    render(<SubscriptionManagement />);
    expect(screen.getByText("load subscriptions failed")).toBeInTheDocument();

    fireEvent.click(screen.getByText("common:retry"));
    expect(refetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows empty state", () => {
    mockQueries({
      subscriptionsData: { items: [], total: 0, page: 1, page_size: 20 },
    });

    render(<SubscriptionManagement />);
    expect(screen.getByText("common:noData")).toBeInTheDocument();
  });

  it("submits duration update from modify modal", () => {
    mockQueries({
      subscriptionsData: { items: [subscriptionItem], total: 1, page: 1, page_size: 20 },
    });

    render(<SubscriptionManagement />);

    fireEvent.click(screen.getByTitle("subscriptions.modify"));
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "subscriptions.saveChanges" }));

    expect(mutateMock).toHaveBeenCalledWith({
      userId: "user-1",
      data: { plan_name: "pro", duration_days: 30 },
    });
  });

  it("shows no-changes error when submitting unchanged form", () => {
    mockQueries({
      subscriptionsData: { items: [subscriptionItem], total: 1, page: 1, page_size: 20 },
    });

    render(<SubscriptionManagement />);

    fireEvent.click(screen.getByTitle("subscriptions.modify"));
    fireEvent.click(screen.getByRole("button", { name: "subscriptions.saveChanges" }));

    expect(mutateMock).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith("subscriptions.noChanges");
  });
});
