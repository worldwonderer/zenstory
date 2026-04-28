import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import QuotaManagement from "../QuotaManagement";

const useQueryMock = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
}));

describe("QuotaManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockQueries = ({
    statsLoading = false,
    statsError = false,
    statsErrorMessage,
    statsData = {
      material_uploads: 120,
      material_decomposes: 80,
      skill_creates: 30,
      inspiration_copies: 40,
    },
    userData,
  }: {
    statsLoading?: boolean;
    statsError?: boolean;
    statsErrorMessage?: string;
    statsData?: unknown;
    userData?: unknown;
  }) => {
    const statsRefetchMock = vi.fn();

    useQueryMock.mockImplementation(({ queryKey }: { queryKey?: unknown[] }) => {
      if (Array.isArray(queryKey) && queryKey[0] === "admin" && queryKey[1] === "quota" && queryKey[2] === "stats") {
        return {
          data: statsData,
          isLoading: statsLoading,
          isFetching: false,
          isError: statsError,
          error: statsErrorMessage ? new Error(statsErrorMessage) : null,
          refetch: statsRefetchMock,
        };
      }

      if (Array.isArray(queryKey) && queryKey[0] === "admin" && queryKey[1] === "quota" && queryKey[2] === "user") {
        return {
          data: queryKey[3] ? userData : undefined,
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

    return { statsRefetchMock };
  };

  it("shows stats loading state", () => {
    mockQueries({ statsLoading: true });

    render(<QuotaManagement />);
    expect(screen.getByText("common:loading")).toBeInTheDocument();
  });

  it("shows stats error and supports retry", () => {
    const { statsRefetchMock } = mockQueries({
      statsError: true,
      statsErrorMessage: "load quota stats failed",
    });

    render(<QuotaManagement />);
    expect(screen.getByText("load quota stats failed")).toBeInTheDocument();

    fireEvent.click(screen.getByText("common:retry"));
    expect(statsRefetchMock).toHaveBeenCalledTimes(1);
  });

  it("searches user and renders quota usage detail", () => {
    mockQueries({
      userData: {
        user_id: "user-1",
        username: "writer",
        plan_name: "pro",
        ai_conversations_used: 50,
        ai_conversations_limit: 100,
        material_upload_used: 10,
        material_upload_limit: 20,
        skill_create_used: 3,
        skill_create_limit: 10,
        inspiration_copy_used: 5,
        inspiration_copy_limit: 10,
      },
    });

    render(<QuotaManagement />);

    fireEvent.change(screen.getByPlaceholderText("quota.searchUser"), {
      target: { value: "user-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "common:search" }));

    expect(screen.getByText("writer")).toBeInTheDocument();
    expect(screen.getByText("pro")).toBeInTheDocument();
    expect(screen.getByText("50 / 100")).toBeInTheDocument();
    expect(screen.getByText("10 / 20")).toBeInTheDocument();
  });
});
