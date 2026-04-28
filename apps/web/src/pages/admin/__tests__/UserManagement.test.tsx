import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import UserManagement from "../UserManagement";

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const invalidateQueriesMock = vi.fn();

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

describe("UserManagement", () => {
  const sampleUser = {
    id: "user-1",
    username: "writer",
    email: "writer@example.com",
    email_verified: true,
    is_active: true,
    is_superuser: false,
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useMutationMock.mockReturnValue({
      mutate: vi.fn(),
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

    render(<UserManagement />);
    expect(screen.getByText("common:loading")).toBeInTheDocument();
  });

  it("shows error state and supports retry", () => {
    const refetchMock = vi.fn();
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: new Error("load users failed"),
      refetch: refetchMock,
    });

    render(<UserManagement />);
    expect(screen.getByText("load users failed")).toBeInTheDocument();

    fireEvent.click(screen.getByText("common:retry"));
    expect(refetchMock).toHaveBeenCalledTimes(1);
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

    render(<UserManagement />);
    expect(screen.getByText("common:noData")).toBeInTheDocument();
  });

  it("submits search query", async () => {
    useQueryMock.mockReturnValue({
      data: [sampleUser],
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<UserManagement />);

    fireEvent.change(screen.getByPlaceholderText("users.search"), {
      target: { value: "writer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "common:search" }));

    await waitFor(() => {
      expect(useQueryMock).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ["admin", "users", 0, "writer"],
        }),
      );
    });
  });

  it("opens edit modal and submits update payload", () => {
    const mutateMock = vi.fn();
    useMutationMock.mockReturnValue({
      mutate: mutateMock,
      isPending: false,
    });
    useQueryMock.mockReturnValue({
      data: [sampleUser],
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<UserManagement />);

    fireEvent.click(screen.getAllByTitle("users.edit")[0]);
    expect(screen.getByText("users.editUser")).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("writer"), {
      target: { value: "writer-updated" },
    });
    mutateMock.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "common:save" }));

    expect(mutateMock).toHaveBeenCalledWith({
      id: "user-1",
      data: {
        username: "writer-updated",
        email: "writer@example.com",
        is_active: true,
        is_superuser: false,
      },
    });
  });

  it("opens delete modal and confirms delete", () => {
    const mutateMock = vi.fn();
    useMutationMock.mockReturnValue({
      mutate: mutateMock,
      isPending: false,
    });
    useQueryMock.mockReturnValue({
      data: [sampleUser],
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<UserManagement />);

    fireEvent.click(screen.getAllByTitle("users.delete")[0]);
    expect(screen.getByText("users.deleteConfirm")).toBeInTheDocument();

    mutateMock.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "common:confirm" }));
    expect(mutateMock).toHaveBeenCalledWith("user-1");
  });
});
