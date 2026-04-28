import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockNavigate = vi.fn();
const mockHandleOAuthCallback = vi.fn();
const mockCaptureException = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          "auth:errors.oauthFailed": "Login failed",
          "auth:login.loading": "Loading",
          "auth:login.title": "Login",
          "auth:login.verifying": "Verifying identity...",
          "auth:login.failed": "Login failed",
          "auth:login.redirecting": "Redirecting...",
          "auth:login.oauthLoading": "Completing Google login, please wait...",
          "auth:login.backToLogin": "Back to login",
          "auth:errors.oauthErrorHint": "OAuth hint",
        } as Record<string, string>
      )[key] ?? key,
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../../components/PublicHeader", () => ({
  PublicHeader: () => <div>PublicHeader</div>,
}));

vi.mock("../../components/LoadingSpinner", () => ({
  LoadingSpinner: ({ label }: { label?: string }) => <div>{label ?? "Loading"}</div>,
}));

vi.mock("../../components/Logo", () => ({
  LogoMark: () => <div>Logo</div>,
}));

vi.mock("../../lib/ssoRedirect", () => ({
  isValidRedirectUrl: () => true,
}));

vi.mock("../../lib/analytics", () => ({
  captureException: (...args: unknown[]) => mockCaptureException(...args),
}));

import OAuthCallback from "../OAuthCallback";

describe("OAuthCallback", () => {
  const originalLocation = window.location;
  const replaceStateSpy = vi.spyOn(window.history, "replaceState");

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockUseAuth.mockReturnValue({
      handleOAuthCallback: mockHandleOAuthCallback,
      user: null,
    });

    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        ...originalLocation,
        pathname: "/auth/callback",
        search: "",
        hash: "",
        href: "http://localhost:5173/auth/callback",
      },
    });
  });

  it("handles token callback from hash and redirects to dashboard", async () => {
    mockHandleOAuthCallback.mockResolvedValue(undefined);
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        ...originalLocation,
        pathname: "/auth/callback",
        search: "",
        hash: "#access_token=access&refresh_token=refresh",
        href: "http://localhost:5173/auth/callback#access_token=access&refresh_token=refresh",
      },
    });

    render(
      <MemoryRouter>
        <OAuthCallback />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockHandleOAuthCallback).toHaveBeenCalledWith("access", "refresh");
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    });
    expect(replaceStateSpy).toHaveBeenCalled();
    expect(mockCaptureException).not.toHaveBeenCalled();
  });

  it("redirects silently to dashboard when callback tokens are missing but auth context already has a user", async () => {
    mockUseAuth.mockReturnValue({
      handleOAuthCallback: mockHandleOAuthCallback,
      user: { id: "user-1" },
    });

    render(
      <MemoryRouter>
        <OAuthCallback />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    });
    expect(mockHandleOAuthCallback).not.toHaveBeenCalled();
    expect(mockCaptureException).not.toHaveBeenCalled();
    expect(screen.queryByText("Missing tokens in callback")).not.toBeInTheDocument();
  });

  it("redirects back to login when callback is opened without OAuth params or cached session", async () => {
    render(
      <MemoryRouter>
        <OAuthCallback />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/login", { replace: true });
    });
    expect(mockHandleOAuthCallback).not.toHaveBeenCalled();
    expect(mockCaptureException).not.toHaveBeenCalled();
  });
});
