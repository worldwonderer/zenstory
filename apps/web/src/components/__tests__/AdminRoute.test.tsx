import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  auth: {
    user: null as { is_superuser?: boolean } | null,
    loading: false,
  },
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => state.auth,
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const dictionary: Record<string, string> = {
        "admin.verifyingPermission": "Verifying permission",
        "admin.insufficientPermission": "Insufficient permission",
        "admin.superuserRequired": "Superuser required",
        "admin.backToHome": "Back to Home",
      };
      return dictionary[key] ?? key;
    },
  }),
}));

import { AdminRoute } from "../AdminRoute";

const renderRoute = () =>
  render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <div>Admin Content</div>
            </AdminRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );

describe("AdminRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.auth.loading = false;
    state.auth.user = null;
  });

  it("shows loading state while auth is resolving", () => {
    state.auth.loading = true;

    renderRoute();

    expect(screen.getByText("Verifying permission")).toBeInTheDocument();
  });

  it("redirects anonymous users to login", () => {
    state.auth.user = null;

    renderRoute();

    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });

  it("blocks non-superusers", () => {
    state.auth.user = { is_superuser: false };

    renderRoute();

    expect(screen.getByText("Insufficient permission")).toBeInTheDocument();
    expect(screen.getByText("Superuser required")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to Home" })).toBeInTheDocument();
  });

  it("renders admin children for superusers", () => {
    state.auth.user = { is_superuser: true };

    renderRoute();

    expect(screen.getByText("Admin Content")).toBeInTheDocument();
  });

  it("triggers homepage navigation action for blocked users", () => {
    state.auth.user = { is_superuser: false };

    const originalLocation = window.location;
    // happy-dom Location may not implement assign; override with a minimal mock for this test.
    // @ts-expect-error - test override
    delete window.location;
    // @ts-expect-error - test override
    window.location = { href: "", assign: vi.fn() } as Location;
    const assignSpy = vi.spyOn(window.location, "assign");

    renderRoute();
    fireEvent.click(screen.getByRole("button", { name: "Back to Home" }));

    expect(assignSpy).toHaveBeenCalledWith("/");

    window.location = originalLocation;
  });
});
