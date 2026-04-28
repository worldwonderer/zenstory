import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubscriptionPlanManagement from "../SubscriptionPlanManagement";

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const invalidateQueriesMock = vi.fn();
const mutateMock = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
  useMutation: (...args: unknown[]) => useMutationMock(...args),
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
}));

vi.mock("../../../lib/toast", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const plan = {
  id: "plan-pro",
  name: "pro",
  display_name: "专业版",
  display_name_en: "Pro",
  price_monthly_cents: 1999,
  price_yearly_cents: 19999,
  features: {
    ai_conversations_per_day: 100,
    max_projects: 10,
    custom_prompts: true,
  },
  is_active: true,
};

describe("SubscriptionPlanManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMutationMock.mockReturnValue({
      mutate: mutateMock,
      isPending: false,
    });
  });

  it("shows loading state", () => {
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SubscriptionPlanManagement />);
    expect(screen.getByText("common:loading")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    useQueryMock.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SubscriptionPlanManagement />);
    expect(screen.getByText("common:noData")).toBeInTheDocument();
  });

  it("validates features JSON before saving", () => {
    useQueryMock.mockReturnValue({
      data: [plan],
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SubscriptionPlanManagement />);

    fireEvent.click(screen.getByRole("button", { name: "plans.edit" }));

    fireEvent.change(screen.getByPlaceholderText("plans.featuresDetail.jsonPlaceholder"), {
      target: { value: "{" },
    });

    expect(screen.getByText("plans.invalidJson")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "plans.save" })).toBeDisabled();
    expect(mutateMock).not.toHaveBeenCalled();
  });

  it("submits updated plan payload", () => {
    useQueryMock.mockReturnValue({
      data: [plan],
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SubscriptionPlanManagement />);

    fireEvent.click(screen.getByRole("button", { name: "plans.edit" }));
    fireEvent.click(screen.getByRole("button", { name: "plans.save" }));

    expect(mutateMock).toHaveBeenCalledWith({
      planId: "plan-pro",
      data: {
        display_name: "专业版",
        display_name_en: "Pro",
        price_monthly_cents: 1999,
        price_yearly_cents: 19999,
        is_active: true,
        features: {
          ai_conversations_per_day: 100,
          max_projects: 10,
          custom_prompts: true,
        },
      },
    });
  });
});
