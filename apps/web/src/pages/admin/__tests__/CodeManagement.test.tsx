import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import CodeManagement from "../CodeManagement";

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const invalidateQueriesMock = vi.fn();
const mutateMock = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === "codes.batchCreateSuccess" && options?.count) {
        return `${key}:${options.count}`;
      }
      return key;
    },
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

describe("CodeManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMutationMock.mockReturnValue({
      mutate: mutateMock,
      isPending: false,
    });

    vi.stubGlobal("navigator", {
      clipboard: {
        writeText: vi.fn(),
      },
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

    render(<CodeManagement />);
    expect(screen.getByText("common:loading")).toBeInTheDocument();
  });

  it("shows error state and supports retry", () => {
    const refetchMock = vi.fn();
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: new Error("load codes failed"),
      refetch: refetchMock,
    });

    render(<CodeManagement />);
    expect(screen.getByText("load codes failed")).toBeInTheDocument();

    fireEvent.click(screen.getByText("common:retry"));
    expect(refetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows empty state", () => {
    useQueryMock.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CodeManagement />);
    expect(screen.getByText("common:noData")).toBeInTheDocument();
  });

  it("toggles code status", () => {
    useQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "code-1",
            code: "TESTCODE",
            tier: "pro",
            duration_days: 30,
            code_type: "single_use",
            max_uses: 1,
            current_uses: 0,
            is_active: true,
            notes: null,
            created_at: "2026-03-08T00:00:00Z",
            updated_at: "2026-03-08T00:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CodeManagement />);

    mutateMock.mockClear();
    fireEvent.click(screen.getAllByTitle("codes.deactivate")[0]);

    expect(mutateMock).toHaveBeenCalledWith({
      id: "code-1",
      data: { is_active: false },
    });
  });

  it("submits single and batch create", () => {
    useQueryMock.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CodeManagement />);

    const createButtonsBefore = screen.getAllByRole("button", { name: "codes.create" });
    fireEvent.click(createButtonsBefore[0]);
    mutateMock.mockClear();
    const createButtonsAfter = screen.getAllByRole("button", { name: "codes.create" });
    fireEvent.click(createButtonsAfter[createButtonsAfter.length - 1]);

    expect(mutateMock).toHaveBeenCalledWith({
      tier: "pro",
      duration_days: 30,
      code_type: "single_use",
      max_uses: 1,
      notes: "",
    });

    const batchButtonsBefore = screen.getAllByRole("button", { name: "codes.batchCreate" });
    fireEvent.click(batchButtonsBefore[0]);
    mutateMock.mockClear();
    const batchButtonsAfter = screen.getAllByRole("button", { name: "codes.batchCreate" });
    fireEvent.click(batchButtonsAfter[batchButtonsAfter.length - 1]);

    expect(mutateMock).toHaveBeenCalledWith({
      tier: "pro",
      duration_days: 30,
      count: 10,
      code_type: "single_use",
      notes: "",
    });
  });
});
